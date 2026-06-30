import json, os, pickle, copy
from tqdm import tqdm
from program_model import tokenizer, rule_dict, detokenization, extract_context

dataset = "mbjp"  # "mbjp" or "humaneval"
datas = json.load(open(f"datas/{dataset}.json"))
def taskid(num, slash=False):
    return f"{'MBJP' if dataset == 'mbjp' else 'Java'}{'/' if slash else '_'}{num}"

# 1. catogorize the problems into train, valid, test
valid_problem_num_list = []
for problem in datas:
    problem_num = int(problem["task_id"].split("/")[1])
    file_path = f"datas/{dataset}/{taskid(problem_num)}.pkl"
    if os.path.exists(file_path):
        valid_problem_num_list.append(problem_num)
valid_problem_num_list.sort()
# split with 8:1:1
train_num = int(len(valid_problem_num_list) * 0.8)  
test_num = int(len(valid_problem_num_list) * 0.9)
def problem_type(num):
    if num <= valid_problem_num_list[train_num]:
        return 'train'
    elif num <= valid_problem_num_list[test_num]:
        return 'test'
    else:
        return 'valid'

# 2. save the tokenizer and rules
print(f"Rule size: {len(rule_dict)}")
rrule_dict = {v: k for k, v in rule_dict.items()}
for task in ["mbjpcoq","mbjpcoqview","mbjpcoqview2"] if dataset == "mbjp" else ["humanevalcoq", "humanevalcoqview"]:
    dir = f"../Utils/data/{task}"
    pickle.dump(tokenizer, open(f"{dir}/coq_tokenizer.pkl", "wb"))
    json.dump(rule_dict, open(f"{dir}/rules.json", "w"))
    pickle.dump(rule_dict, open(f"{dir}/rules.pkl", "wb"))

# 3. generate data
train_set_coq, valid_set_coq, test_set_coq = [], [], [] # for coq
train_set_grammar, valid_set_grammar, test_set_grammar = [], [], [] # for grammar
train_set_coqview, valid_set_coqview, test_set_coqview = [], [], [] # for coqview
set_t5 = []
set_t5_proof = []
coqview_len_list = []
nl_len_list = []
code_len_list = []
code_token_len_list = []
for problem in tqdm(datas):
    problem_num = int(problem["task_id"].split("/")[1])
    file_path = f"datas/{dataset}/{taskid(problem_num)}.pkl"
    if os.path.exists(file_path):
        data = {}
        java_path = f"datas/{dataset}/{taskid(problem_num)}.java"
        with open(java_path, "r") as f:
            java_code = f.read()
            
        # prepare coq data
        nl = problem["prompt"]
        data["nl"] = tokenizer.encode(nl)
        rules = pickle.load(open(file_path, "rb"))
        data["rulelist"] = [1]+ rules +[2] # <s> and </s>
        tokens = [rrule_dict[r] for r in rules]
        code = detokenization(tokens).to_java()
        data['java_code'] = code
        code_token_len_list.append(len(tokenizer.tokenize(code)))
        data['test'] = problem["test"]
        globals()[f"{problem_type(problem_num)}_set_coq"].append(data)

        nl_len_list.append(len(data["nl"]))
        code_len_list.append(len(rules))

        # prepare grammar data
        data_grammar = {}
        data_grammar["description"] = nl
        data_grammar["java_code"] = code
        data_grammar["test"] = problem["test"]
        globals()[f"{problem_type(problem_num)}_set_grammar"].append(data_grammar)

        # prepare coqview data
        data_coqview = copy.copy(data)
        coqview_path = f"datas/{dataset}_coqview/{problem_num}"
        coqview_data = []
        coqview_data_raw = ""
        for step in range(len(rules)-1):
            step_file = f"{coqview_path}/step{step+1}.txt"
            with open(step_file, "r") as f:
                coq_view = f.read()
            context = extract_context(coq_view)
            encoded_context = tokenizer.encode(context)[1:-1]
            coqview_data_raw+=context
            coqview_data.append(encoded_context)
            coqview_len_list.append(len(encoded_context))
        data_coqview["coqview"] = coqview_data
        data_coqview["coqview_raw"] = coqview_data_raw
        globals()[f"{problem_type(problem_num)}_set_coqview"].append(data_coqview)

        #prepare t5 data
        t5data= copy.deepcopy(problem)
        t5data["type"] = problem_type(problem_num)
        set_t5.append(t5data)
        t5data_proof = copy.deepcopy(t5data)
        t5data_proof["proof"] = data["rulelist"][1:-1]
        set_t5_proof.append(t5data_proof)


print(f"Train set: {len(train_set_coq)} Valid set: {len(valid_set_coq)} Test set: {len(test_set_coq)}")
print(f"Max coqview len: {max(coqview_len_list)}, min coqview len: {min(coqview_len_list)}, avg coqview len: {sum(coqview_len_list)/len(coqview_len_list)}")
print(f"Max nl len: {max(nl_len_list)}, min nl len: {min(nl_len_list)}, avg nl len: {sum(nl_len_list)/len(nl_len_list)}")
print(f"Max code len: {max(code_len_list)}, min code len: {min(code_len_list)}, avg code len: {sum(code_len_list)/len(code_len_list)}")
print(f"Max code token len: {max(code_token_len_list)}, min code token len: {min(code_token_len_list)}, avg code token len: {sum(code_token_len_list)/len(code_token_len_list)}")

# 4. save the data
# save groundvalid data
groundvalid = "\n".join([item['java_code'] for item in valid_set_coq])
for task in ["mbjpcoq","mbjpcoqview","mbjpcoqview2"] if dataset == "mbjp" else ["humanevalcoq", "humanevalcoqview"]:
    with open(f"../Utils/data/{task}/groundvalid.txt", "w") as f:
        f.write(groundvalid)
# save config
for task in ["mbjpcoqview", "mbjpcoqview2", "humanevalcoqview"]:
    with open(f"../Utils/data/{task}/config.json", "r") as f:
        config = json.load(f)
    config["max_coqview_len"] = max(coqview_len_list)
    config["max_nl_len"] = max(nl_len_list)
    config["max_code_len"] = max(code_len_list)
    with open(f"../Utils/data/{task}/config.json", "w") as f:
        json.dump(config, f, indent=2)
# save data
with open(f"../t5_llm/data/{dataset}_t5.json", "w") as f:
    json.dump(set_t5, f, indent=2)
with open(f"../t5_llm/data/{dataset}_t5_codeproof.json", "w") as f:
    json.dump(set_t5_proof, f, indent=2)
# for data_type in ["train", "valid", "test"]:
#     pickle.dump(globals()[f"{data_type}_set_grammar"], open(f"../Utils/data/{dataset}/{dataset}_{data_type}.pkl", "wb"))
#     pickle.dump(globals()[f"{data_type}_set_grammar"], open(f"../Utils/data/{dataset}_blind/{dataset}_blind_{data_type}.pkl", "wb"))
#     json.dump(globals()[f"{data_type}_set_coq"], open(f"../Utils/data/{dataset}coq/{data_type}.json", "w"))
#     pickle.dump(globals()[f"{data_type}_set_coq"], open(f"../Utils/data/{dataset}coq/{data_type}.pkl", "wb"))
#     for task in ["mbjpcoqview", "mbjpcoqview2"] if dataset == "mbjp" else ["humanevalcoqview"]:
#         json.dump(globals()[f"{data_type}_set_coqview"], open(f"../Utils/data/{task}/{data_type}.json", "w"))
#         pickle.dump(globals()[f"{data_type}_set_coqview"], open(f"../Utils/data/{task}/{data_type}.pkl", "wb"))
    