from transformers import (
    AutoTokenizer,
    AutoModelForCausalLM,
    DataCollatorForLanguageModeling,
    TrainingArguments,
    Trainer,
    TrainerCallback,
)
from torch.utils.data import DataLoader
from torch.nn.utils.rnn import pad_sequence
from datasets import Dataset, DatasetDict
import os, pickle, datetime, swanlab, json, torch, time
from tqdm import trange
from evaluator.CodeBLEU.calc_code_bleu import get_codebleu
from math import ceil
date = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

def collate_fn(batch):
    input_ids_list = torch.tensor([item['input_ids'][:item['prompt_lens']] for item in batch])
    input_ids_padded = pad_sequence(input_ids_list, batch_first=True)
    return input_ids_padded

class CustomCallback(TrainerCallback):
    def __init__(self, tokenizer, test_dataset, save_dir_base="./results", output_dir_base="../Utils/output/Qwen2.5-0.5B_sufu_test_ans"):
        self.save_dir_base = save_dir_base
        self.tokenizer = tokenizer
        self.test_dataset = test_dataset
        self.numbeams = 10
        self.output_dir_base = output_dir_base

    def on_evaluate(self, args, state, control, **kwargs):
        model = kwargs.get("model")
        if model is None:
            return
        
        model.eval()
        results = []
        for idx in trange(len(self.test_dataset), leave=False, desc="Generating predictions"):
            item = self.test_dataset[idx]
            prompt_len = item['prompt_lens']
            input_ids = torch.tensor(item['input_ids'][:prompt_len]).unsqueeze(0).to(model.device)
            attention_mask = torch.ne(input_ids, self.tokenizer.pad_token_id).to(model.device)
            with torch.no_grad():
                outputs = model.generate(
                    input_ids=input_ids,
                    attention_mask=attention_mask,
                    do_sample=False,
                    num_beams=self.numbeams,
                    max_new_tokens=512,
                    pad_token_id=self.tokenizer.pad_token_id,
                    eos_token_id=self.tokenizer.eos_token_id,
                    num_return_sequences=self.numbeams,
                )
            generated_texts = [
                self.tokenizer.decode(output, skip_special_tokens=True)
                for output in outputs
            ]
            results.append(generated_texts)
        current_epoch = int(state.epoch)
        output_dir = os.path.join(self.output_dir_base, str(current_epoch))
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        for num in range(len(results)):
            for i in range(self.numbeams):
                with open(f"{output_dir}/{num}_{i}.txt", "w") as f:
                    f.write(results[num][i])
        print(f"Test predictions saved to {output_dir}")
        model.train()

def train_model(
    model_name: str = "Qwen2.5-0.5B",
    dataset_name: str = "sufu",
    gpu_num: int = -1,
    # 训练参数
    max_length: int = 512,
    num_epochs: int = 300,
    per_device_train_batch_size: int = 15,
    learning_rate: float = 1e-3,
    weight_decay: float = 1e-4,
):
    # 加载 tokenizer 和模型
    device = "cuda" #if gpu_num == -1 else f"cuda:{gpu_num}"
    print(f"Using device: {device}")
    tokenizer = AutoTokenizer.from_pretrained(model_name, padding_side='left')
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    model = AutoModelForCausalLM.from_pretrained(model_name).to(device)

    model_name = model_name.split("/")[-1]
    task_name = f"{model_name}_{dataset_name}" #Qwen2.5-0.5B_sufu
    output_dir = f"./models/{task_name}/{date}"
    data_path = f"./data/{dataset_name}_t5.json"
    

    # 加载数据集
    datas = json.load(open(data_path, "r"))
    train_data = Dataset.from_list([data for data in datas if data['type'] == 'train'])
    valid_data = Dataset.from_list([data for data in datas if data['type'] == 'valid'])
    test_data = Dataset.from_list([data for data in datas if data['type'] == 'test'])
    dataset = DatasetDict({
        "train": train_data,
        "validation": valid_data,
        "test": test_data,
    })
    # 预处理函数：拼接 description + code，并构造 labels
    def preprocess_function(examples):
        texts = [f"{desc}\n{code}" for desc, code in zip(examples["prompt"], examples["postfix"])]
        encodings = tokenizer(texts, 
                              truncation=True, 
                              padding="max_length", 
                              max_length=max_length, 
                              return_tensors="pt",
                              return_special_tokens_mask=True)
        # 构造 labels：将 prompt 部分设为 -100，只计算 target 部分的 loss
        labels = []
        prompt_lens = []
        for i in range(len(texts)):
            text = texts[i]
            prompt = examples["prompt"][i]
            prompt_len = len(tokenizer(text[:len(prompt)], add_special_tokens=False).input_ids)
            prompt_lens.append(prompt_len)
            input_ids = encodings.input_ids[i]
            # 将 prompt 部分的 token 设置为 -100
            label = torch.where(
                torch.arange(input_ids.shape[-1]) >= prompt_len,
                input_ids,
                torch.tensor(-100)
            )
            labels.append(label)
        
        encodings["labels"] = labels
        encodings["prompt_lens"] = prompt_lens
        return encodings

    # 对 dataset 进行 map 处理
    encoded_dataset = dataset.map(preprocess_function, batched=True)
    # 数据 collator（自动处理 pad token 的 loss 忽略）
    data_collator = DataCollatorForLanguageModeling(
        tokenizer=tokenizer,
        mlm=False,  # 因为是 causal LM，不需要 MLM
    )
    
    # 保存数据集
    save_data_path = f"../Utils/data/{task_name}"
    if not os.path.exists(save_data_path):
        os.makedirs(save_data_path)
    with open(f"{save_data_path}/train.pkl", "wb") as f:
        pickle.dump(encoded_dataset["train"], f)
    with open(f"{save_data_path}/valid.pkl", "wb") as f:
        pickle.dump(encoded_dataset["validation"], f)
    with open(f"{save_data_path}/test.pkl", "wb") as f:
        pickle.dump(encoded_dataset["test"], f)
    
    # 设置训练参数
    steps_per_epoch = ceil(len(encoded_dataset["train"]) / per_device_train_batch_size)
    print(f"Steps per epoch: {steps_per_epoch}")
    training_args = TrainingArguments(
        output_dir=output_dir,
        overwrite_output_dir=True,
        learning_rate=learning_rate,
        weight_decay=weight_decay,
        num_train_epochs=num_epochs,
        per_device_train_batch_size=per_device_train_batch_size,
        per_device_eval_batch_size=per_device_train_batch_size,
        logging_dir=f"{output_dir}/logs",
        logging_strategy="epoch",
        save_strategy="steps", 
        save_steps= steps_per_epoch * 20,
        evaluation_strategy="steps", 
        eval_steps= steps_per_epoch * 20,
        warmup_steps=steps_per_epoch * 100,
        report_to="tensorboard",
        run_name=f"{task_name}_{date}",
        fp16=True
    )

    # 初始化 Trainer
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=encoded_dataset["train"],
        eval_dataset=encoded_dataset["test"],
        data_collator=data_collator,
        tokenizer=tokenizer,
        callbacks=[CustomCallback(tokenizer = tokenizer, 
                                  test_dataset=encoded_dataset["test"],
                                  save_dir_base=output_dir,
                                  output_dir_base=f"../Utils/output/{task_name}_test_ans/{date}")],
    )

    trainer.train()
    # 保存模型
    trainer.save_model(output_dir)
    tokenizer.save_pretrained(output_dir)
    print(f"Model saved to {output_dir}")
    return

if __name__ == "__main__":
    train_model(
        model_name="Qwen/Qwen2.5-0.5B",
        dataset_name="sufu",
        gpu_num=7,
    )