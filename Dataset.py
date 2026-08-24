import torch
import torch.utils.data as data
from torch.utils.data import Sampler
import numpy as np

import os
import random, pickle
from transformers import AutoTokenizer

tokenizer_path = "Utils/models/codet5-small"
if not os.path.exists(tokenizer_path):
    tokenizer_path = "Salesforce/codet5-small"
try:
    tokenizer = AutoTokenizer.from_pretrained(tokenizer_path, local_files_only=True)
except (TypeError, ValueError):
    from transformers.models.roberta.tokenization_roberta import RobertaTokenizer
    tokenizer = RobertaTokenizer(
        os.path.join("Utils", "models", "codet5-small", "vocab.json"),
        os.path.join("Utils", "models", "codet5-small", "merges.txt"),
    )
args = {}

DEFAULT_PAD_TOKEN = tokenizer.pad_token_id
PAD_token = DEFAULT_PAD_TOKEN

def resolve_pad_token(config):
    get_value = config.get if isinstance(config, dict) else lambda key, default=None: getattr(config, key, default)
    if get_value("model_family") == "t5gemma2":
        return get_value("pad_token_id", get_value("mask_id", 0))
    return get_value("pad_token_id", DEFAULT_PAD_TOKEN)

class ChunkedRandomSampler(Sampler):
    def __init__(self, data_source, batch_size):
      self.data_source = data_source
      self.batch_size = batch_size

    def __iter__(self):
      lst = list(range(len(self.data_source)))
      chunked = [lst[i:i+self.batch_size] for i in range(0, len(self.data_source), self.batch_size)]
      random.shuffle(chunked)
      new_lst = [e for piece in chunked for e in piece]
      return iter(new_lst)

    def __len__(self):
      return len(self.data_source)

def pad_seq(seq, maxlen, reverse=False):
    if len(seq) < maxlen:
        seq_shape = np.array(seq).shape
        pad_shape = (maxlen - len(seq),) + seq_shape[1:]
        pad_elements = np.full(pad_shape, PAD_token).tolist()
        if reverse:
            seq = pad_elements + seq
        else:
            seq = seq + pad_elements
    return seq[:maxlen]
# pad nl and code to same maxlen
def rs_collate_fn(batch, cut_prefix=False):
    rbatch = {}
    batch_nl = []
    batch_res = []
    batch_prefix = []
    batch_coqview = []
    batch_distributed_padding = []

    max_nl_len = 0
    max_code_len = 0
    max_prefix_len = 0

    for k in (range(len(batch))):
        batch_distributed_padding.append(
            bool(batch[k].get("_distributed_zero_loss_padding", False))
        )
        inputnl = batch[k]['nl']
        inputres = batch[k]['rulelist'][1:-1]
        if "prefix" in batch[k]:
            prefix = batch[k]['prefix']
            batch_prefix.append(prefix)
            max_prefix_len = max(max_prefix_len, len(prefix))
            if cut_prefix:
                assert len(prefix) <= len(inputres) and all(a == b for a, b in zip(prefix, inputres)), f"prefix: {prefix}, inputres: {inputres}"
                inputres = inputres[len(prefix):]
        if "coqview" in batch[k]:
            inputcoqview = batch[k]['coqview']
            if cut_prefix:
                inputcoqview = inputcoqview[max(len(prefix) - 1, 0):]
            expected_coqview_len = len(inputres)
            if not cut_prefix or len(prefix) == 0:
                expected_coqview_len = len(inputres) - 1
            assert len(inputcoqview) == expected_coqview_len, f"inputcoqview: {len(inputcoqview)}, inputres: {len(inputres)}"
            inputcoqview = [pad_seq(coqview, args.max_coqview_len) for coqview in inputcoqview]
            batch_coqview.append(inputcoqview)
        
        max_nl_len = max(max_nl_len, len(inputnl))
        max_code_len = max(max_code_len, len(inputres))
        batch_nl.append(inputnl)
        batch_res.append(inputres)        
    max_nl_len = min(max_nl_len, args.NlLen)
    max_code_len = min(max_code_len, args.CodeLen)

    for i in range(len(batch_nl)):
        batch_nl[i] = pad_seq(batch_nl[i], max_nl_len)
        batch_res[i] = pad_seq(batch_res[i], max_code_len)
        if len(batch_coqview) > i:
            coqview_max_len = max_code_len if cut_prefix else max_code_len - 1
            batch_coqview[i] = pad_seq(batch_coqview[i], coqview_max_len)
    if len(batch_prefix) > 0:
        batch_prefix = [pad_seq(prefix, max_prefix_len) for prefix in batch_prefix]
        rbatch['prefix'] = torch.tensor(batch_prefix)
    rbatch['nl'] = torch.tensor(batch_nl)
    rbatch['res'] = torch.tensor(batch_res)
    rbatch['coqview'] = torch.tensor(batch_coqview)
    if any(batch_distributed_padding):
        padding_mask = torch.tensor(batch_distributed_padding, dtype=torch.bool)
        # Keep valid targets for the forward graph.  Padding-only distributed
        # batches use these targets and zero the resulting scalar loss in
        # run.py, avoiding NaN from an all-ignore target tensor while still
        # executing the same model graph on every rank.
        rbatch['distributed_zero_loss_padding_res'] = rbatch['res'].clone()
        rbatch['res'][padding_mask] = PAD_token
        rbatch['distributed_zero_loss_padding'] = padding_mask
    return rbatch

def rs_collate_fn_cutprefix(batch):
    return rs_collate_fn(batch, cut_prefix=True)

class SumDataset(data.Dataset):
    def __init__(self, config, dataName="train", idx=-1):
        global args, PAD_token
        args = config
        PAD_token = resolve_pad_token(config)
        config.mask_id = PAD_token
        self.dataName = dataName

        runtime_dir = config.get("runtime_dir", "tmp") if isinstance(config, dict) else getattr(config, "runtime_dir", "tmp")
        shard_path = os.path.join(runtime_dir, f"data_{dataName}{idx}.pkl")
        with open(shard_path, "rb") as f:
            self.data = pickle.load(f)
        
        import numpy as np
        leng = [ len(x['rulelist']) for x in self.data]
        leng2 = [ len(x['nl']) for x in self.data]
        print(f"{dataName} set({idx}) length: {len(self.data)}")
        if self.data:
            print(f"{dataName} set({idx}) mean rulelist length: {np.mean(leng)}")
            print(f"{dataName} set({idx}) max rulelist length: {np.max(leng)}")
            print(f"{dataName} set({idx}) mean nl length: {np.mean(leng2)}")
            print(f"{dataName} set({idx}) max nl length: {np.max(leng2)}")
        else:
            print(f"{dataName} set({idx}) is empty")

    def __getitem__(self, offset):
        return self.data[offset]
    def __len__(self):
        return len(self.data)
