import re, json, pickle
from tqdm import tqdm
from java2impp import javalang, visit, tokenizer
import matplotlib.pyplot as plt

def extract_java_code_from_dicts(dict_list):
    # Define a placeholder for java code
    placeholder = "<JAVA_CODE>"
    # Regular expression to match java code blocks
    java_code_pattern = re.compile(r"```java\n.*?```", re.DOTALL)
    nl_length_cnt, java_length_cnt = {}, {}

    for item in tqdm(dict_list):
        if 'output' in item:
            # Extract java code from the output field
            java_code_matches = java_code_pattern.findall(item['output'])
            
            # Remove the enclosing ```java and ``` from the matches
            java_code_matches = [code[8:-3].strip() for code in java_code_matches]

            # Save the extracted java code to the new field
            item['java_list'] = java_code_matches

            # Replace the java code in the output field with the placeholder
            item['output'] = java_code_pattern.sub(placeholder, item['output'])
            item['text'] = item['instruction'] + '\n\n' + item['output']
            for l in [len(code) for code in java_code_matches]:
                if l not in java_length_cnt:
                    java_length_cnt[l] = 0
                java_length_cnt[l] += 1
            if len(item["instruction"]) not in nl_length_cnt:
                nl_length_cnt[len(item["instruction"])] = 0
            nl_length_cnt[len(item["instruction"])] += 1
    plt.figure(figsize=(10, 5))
    plt.bar(nl_length_cnt.keys(), nl_length_cnt.values(), width=1.0, color='blue', alpha=0.7)
    plt.xlabel('NL Length')
    plt.ylabel('Frequency')
    plt.title('NL Length Distribution')
    plt.savefig('nl_length_distribution.png')
    plt.figure(figsize=(10, 5))
    plt.bar(java_length_cnt.keys(), java_length_cnt.values(), width=1.0, color='green', alpha=0.7)
    plt.xlabel('Java Code Length')
    plt.ylabel('Frequency')
    plt.title('Java Code Length Distribution')
    plt.savefig('java_length_distribution.png')
    return dict_list

newdatas = []
placeholder = "<JAVA_CODE>"
dataset0="instruct_java.jsonl" #78w
dataset1="hemp_java_shuffle.json" #1w
dataset2="opencoder-sft-java.json" #7w
with open(f"datas/{dataset2}", 'r') as f:
    data = json.load(f)
    data = extract_java_code_from_dicts(data)
nl_lens, token_lens = [], []
for i in tqdm(range(len(data))):
    try:
        newdata = {}
        newdata['text'] = data[i]['instruction']
        newdata["nl"] = tokenizer.encode(data[i]['instruction'])
        assert len(data[i]['java_list']) == 1
        javacode = data[i]['java_list'][0]
        assert len(javacode)<= 3000
        assert len(newdata["nl"]) <= 2000
        javacode = javacode.replace("public static void", "public static int")
        newdata['javacode']=javacode
        tree = javalang.parse.parse(javacode)
        program = visit(tree)
        tokens = program.to_coq().tokenization()
        newdata['tokens'] = tokens
        newdata["rulelist"] = [1] + tokenizer.convert_tokens_to_ids(tokens) + [2]
        assert len(tokens) <= 1000
        program.to_java()
        nl_lens.append(len(newdata["nl"]))
        token_lens.append(len(newdata["rulelist"]))
        newdatas.append(newdata)
    except Exception as e:
        error_message = str(e)
        # if error_message.strip():
        #     print(error_message)
        #     if "None" in error_message:
        #         print(javacode)
        #         break    
        continue

print(f"{len(newdatas)} samples are generated")
print(f"Example: {json.dumps(newdatas[0], ensure_ascii=False)}")
print(f"NL length: {min(nl_lens)} ~ {max(nl_lens)}, avg: {sum(nl_lens)/len(nl_lens)}")
print(f"Token length: {min(token_lens)} ~ {max(token_lens)}, avg: {sum(token_lens)/len(token_lens)}")
with open(f"../Utils/data/pretrain/train.json", 'w') as f:
    json.dump(newdatas, f, ensure_ascii=False)
with open(f"../Utils/data/pretrain/train.pkl", 'wb') as f:
    pickle.dump(newdatas, f)
rule_dict = tokenizer.get_vocab()
with open(f"../Utils/data/pretrain/rules.json", 'w') as f:
    json.dump(rule_dict, f, ensure_ascii=False)
with open(f"../Utils/data/pretrain/rules.pkl", 'wb') as f:
    pickle.dump(rule_dict, f)