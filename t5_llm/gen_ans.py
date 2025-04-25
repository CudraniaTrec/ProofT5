import torch
from transformers import RobertaTokenizer, T5ForConditionalGeneration
from torch.utils.data import Dataset, DataLoader, SequentialSampler
import json
from tqdm import tqdm

class CodeDataset(Dataset):
    def __init__(self, data, tokenizer, max_length=512):
        self.data = data
        self.tokenizer = tokenizer
        self.max_length = max_length
        self.inputs = []
        self.outputs = []
        for example in self.data:
            code = example['java_code']
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
model = T5ForConditionalGeneration.from_pretrained("/data_ssd/zz/dslcoq/LLM/outputs/dslcoq_codet5_small")
tokenizer = RobertaTokenizer.from_pretrained(model_name)

# 加载数据集
with open("/data_ssd/zz/dslcoq/LLM/data/mbdslp.jsonl", "r") as f:
    lines = f.readlines()
    mbdslp = [json.loads(line) for line in lines]

with open("data/mbjp_dsl_test.json", "r") as f:
    test_data = json.load(f)
with open("data/mbjp_dsl_valid.json", "r") as f:
    valid_data = json.load(f)
with open("data/mbjp_dsl_train.json", "r") as f:
    train_data = json.load(f)

train_dataset = CodeDataset(train_data, tokenizer)
valid_dataset = CodeDataset(valid_data, tokenizer)
test_dataset = CodeDataset(test_data, tokenizer)
codebleu_validbase = [data['java_code'] for data in valid_data]
codebleu_testbase = [data['java_code'] for data in test_data]

device = "cuda"
model.to(device)
def test_epoch(model, dataset, topk=1):
    model.eval()
    test_sampler = SequentialSampler(dataset)
    test_loader = DataLoader(dataset, sampler = test_sampler, batch_size=75)
    predictions = []
    for batch in tqdm(test_loader):
        input_ids = batch['input'].to(device)
        input_mask = input_ids.ne(0)

        with torch.no_grad():
            preds = model.generate(
                input_ids, 
                attention_mask=input_mask, 
                max_length=512, 
                num_beams=topk, 
                num_return_sequences=topk,
                early_stopping=False)
        predictions.extend(list(preds.cpu().numpy()))

    pred_texts = tokenizer.batch_decode(predictions, skip_special_tokens=True)
    return pred_texts

pred_texts = test_epoch(model, test_dataset, topk=10)
with open(f"/data_ssd/zz/dslcoq/LLM/outputs/dslcoq_codet5_small/test_pred_text_top10.json", "w") as f:
    json.dump(pred_texts, f)