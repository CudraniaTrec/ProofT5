import torch, json, datetime, swanlab, random, os, pickle
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
from torch.utils.data import Dataset, DataLoader, SequentialSampler
from tqdm import tqdm
from evaluator.CodeBLEU.calc_code_bleu import get_codebleu
from evaluator.bleu import _bleu, bleu_from_list
import numpy as np
import time
seed = 273567
random.seed(seed)
np.random.seed(seed)
torch.manual_seed(seed)
torch.cuda.manual_seed(seed)
torch.cuda.manual_seed_all(seed)
os.environ['PYTHONHASHSEED'] = str(seed)

def get_special_tokens(tokenizer):
    token_id_mapping = {}
    # if tokenizer.pad_token:
    #     token_id_mapping[tokenizer.pad_token] = tokenizer.pad_token_id # 0
    # if tokenizer.cls_token:
    #     token_id_mapping[tokenizer.cls_token] = tokenizer.cls_token_id # 1
    # if tokenizer.bos_token:
    #     token_id_mapping[tokenizer.bos_token] = tokenizer.bos_token_id # 1
    # if tokenizer.eos_token:
    #     token_id_mapping[tokenizer.eos_token] = tokenizer.eos_token_id # 2
    # if tokenizer.sep_token:
    #     token_id_mapping[tokenizer.sep_token] = tokenizer.sep_token_id # 2
    # if tokenizer.unk_token:
    #     token_id_mapping[tokenizer.unk_token] = tokenizer.unk_token_id # 3
    # if tokenizer.mask_token:
    #     token_id_mapping[tokenizer.mask_token] = tokenizer.mask_token_id # 4
    # 添加additional tokens
    for token in tokenizer.additional_special_tokens:
        token_id_mapping[token] = tokenizer.convert_tokens_to_ids(token)
    return token_id_mapping

class CodeDataset(Dataset):
    def __init__(self, data, tokenizer, max_length=1024, codeproof=False):
        self.data = data
        self.tokenizer = tokenizer
        self.max_length = max_length
        self.inputs = []
        self.outputs = []
        token_id_mapping = get_special_tokens(tokenizer)
        code_id = token_id_mapping['<code>']
        code_end_id = token_id_mapping['</code>']
        proof_id = token_id_mapping['<proof>']
        proof_end_id = token_id_mapping['</proof>']
        bos_id = tokenizer.bos_token_id
        eos_id = tokenizer.eos_token_id
        output_lens = []
        proof_lens = []
        for example in self.data:
            if 'code' in example:
                code = example['code']
            else:
                code = example['prompt'] + example['canonical_solution']
            description = example['prompt']
            input = tokenizer.encode(description,
                                     return_tensors="pt",
                                     max_length=self.max_length,
                                     truncation=True,
                                     padding='max_length')[0]
            output = tokenizer.encode(code, return_tensors="pt")[0]
            if 'proof' in example:
                if codeproof:
                    output = [bos_id, code_id] + output.tolist()[1:-1] + [code_end_id, proof_id] + [token for token in example['proof'] if token>=32000] + [proof_end_id, eos_id]
                else:
                    output = [bos_id, proof_id] + [token for token in example['proof'] if token>=32000] + [proof_end_id, code_id] + output.tolist()[1:-1] + [code_end_id, eos_id]
            else:
                output = [bos_id] + output.tolist()[1:-1] + [eos_id]
            current_length = len(output)
            output_lens.append(current_length)
            proof_lens.append(len(example['proof']) if 'proof' in example else 0)
            pad_token_id = tokenizer.eos_token_id
            if current_length > max_length:
                output = output[:max_length-1] + [output[-1]]
            elif current_length < max_length:
                output = output + [pad_token_id] * (max_length - current_length)
            output = torch.tensor(output)
            self.inputs.append(input)
            self.outputs.append(output)
        if output_lens:
            print(f"Max output length: {max(output_lens)}, Min output length: {min(output_lens)}, Average output length: {sum(output_lens)/len(output_lens)}")
        if proof_lens:
            print(f"Max proof length: {max(proof_lens)}, Min proof length: {min(proof_lens)}, Average proof length: {sum(proof_lens)/len(proof_lens)}")

    def __len__(self):
        return len(self.data)

    def __getitem__(self, idx):
        return {
            'input': self.inputs[idx],
            'output': self.outputs[idx]
        }

def train_epoch(model, train_dataset, optimizer, device="cuda", batch_size=10):
    model.train()
    total_loss = 0
    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
    for batch in train_loader:
        optimizer.zero_grad()
        input_ids = batch['input'].to(device=device)
        target_ids = batch['output'].to(device=device)
        input_mask = input_ids.ne(0)

        outputs = model(input_ids, attention_mask=input_mask, labels=target_ids)
        loss = outputs.loss
        loss.backward()
        optimizer.step()
        total_loss += loss.item()
    return total_loss / len(train_loader)

def test_epoch(model, eval_dataset, codebleu_dataset, tokenizer, topk=10, device="cuda", output_path=None):
    token_id_mapping = get_special_tokens(tokenizer)
    code_id = token_id_mapping['<code>']
    code_end_id = token_id_mapping['</code>']
    bos_id = tokenizer.bos_token_id
    eos_id = tokenizer.eos_token_id
    def retrive_code_from_output(output_ids):
        if code_id in output_ids and code_end_id in output_ids:
            code_start = output_ids.index(code_id) + 1
            code_end = output_ids.index(code_end_id)
            return [bos_id] + output_ids[code_start:code_end] + [eos_id]
        else:
            return output_ids

    model.eval()
    test_sampler = SequentialSampler(eval_dataset)
    test_loader = DataLoader(eval_dataset, sampler = test_sampler, batch_size=10)
    predictions = []
    for batch in test_loader:
        input_ids = batch['input'].to(device=device)
        input_mask = input_ids.ne(0)
        with torch.no_grad():
            preds = model.generate(
                input_ids,
                attention_mask=input_mask,
                max_length=1024,
                num_beams=topk,
                num_return_sequences=topk)
        predictions.extend(list(preds.cpu().numpy()))

    predictions = [retrive_code_from_output(pred.tolist()) for pred in predictions]
    pred_texts = tokenizer.batch_decode(predictions, skip_special_tokens=True)
    codebleu = get_codebleu([ref.strip() for ref in codebleu_dataset], [pred.strip() for pred in pred_texts[::topk]], 'java')
    if output_path:
        output_dir = f"../Utils/output/{output_path}/"
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        for num in range(len(pred_texts) // topk):
            for i in range(topk):
                with open(f"{output_dir}{num}_{i}.txt", "w") as f:
                    f.write(pred_texts[num * topk + i])
        print(f"Test predictions saved to {output_dir}")
    model.train()  # Reset model to training mode
    return pred_texts, codebleu

def finetune(model_name="Salesforce/codet5-base",
             dataset_name="humaneval",
             cuda_num=0,
             warmup_epochs=50,
             eval_step=20,
             lr=5e-4,
             weight_decay=1e-2):
    # 加载 T5 模型和 Tokenizer
    model = AutoModelForSeq2SeqLM.from_pretrained(model_name,local_files_only=False, trust_remote_code=True)
    # tokenizer = AutoTokenizer.from_pretrained(model_name,local_files_only=False, trust_remote_code=True)
    tokenizer = pickle.load(open("data/tokenizer.pkl", "rb"))
    model.resize_token_embeddings(len(tokenizer))

    time.sleep(cuda_num*10)
    date = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    model_name = model_name.split("/")[-1]
    task_name = f"{model_name}_{dataset_name}"
    swanlab_log = swanlab.init(
        project="finetune_codet5",
        experiment_name= f"{model_name}_{dataset_name}_{date}",
    )
    swanlab_log.log({
        "Learning Rate": lr,
        "Weight Decay": weight_decay,
        "Warmup Epochs": warmup_epochs,
        "Eval Step": eval_step,
    })

    # 加载数据集
    humaneval_path = "data/humaneval_t5.json"
    mbjp_path = "data/mbjp_t5.json"
    sufu_path = "data/sufu_t5.json"
    codeproof = False
    if dataset_name == "humaneval":
        data_path = humaneval_path
    elif dataset_name == "mbjp":
        data_path = mbjp_path
    elif dataset_name == "sufu":
        data_path = sufu_path
    elif dataset_name == "sufu_codeproof":
        data_path = "data/sufu_t5_codeproof.json"
        codeproof = True
    elif dataset_name == "sufu_proofcode":
        data_path = "data/sufu_t5_codeproof.json"
        codeproof = False
    elif dataset_name == "mbjp_codeproof":
        data_path = "data/mbjp_t5_codeproof.json"
        codeproof = True
    elif dataset_name == "mbjp_proofcode":
        data_path = "data/mbjp_t5_codeproof.json"
        codeproof = False
    else:
        raise ValueError("Unsupported dataset name. Choose from 'humaneval', 'mbjp', or 'sufu'.")
    with open(data_path, "r") as f:
        datas = json.load(f)

    # print dataset statistics
    all_tokenized_codes = [tokenizer.tokenize(data['code'] if "code" in data else data['prompt']+data['canonical_solution']) for data in datas]
    print(f"Max code length in {dataset_name}: {max(len(code) for code in all_tokenized_codes)}")
    print(f"Min code length in {dataset_name}: {min(len(code) for code in all_tokenized_codes)}")
    print(f"Average code length in {dataset_name}: {sum(len(code) for code in all_tokenized_codes) / len(all_tokenized_codes)}")

    # split data into train, valid, and test sets
    train_data = [data for data in datas if data['type'] == 'train']
    valid_data = [data for data in datas if data['type'] == 'valid']
    test_data = [data for data in datas if data['type'] == 'test']
    train_dataset = CodeDataset(train_data, tokenizer, codeproof=codeproof)
    valid_dataset = CodeDataset(valid_data, tokenizer, codeproof=codeproof)
    test_dataset = CodeDataset(test_data, tokenizer, codeproof=codeproof)
    test_data_path = f"../Utils/data/{task_name}"
    if not os.path.exists(test_data_path):
        os.makedirs(test_data_path)
    with open(f"{test_data_path}/test.pkl", "wb") as f:
        pickle.dump(test_data, f)
    with open(f"{test_data_path}/valid.pkl", "wb") as f:
        pickle.dump(valid_data, f)
    with open(f"{test_data_path}/train.pkl", "wb") as f:
        pickle.dump(train_data, f)

    # get codebleu base
    if dataset_name in ["humaneval"]:
        codebleu_validbase = [data['code'] for data in valid_data]
        codebleu_testbase = [data['code'] for data in test_data]
    elif dataset_name in ["mbjp", "mbjp_codeproof", "mbjp_proofcode"]:
        codebleu_validbase = [data['prompt']+data['canonical_solution'] for data in valid_data]
        codebleu_testbase = [data['prompt']+data['canonical_solution'] for data in test_data]
    elif dataset_name in ["sufu", "sufu_codeproof", "sufu_proofcode"]:
        codebleu_validbase = [data['code'] for data in test_data]
        codebleu_testbase = [data['code'] for data in test_data]
        valid_dataset = test_dataset
    else:
        raise ValueError("Unsupported dataset name. Choose from 'humaneval', 'mbjp', or 'sufu'.")

    device = "cuda" if cuda_num == -1 else f"cuda:{cuda_num}"
    model = model.to(device=device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=weight_decay)
    highest_score, patient = 0, 0
    batch_size_map = {
        "codet5-base_sufu": 15,
        "codet5p-220m_sufu": 15,
        "codet5p-770m_sufu": 6,
        "Qwen2.5-0.5B_sufu": 10,
        "codet5-base_mbjp": 20,
        "codet5p-220m_mbjp": 20,
        "codet5p-770m_mbjp": 6,
        "codet5-base_sufu_codeproof": 5,
        "codet5-base_sufu_proofcode": 5,
        "codet5-base_mbjp_codeproof": 5,
        "codet5-base_mbjp_proofcode": 5,
    }
    batch_size = batch_size_map.get(task_name, 10)

    for epoch in range(500):
        train_loss = train_epoch(model, train_dataset, optimizer, device=device, batch_size=batch_size)
        print(f"Task {task_name} Epoch {epoch} Train Loss: {train_loss}")
        swanlab_log.log({"Loss": train_loss})
        if epoch % eval_step == 0 and epoch >= warmup_epochs:
            _, codebleu = test_epoch(model, valid_dataset, codebleu_validbase, tokenizer, topk=1, device=device)
            _, codebleu_test = test_epoch(model, test_dataset, codebleu_testbase, tokenizer, topk=10, device=device, output_path=f"{task_name}_test_ans/{date}/{epoch}")
            print(f"Task {task_name} Epoch {epoch} Valid CodeBLEU: {codebleu}")
            score = codebleu
            swanlab_log.log({"Valid CodeBLEU": codebleu})
            swanlab_log.log({"Test CodeBLEU": codebleu_test})
            if score > highest_score:
                highest_score = score
                print(f"Highest Score: {highest_score}")
                patient = 0
            else:
                patient += 1
                if patient >= 3:
                    break
            model.save_pretrained(f"models/{task_name}/{date}/epoch_{epoch}")
            torch.cuda.empty_cache()

    model.save_pretrained(f"models/{task_name}")
    _, codebleu = test_epoch(model, test_dataset, codebleu_testbase, tokenizer, topk=10, device=device, output_path=f"{task_name}_test_ans/")
    print(f"{'='*20}Task {task_name} Test CodeBLEU: {codebleu}{'='*20}")
    swanlab_log.finish()

if __name__ == "__main__":
    tasks = [
        # ("Salesforce/codet5-base", "sufu_codeproof", 1, 20, 10, 9e-4, 1e-3),
        # ("Salesforce/codet5-base", "sufu_proofcode", 2, 20, 20, 9e-4, 1e-4),
        # ("Salesforce/codet5-base", "mbjp_proofcode", 3, 10, 5, 4e-4, 1e-2),
        # ("Salesforce/codet5-base", "mbjp_codeproof", 4, 10, 5, 9e-4, 1e-3),
        ("Salesforce/codet5-base", "sufu_codeproof", 0, 10, 5, 4e-4, 1e-3),
        # ("Salesforce/codet5p-220m", "mbjp", 1, 200, 20, 4e-4, 1e-4),
        # ("Salesforce/codet5p-2b", "sufu", 3),
        # ("Salesforce/codet5-base", "sufu", 4),
        # ("Salesforce/codet5p-220m", "sufu", 5),
    ]
    # tasks2 = [
    #     ("Salesforce/codet5p-220m", "mbjp", 0, 150, 10, 4e-4, 1e-4),
    # ]
    import multiprocessing as mp
    with mp.Pool(processes=len(tasks)+1) as pool:
        pool.starmap(finetune, tasks)
    # with mp.Pool(processes=len(tasks2)+1) as pool:
    #     pool.starmap(finetune, tasks2)

