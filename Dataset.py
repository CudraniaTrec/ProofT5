import torch
import torch.utils.data as data
from torch.utils.data import Sampler
import numpy as np

import random, pickle
from transformers import AutoTokenizer

tokenizer = AutoTokenizer.from_pretrained('Salesforce/codet5-small', local_files_only=True)
args = {}

PAD_token = tokenizer.pad_token_id

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

def pad_seq(seq, maxlen):
    if len(seq) < maxlen:
        seq_shape = np.array(seq).shape
        pad_shape = (maxlen - len(seq),) + seq_shape[1:]
        pad_elements = np.full(pad_shape, PAD_token).tolist()
        seq = seq + pad_elements
    return seq[:maxlen]
# pad nl and code to same maxlen
def rs_collate_fn(batch):
    rbatch = {}
    batch_nl = []
    batch_res = []
    batch_coqview = []

    max_nl_len = 0
    max_code_len = 0

    for k in (range(len(batch))):
        inputnl = batch[k]['nl']
        inputres = batch[k]['rulelist'][1:-1]
        if "coqview" in batch[k]:
            inputcoqview = batch[k]['coqview']
            assert len(inputcoqview) == len(inputres)-1, f"inputcoqview: {len(inputcoqview)}, inputres: {len(inputres)}"
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
            batch_coqview[i] = pad_seq(batch_coqview[i], max_code_len-1)
    rbatch['nl'] = torch.tensor(batch_nl)
    rbatch['res'] = torch.tensor(batch_res)
    rbatch['coqview'] = torch.tensor(batch_coqview)
    return rbatch

class SumDataset(data.Dataset):
    def __init__(self, config, dataName="train", idx=-1):
        global args
        args = config
        config.mask_id = PAD_token
        self.dataName = dataName

        self.data = None
        if dataName == "train":
            self.data = pickle.load(open('tmp/data_train%d.pkl'%idx, "rb"))   
        elif dataName == "valid":
            self.data = pickle.load(open('tmp/data_valid%d.pkl'%idx, 'rb'))
        else: # test
            self.data = pickle.load(open('tmp/data_test%d.pkl'%idx, 'rb'))
        
        import numpy as np
        leng = [ len(x['rulelist']) for x in self.data]
        leng2 = [ len(x['nl']) for x in self.data]
        print(f"{dataName} set({idx}) length: {len(self.data)}")
        print(f"{dataName} set({idx}) mean rulelist length: {np.mean(leng)}")
        print(f"{dataName} set({idx}) max rulelist length: {np.max(leng)}")
        print(f"{dataName} set({idx}) mean nl length: {np.mean(leng2)}")
        print(f"{dataName} set({idx}) max nl length: {np.max(leng2)}")

    def __getitem__(self, offset):
        return self.data[offset]
    def __len__(self):
        return len(self.data)
