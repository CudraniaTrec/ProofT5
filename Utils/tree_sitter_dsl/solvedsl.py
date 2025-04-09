import pickle, json, os
from tqdm import tqdm
from tree_sitter import Language, Parser
from transformers import AutoTokenizer
from stringfy import Node, parseTree, postfix, lit_postfix, strfy

path = os.path.split(os.path.realpath(__file__))[0]
DSL_LANGUAGE = Language(path + "/parser.so", "dsl")
parser = Parser()
parser.set_language(DSL_LANGUAGE)

tokenizer = AutoTokenizer.from_pretrained("Salesforce/codet5-small", local_files_only=True)
rules = pickle.load(open(path+"/../data/grammart5rules.pkl", "rb"))
for rule in [f"string_literal{postfix} -> End", f"string_literal{postfix} -> End", "start -> dsl"]:
    if rule not in rules:
        rules[rule] = len(rules)
print(f"Rule size: {len(rules)}")

rulelist = []   # for each node, the rule id
fatherlist = [] # for each node, the father node id
endlist = []    # for each node, the end node(of the corresponding tree) id

# transform tree-sitter tree `root` into a new tree `newroot` 
def revisitTree(root, newroot, code, cursor):
    newroot.name = root.type
    children = []

    haschild = cursor.goto_first_child()
    for x in root.children:
        tmp = Node("init")
        children.append(tmp)
        tmp.father = newroot
        revisitTree(x, tmp, code, cursor)
        cursor.goto_next_sibling()
    newroot.child = children

    if haschild:
        cursor.goto_parent()
    else: # if the node is a leaf node
        ans = code[cursor.node.start_byte : cursor.node.end_byte]
        if ans != newroot.name: #identifier/literal
            newnode = Node(ans)
            newnode.father = newroot
            newroot.child = [newnode]

# add postfix to the each node name
def modifyTree(root):
    def addpost(root):
        if len(root.child) == 0:
            root.name += lit_postfix
            return
        else:
            root.name += postfix
            for x in root.child:
                addpost(x)
        return
    addpost(root)

# for each data in datas, parse the code into a tree (check if it is valid)
def parserTree(datas):
    data = []
    for i in tqdm(range(len(datas))):
        code = datas[i]["function"]
        root_node = parser.parse(bytes(code, 'utf-8')).root_node
        cursor = root_node.walk()
        sroot = Node("init")
        revisitTree(root_node, sroot, code, cursor)
        modifyTree(sroot)

        ans = datas[i]["nl"]
        data.append(
            {
                "input": ans,
                "root": sroot.getTreestr(),
                "code": datas[i]["function"],
                "id": datas[i]["id"],
            }
        )
    return data

# generate all rules in this node
def getRule(node, currId):
    global rules
    global rulelist
    global fatherlist
    global endlist

    # if the node is a leaf node
    if len(node.child) == 0:
        return [], []
    
    child = node.child
    if (
        len(node.child) == 1
        and len(node.child[0].child) == 0
        and ("identifier" in node.name or "literal" in node.name)
    ):  # if the node is nearly a leaf node (literal or identifier)
        actions = tokenizer.convert_tokens_to_ids(
            tokenizer.tokenize(" "+node.child[0].name[:-4])
        )
        if node.name == "string_literal" + postfix:
            rule = f"string_literal{postfix} -> End"
            actions = [rules[rule]] + actions

        actions.reverse()
        for action in actions:
            rulelist.append(action)
            fatherlist.append(currId)
            endlist.append(len(rulelist) - 1)
        currid = len(rulelist) - 1
    else:
        rule = node.name + " -> "
        for x in child:
            rule += x.name + " "
        if rule not in rules:
            print(f"Adding new rule: {rule}")
            rules[rule] = len(rules)
        rulelist.append(rules[rule])
        fatherlist.append(currId)
        endlist.append(-1)
        currid = len(rulelist) - 1
        for x in child:
            getRule(x, currid)
        endlist[currid] = len(rulelist) - 1

# generate the sequentialized data
def processaction(data, newrules=None):
    global rules, rulelist, fatherlist, endlist
    if newrules is not None:
        rules = newrules

    pdata = []
    for entry in tqdm(data):
        tree = entry["root"]
        nl   = entry["input"]

        root = parseTree(tree)
        nroot = Node("dsl")
        nroot.child = [root]
        root.father = nroot

        rulelist, fatherlist, endlist = [], [], []
        getRule(nroot, -1)
        clsid = tokenizer.cls_token_id
        sepid = tokenizer.sep_token_id
        rulelist = [clsid, rules["start -> dsl"]] + rulelist + [sepid]

        fatherlist = [0, 1] + [x + 2 for x in fatherlist]+ [len(rulelist) - 1]
        endlist = [0, 1] + [x + 2 for x in endlist] + [len(rulelist) - 1]
        pdata.append({
                "nl": tokenizer.encode(nl),
                "rulelist": rulelist,
                'id': entry['id'],
                })
    return pdata, rules

#convert dataset in json format into [Tree]
def process_data(dataset_name, dataset_type):
    # ./data/mbjp/
    dump_path = f'{path}/../data/{dataset_name}/'
    dataset_load_path = f'{dump_path}/{dataset_name}_{dataset_type}.pkl'
    dataset = pickle.load(open(dataset_load_path, 'rb'))

    datas = []
    for entry in dataset:
        if entry['java_code'] == None or entry['description'] == None:
            continue
        datas.append({'nl':entry['description'], 'function':entry["java_code"], 'id':entry['num']})

    json.dump(datas, open(f'{dump_path}/{dataset_type}.json', 'w'))
    print(f'Processing {dataset_name} {dataset_type} dataset, total {len(datas)} entries')
    pdata = parserTree(datas)

    # dump standard code for validation during finetuning
    if dataset_type == 'valid':
        # data/mbjp/groundvalid.txt
        with open(f'{dump_path}/groundvalid.txt', 'w') as f:
            for i in range(len(pdata)):
                tmpstr = strfy(pdata[i]['root'])
                tmpstr = tmpstr.replace('\n', ' ').replace('\t', ' ')
                f.write(tmpstr  + '\n')
    return pdata


if __name__ == "__main__":
    dataset_name = "mbjp_dsl"
    train_data = process_data(dataset_name, 'train')
    valid_data = process_data(dataset_name, 'valid')
    test_data  = process_data(dataset_name, 'test')

    print("="*25 + "Post Processing(Sequentialization)" + "="*25)
    ptraindata, rules = processaction(train_data)
    pvaliddata, rules = processaction(valid_data, rules)
    ptestdata , rules = processaction(test_data, rules)
    
    path = f'{path}/../data/{dataset_name}/'
    pickle.dump(ptraindata, open(f'{path}/train.pkl', 'wb'))
    pickle.dump(pvaliddata, open(f'{path}/valid.pkl', 'wb'))
    pickle.dump(ptestdata, open(f'{path}/test.pkl', 'wb'))
    pickle.dump(rules, open(f'{path}/rules.pkl', 'wb'))

    print(f"Train len: {len(ptraindata)} Valid len: {len(pvaliddata)} Test len: {len(ptestdata)} ")
    print(f"Rules size: {len(rules)}")