import torch
from transformers import RobertaTokenizer, T5ForConditionalGeneration
from torch.utils.data import Dataset, DataLoader, SequentialSampler
import json
from tqdm import tqdm
from evaluator.CodeBLEU.calc_code_bleu import get_codebleu
from evaluator.bleu import _bleu, bleu_from_list

class CodeDataset(Dataset):
    def __init__(self, data, tokenizer, max_length=512):
        self.data = data
        self.tokenizer = tokenizer
        self.max_length = max_length
        self.inputs = []
        self.outputs = []
        for example in self.data:
            code = example['code']
            description = example['description']
            input = tokenizer.encode(description, return_tensors="pt", max_length=self.max_length, truncation=True, padding='max_length')[0]
            output = tokenizer.encode(code, return_tensors="pt", max_length=self.max_length, truncation=True, padding='max_length')[0]
            self.inputs.append(input)
            self.outputs.append(output)

            
    def __len__(self):
        return len(self.data)

    def __getitem__(self, idx):
        # 获取代码和描
        return {
            'input': self.inputs[idx],
            'output': self.outputs[idx]
        }
    
# 加载 CodeT5 模型和 Tokenizer
model_name = "/data_ssd/zz/dslcoq/LLM/models/codet5-small"
model = T5ForConditionalGeneration.from_pretrained(model_name)
tokenizer = RobertaTokenizer.from_pretrained(model_name)

# 加载数据集
with open("/data_ssd/zz/dslcoq/LLM/data/mbdslp.jsonl", "r") as f:
    lines = f.readlines()
    mbdslp = [json.loads(line) for line in lines]

train_data = []
valid_data = []
test_data = []
# 601-- train
# 11-510 test
# 511-600 valid
for data in mbdslp:
    task_id = int(data['task_id'].split('/')[1])
    if task_id > 600:
        train_data.append(data)
    elif task_id <= 510:
        test_data.append(data)
    else:
        valid_data.append(data)

train_dataset = CodeDataset(train_data, tokenizer)
valid_dataset = CodeDataset(valid_data, tokenizer)
test_dataset = CodeDataset(test_data, tokenizer)
codebleu_validbase = [data['code'] for data in valid_data]
codebleu_testbase = [data['code'] for data in test_data]

def train_epoch(model, train_dataset, optimizer):
    model.train()
    total_loss = 0
    train_loader = DataLoader(train_dataset, batch_size=16, shuffle=True)
    for batch in tqdm(train_loader):
        optimizer.zero_grad()
        input_ids = batch['input'].to("cuda:3")
        target_ids = batch['output'].to("cuda:3")
        input_mask = input_ids.ne(0)
        target_mask = target_ids.ne(0)

        outputs = model(input_ids, attention_mask=input_mask, labels=target_ids, decoder_attention_mask=target_mask)
        loss = outputs.loss
        loss.backward()
        optimizer.step()
        total_loss += loss.item()
    return total_loss / len(train_loader)

def eval_epoch(model, eval_dataset):
    model.eval()
    eval_sampler = SequentialSampler(eval_dataset)
    eval_loader = DataLoader(eval_dataset, sampler = eval_sampler, batch_size=90)
    predictions = []
    for batch in tqdm(eval_loader):
        input_ids = batch['input'].to("cuda:3")
        input_mask = input_ids.ne(0)

        with torch.no_grad():
            preds = model.generate(input_ids, attention_mask=input_mask, max_length=512, num_beams=1, early_stopping=False)
        predictions.extend(list(preds.cpu().numpy()))

    pred_texts = tokenizer.batch_decode(predictions, skip_special_tokens=True)

    codebleu = get_codebleu([ref.strip() for ref in codebleu_validbase], [pred.strip() for pred in pred_texts], 'java')
    bleu = bleu_from_list([ref.strip() for ref in codebleu_validbase], [pred.strip() for pred in pred_texts]) / 100

    em = 0
    for pred, ref in zip(pred_texts, codebleu_validbase):
        if pred.strip() == ref.strip():
            em += 1
    print("Exact Match", em)
    em = em / len(pred_texts)

    return codebleu, bleu, em, pred_texts

def test_epoch(model, eval_dataset):
    model.eval()
    test_sampler = SequentialSampler(test_dataset)
    test_loader = DataLoader(test_dataset, sampler = test_sampler, batch_size=75)
    predictions = []
    for batch in tqdm(test_loader):
        input_ids = batch['input'].to("cuda:3")
        input_mask = input_ids.ne(0)

        with torch.no_grad():
            preds = model.generate(input_ids, attention_mask=input_mask, max_length=512, num_beams=1, early_stopping=False)
        predictions.extend(list(preds.cpu().numpy()))

    pred_texts = tokenizer.batch_decode(predictions, skip_special_tokens=True)

    codebleu = get_codebleu([ref.strip() for ref in codebleu_testbase], [pred.strip() for pred in pred_texts], 'java')
    bleu = bleu_from_list([ref.strip() for ref in codebleu_testbase], [pred.strip() for pred in pred_texts]) / 100

    em = 0
    for pred, ref in zip(pred_texts, codebleu_testbase):
        if pred.strip() == ref.strip():
            em += 1
    em = round(em / len(pred_texts), 2)
    return codebleu, bleu, em, pred_texts


model = model.to("cuda:3")

optimizer = torch.optim.AdamW(model.parameters(), lr=5e-5)

highest_score = 0
patient = 0
for epoch in range(1000):
    train_loss = train_epoch(model, train_dataset, optimizer)
    print(f"Epoch {epoch} Train Loss: {train_loss}")
    if epoch % 20 == 0 and epoch > 0:
        codebleu, bleu, em, pred_text = eval_epoch(model, valid_dataset)
        print(f"Valid CodeBLEU: {codebleu}, BLEU: {bleu}, EM: {em}")
        score = codebleu + bleu + em
        if score > highest_score:
            highest_score = score
            model.save_pretrained(f"/data_ssd/zz/dslcoq/LLM/outputs/dslcoq_codet5_small_origin")
            with open(f"/data_ssd/zz/dslcoq/LLM/outputs/dslcoq_codet5_small_origin/pred_text.json", "w") as f:
                json.dump(pred_text, f)
            print(f"Highest Score: {highest_score}")
            patient = 0
        else:
            patient += 1
            if patient > 5:
                break     

test_codebleu, test_bleu, test_em, test_pred_text = test_epoch(model, test_dataset)
print(f"Test CodeBLEU: {test_codebleu}, BLEU: {test_bleu}, EM: {test_em}")
with open(f"/data_ssd/zz/dslcoq/LLM/outputs/dslcoq_codet5_small_origin/test_pred_text.json", "w") as f:
    json.dump(test_pred_text, f)