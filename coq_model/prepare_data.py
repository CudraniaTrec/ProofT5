import json, os, pickle
from tqdm import tqdm
from program_model import tokenizer, rule_dict, detokenization, extract_context
from java2impp import visit, javalang
mbjp_data = json.load(open("datas/mbjp.json"))

# 1. catogorize the problems into train, valid, test
def mbjp_problem_type_standard(num):
    if num <= 10: # prompt
        return "train"
    elif num <= 510: # test
        return "test"
    elif num <= 600: # valid
        return "valid"
    else: # train
        return "train"

valid_problem_num_list = []
for problem in mbjp_data:
    problem_num = int(problem["task_id"].split("/")[1])
    file_path = f"datas/mbjp/MBJP_{problem_num}.pkl"
    if os.path.exists(file_path):
        valid_problem_num_list.append(problem_num)
valid_problem_num_list.sort()
# split with 8:1:1
train_num = int(len(valid_problem_num_list) * 0.8)  
test_num = int(len(valid_problem_num_list) * 0.9)
def mbjp_problem_type(num):
    if num <= valid_problem_num_list[train_num]:
        return 'train'
    elif num <= valid_problem_num_list[test_num]:
        return 'test'
    else:
        return 'valid'
    
# 2. split the prompt and code
def split_prompt_code(file_path):
    with open(file_path, "r") as f:
        java_code = f.read()
    code = [line.strip() for line in java_code.split("\n") if line.strip()]
    annotation_start = 0
    annotation_end = 0
    class_start = 0
    for i, line in enumerate(code):
        if line.startswith("/**"):
            annotation_start = i
        if line.endswith("*/"):
            annotation_end = i
        if line.startswith("class"):
            class_start = i
    assert annotation_start < annotation_end, f"Annotation start: {annotation_start} Annotation end: {annotation_end}"
    assert annotation_start-1 == class_start, f"Annotation start: {annotation_start} Class start: {class_start}"
    nl = code[class_start:annotation_start] + code[annotation_start + 1:annotation_end]
    nl = [line.strip() for line in nl if line.strip()]
    code = code[class_start:annotation_start] + code[annotation_end+1:]
    return "\n".join(nl), "\n".join(code)

# 3. save the tokenizer and rules
print(f"Rule size: {len(rule_dict)}")
rrule_dict = {v: k for k, v in rule_dict.items()}
for dir in ["../Utils/data/mbjpcoq", "../Utils/data/mbjpcoqview", "../Utils/data/mbjpcoqview2"]:
    pickle.dump(tokenizer, open(f"{dir}/coq_tokenizer.pkl", "wb"))
    json.dump(rule_dict, open(f"{dir}/rules.json", "w"))
    pickle.dump(rule_dict, open(f"{dir}/rules.pkl", "wb"))

# 4. generate data
train_set, valid_set, test_set = [], [], []
train_set_mbjp, valid_set_mbjp, test_set_mbjp = [], [], []
train_set_coqview, valid_set_coqview, test_set_coqview = [], [], []
train_set_dsl, valid_set_dsl, test_set_dsl = [], [], []
max_coqview_len , coqview_len_list = 0, []
max_nl_len , nl_len_list = 0, []
max_code_len , code_len_list = 0, []

for problem in tqdm(mbjp_data):
    problem_num = int(problem["task_id"].split("/")[1])
    file_path = f"datas/mbjp/MBJP_{problem_num}.pkl"
    if os.path.exists(file_path):
        # prepare mbjpcoq data
        data = {}
        java_path = f"datas/mbjp/MBJP_{problem_num}.java"
        with open(java_path, "r") as f:
            java_code = f.read()
        tree = javalang.parse.parse(java_code)
        dsl_program = visit(tree).to_code()
        
        nl, code = split_prompt_code(java_path)
        data["nl"] = tokenizer.encode(nl)
        data["rulelist"] = [1]+pickle.load(open(file_path, "rb"))+[2] # <s> and </s>
        tokens = [rrule_dict[r] for r in data["rulelist"][1:-1]]
        data['java_code'] = detokenization(tokens).to_java().replace("\n", "")
        data['test'] = problem["test"]
        globals()[f"{mbjp_problem_type(problem_num)}_set"].append(data)
        max_nl_len = max(max_nl_len, len(data["nl"]))
        max_code_len = max(max_code_len, len(tokens))
        nl_len_list.append(len(data["nl"]))
        code_len_list.append(len(tokens))
        # prepare mbjp data
        data_mbjp = {}
        data_mbjp["description"] = nl
        data_mbjp["java_code"] = code
        data_mbjp["test"] = problem["test"]
        globals()[f"{mbjp_problem_type(problem_num)}_set_mbjp"].append(data_mbjp)
        # prepare dsl data
        data_dsl = {}
        data_dsl["description"] = nl
        data_dsl["java_code"] = dsl_program
        data_dsl["test"] = problem["test"]
        data_dsl['num'] = problem_num
        globals()[f"{mbjp_problem_type(problem_num)}_set_dsl"].append(data_dsl)
        # prepare mbjpcoqview data
        coqview_path = f"datas/mbjp_coqview/{problem_num}"
        coqview_data = []
        coqview_data_raw = ""
        for step in range(len(tokens)-1):
            step_file = f"{coqview_path}/step{step+1}.txt"
            with open(step_file, "r") as f:
                coq_view = f.read()
            context = extract_context(coq_view)
            encoded_context = tokenizer.encode(context)[1:-1]
            max_coqview_len = max(max_coqview_len, len(encoded_context))
            coqview_len_list.append(len(encoded_context))
            coqview_data_raw+=context
            coqview_data.append(encoded_context)
        data["coqview"] = coqview_data
        data["coqview_raw"] = coqview_data_raw
        globals()[f"{mbjp_problem_type(problem_num)}_set_coqview"].append(data)
print(f"Train set: {len(train_set)} Valid set: {len(valid_set)} Test set: {len(test_set)}")

# 5. save the data
print(f"Max coqview len: {max_coqview_len} Max nl len: {max_nl_len} Max code len: {max_code_len}")
print(f"Average coqview len: {sum(coqview_len_list)/len(coqview_len_list)}")
print(f"Average nl len: {sum(nl_len_list)/len(nl_len_list)}")
print(f"Average code len: {sum(code_len_list)/len(code_len_list)}")
# save groundvalid data
groundvalid = "\n".join([item['java_code'] for item in valid_set])
for task in ["mbjpcoq", "mbjpcoqview", "mbjpcoqview2"]:
    with open(f"../Utils/data/{task}/groundvalid.txt", "w") as f:
        f.write(groundvalid)
# save config
for task in ["mbjpcoqview", "mbjpcoqview2"]:
    with open(f"../Utils/data/{task}/config.json", "r") as f:
        config = json.load(f)
    config["max_coqview_len"] = max_coqview_len
    config["max_nl_len"] = max_nl_len
    config["max_code_len"] = max_code_len
    with open(f"../Utils/data/{task}/config.json", "w") as f:
        json.dump(config, f, indent=2)
# save dsldata
for data_type in ["train", "valid", "test"]:
    pickle.dump(globals()[f"{data_type}_set_dsl"], open(f"../Utils/data/mbjp_dsl/mbjp_dsl_{data_type}.pkl", "wb"))
    json.dump(globals()[f"{data_type}_set_dsl"], open(f"../Utils/data/mbjp_dsl/mbjp_dsl_{data_type}.json", "w"))
    for data in globals()[f"{data_type}_set_dsl"]:
        num = data['num']
        code = data['java_code']
        with open(f"../Utils/data/mbjp_dsl/programs/{num}.txt", "w") as f:
            f.write(code)
groundvalid_dsl = "\n".join([item['java_code'].replace("\n", "") for item in valid_set_dsl])
with open(f"../Utils/data/mbjp_dsl/groundvalid.txt", "w") as f:
    f.write(groundvalid_dsl)
# save data
for data_type in ["train", "valid", "test"]:
    pickle.dump(globals()[f"{data_type}_set_mbjp"], open(f"../Utils/data/mbjp/mbjp_{data_type}.pkl", "wb"))
    pickle.dump(globals()[f"{data_type}_set_mbjp"], open(f"../Utils/data/mbjp_blind/mbjp_blind_{data_type}.pkl", "wb"))
    for task in ["mbjpcoqview", "mbjpcoqview2"]:
        json.dump(globals()[f"{data_type}_set_coqview"], open(f"../Utils/data/{task}/{data_type}.json", "w"))
        pickle.dump(globals()[f"{data_type}_set_coqview"], open(f"../Utils/data/{task}/{data_type}.pkl", "wb"))
    json.dump(globals()[f"{data_type}_set"], open(f"../Utils/data/mbjpcoq/{data_type}.json", "w"))
    pickle.dump(globals()[f"{data_type}_set"], open(f"../Utils/data/mbjpcoq/{data_type}.pkl", "wb"))
