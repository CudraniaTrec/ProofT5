import torch, json, datetime, swanlab, os
from transformers import RobertaTokenizer, T5ForConditionalGeneration
from torch.utils.data import Dataset, DataLoader, SequentialSampler
from tqdm import tqdm

class CodeDataset(Dataset):
    def __init__(self, data, tokenizer, max_length=512):
        self.data = data
        self.tokenizer = tokenizer
        self.max_length = max_length
        self.inputs = []
        self.outputs = []
        for example in self.data:
            code = example['code'] if 'code' in example else example['canonical_solution']
            description = example['prompt']
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

# 加载 T5 模型和 Tokenizer
humaneval_path = "data/humaneval_t5.json"
mbjp_path = "data/mbjp_t5.json"
sufu_path = "data/sufu_t5.json"

def dump_data(model_name, dataset_name, cuda_num=-1):
    model_full_name = f"Salesforce/{model_name}"
    time = "2025-07-02_15-48-24"
    epoch = "50"
    model_path = f"models/{model_name}_{dataset_name}/{time}/epoch_{epoch}/" if time else f"models/{model_name}_{dataset_name}/"
    print(f"Loading model {model_full_name} from {model_path}")
    model = T5ForConditionalGeneration.from_pretrained(model_path)
    tokenizer = RobertaTokenizer.from_pretrained(model_full_name, local_files_only=True)
    if dataset_name == "humaneval":
        data_path = humaneval_path 
    elif dataset_name == "mbjp":
        data_path = mbjp_path
    elif dataset_name == "sufu":
        data_path = sufu_path
    else:
        raise ValueError("Unsupported dataset name. Choose from 'humaneval', 'mbjp', or 'sufu'.")
    with open(data_path, "r") as f:
        datas = json.load(f)

    test_data = [data for data in datas if data['type'] == 'test']
    test_dataset = CodeDataset(test_data, tokenizer)

    device = "cuda" if cuda_num == -1 else f"cuda:{cuda_num}"
    def test_epoch(model, eval_dataset, topk=10):
        model.eval()
        test_sampler = SequentialSampler(eval_dataset)
        test_loader = DataLoader(eval_dataset, sampler = test_sampler, batch_size=5)
        predictions = []
        for idx, batch in enumerate(test_loader):
            print(f"Processing batch {idx} with {len(batch['input'])} examples.")
            input_ids = batch['input'].to(device=device)
            # print("="*50)
            # print(tokenizer.decode(input_ids[0], skip_special_tokens=True))
            input_mask = input_ids.ne(0)
            with torch.no_grad():
                preds = model.generate(
                    input_ids, 
                    attention_mask=input_mask, 
                    max_length=512, 
                    num_beams=topk, 
                    num_return_sequences=topk)
            # print(tokenizer.decode(preds[0], skip_special_tokens=True))
            predictions.extend(list(preds.cpu().numpy()))

        pred_texts = tokenizer.batch_decode(predictions, skip_special_tokens=True)
        return pred_texts

    model = model.to(device=device)
    topk = 100
    test_pred = test_epoch(model, test_dataset, topk=topk)
    print(f"Test predictions generated for {len(test_pred)} examples.")
    output_dir = f"../Utils/output/{model_name}_{dataset_name}_test_ans/{time}/{epoch}x/" if time else f"../Utils/output/{model_name}_{dataset_name}_test_ans/"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    for num in range(len(test_data)):
        for i in range(topk):
            with open(f"{output_dir}{num}_{i}.txt", "w") as f:
                f.write(test_pred[num * topk + i])
    print(f"Test predictions saved to {output_dir}")
    test_data_path = f"../Utils/data/{model_name}_{dataset_name}"
    if not os.path.exists(test_data_path):
        os.makedirs(test_data_path)
    test_data_path+="/test.pkl"
    with open(test_data_path, "wb") as f:
        import pickle
        pickle.dump(test_data, f)

def main():
    tasks = [
        ("codet5-base", "mbjp", 6),
        # ("codet5p-220m", "mbjp", 7),
        # ("codet5-base", "humaneval", 2),
        # ("codet5p-220m", "humaneval", 3),
        # ("codet5-base", "sufu", 4),
        # ("codet5p-220m", "sufu", 5),
    ]
    tasks2 = [
        ("codet5-base", "humaneval", 6),
        ("codet5p-220m", "humaneval", 7),
    ]
    tasks3 = [
        ("codet5-base", "sufu", 6),
        ("codet5p-220m", "sufu", 7),
    ]
    import multiprocessing as mp
    with mp.Pool(processes=len(tasks)+1) as pool:
        pool.starmap(dump_data, tasks)
    # with mp.Pool(processes=len(tasks2)+1) as pool:
    #     pool.starmap(dump_data, tasks2)
    # with mp.Pool(processes=len(tasks3)+1) as pool:
    #     pool.starmap(dump_data, tasks3)

#test one problem in mbjp
def test():
    model_name = "codet5-base"
    dataset_name = "mbjp"
    model_full_name = f"Salesforce/{model_name}"
    model_path = "/data4/hzc/ProofT5/t5_llm/models/codet5-base_mbjp/2025-06-15_10-27-59/epoch_200"
    print(f"Loading model {model_full_name} from {model_path}")
    model = T5ForConditionalGeneration.from_pretrained(model_path)
    tokenizer = RobertaTokenizer.from_pretrained(model_full_name, local_files_only=True)
    prompt = """/**
* Write a Java function to find the first odd number in a given list of integers.
*
* public static int firstOdd(List<Integer> numbers)
* 
* Examples:
* > firstOdd(Arrays.asList(3, 5))
* 3
* 
* > firstOdd(Arrays.asList(2, 4, 1, 3))
* 1
*/"""
    input_ids = tokenizer.encode(prompt, return_tensors="pt")
    input_ids = input_ids.to("cuda")
    model = model.to("cuda")
    with torch.no_grad():
        outputs = model.generate(input_ids, max_length=512, num_beams=10, num_return_sequences=10)
    pred_texts = tokenizer.batch_decode(outputs, skip_special_tokens=True)
    for i, text in enumerate(pred_texts):
        print(f"Prediction {i+1}: {text}")


if __name__ == "__main__":
    main()