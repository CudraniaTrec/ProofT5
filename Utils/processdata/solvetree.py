from tqdm import tqdm
import pickle, traceback
from transformers import AutoTokenizer
from .process_utils import Node, onelist, identifiers, postfix
from .stringfy import parseTree, stringfy

tokenizer = AutoTokenizer.from_pretrained("Salesforce/codet5-small", local_files_only=True)
import os
path = os.path.split(os.path.realpath(__file__))[0]
rules = pickle.load(open(path+"/../data/grammart5rules.pkl", "rb"))
rulelist = []   # for each node, the rule id
fatherlist = [] # for each node, the father node id
fathername = [] # for each node, the father node name
endlist = []    # for each node, the end node(of the corresponding tree) id

onelist = [x + postfix for x in onelist]
identifiers = [x + postfix for x in identifiers]

#get all unfolding rules in this node
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
            tokenizer.tokenize(" " + node.child[0].name[:-4])
        )
        if node.name == "string_literal"+postfix:
            actions = actions[:25]
            node.child[0].name = (
                "".join(tokenizer.convert_ids_to_tokens(actions))
                .replace("Ġ", " ")
                .strip()
                + "_ter"
            )
            rule = f"string_literal{postfix} -> End"
            if rule not in rules:
                rules[rule] = len(rules)
            actions = [rules[rule]] + actions

        actions.reverse()
        for action in actions:
            rulelist.append(action)
            fatherlist.append(currId)
            fathername.append(node.name)
            endlist.append(len(rulelist) - 1)
        currid = len(rulelist) - 1
    else:
        # no special case
        if node.name not in onelist:
            rule = node.name + " -> "
            for x in child:
                rule += x.name + " "
            if rule not in rules:
                print(f"Adding new rule: {rule}")
                rules[rule] = len(rules)
            rulelist.append(rules[rule])

            fatherlist.append(currId)
            fathername.append(node.name)
            endlist.append(-1)
            currid = len(rulelist) - 1
            for x in child:
                getRule(x, currid)
            endlist[currid] = len(rulelist) - 1
        else:
        # node in onelist, add rules for each child node and End
            for x in child:
                rule = node.name + " -> " + x.name
                if rule not in rules:
                    rules[rule] = len(rules)
                    print(f"Adding new rule: {rule}")
                rulelist.append(rules[rule])

                fatherlist.append(currId)
                fathername.append(node.name)
                currid = len(rulelist) - 1
                endlist.append(-1)
                getRule(x, len(rulelist) - 1)
                endlist[currid] = len(rulelist) - 1
            rule = node.name + " -> End "
            if rule not in rules:
                rules[rule] = len(rules)
                print(f"Adding new rule: {rule}")
            rulelist.append(rules[rule])
            fatherlist.append(currId)
            fathername.append(node.name)
            endlist.append(len(rulelist) - 1)

# check if the tree contains a node named error
def containserror(root):
    if root.name == "ERROR" and len(root.child) != 0:
        return True
    for x in root.child:
        if containserror(x):
            return True
    return False

def processaction(data, newrules=None, mode="gen"):
    global rules, rulelist, fatherlist, fathername, endlist
    if newrules is not None:
        rules = newrules

    pdata = []
    for entry in tqdm(data):
        tree = entry["root"]
        nl   = entry["input"]
        code = entry["code"]

        root = parseTree(tree)
        nroot = Node("java")
        nroot.child = [root]
        root.father = nroot
        root = nroot
        if containserror(root):
            print("Error in tree")
            print(str(root))
            continue

        rulelist = []
        fatherlist = []
        fathername = []
        endlist = []
        try:
            getRule(root, -1)
        except:
            traceback.print_exc()
            print(code)
            continue

        if '"' in stringfy(root):
            code = stringfy(root)

        clsid = tokenizer.cls_token_id
        sepid = tokenizer.sep_token_id
        rulelist = [clsid, rules["start -> java"]] + rulelist + [sepid]

        fatherlist = [-2, -1] + fatherlist
        fatherlist = [x + 2 for x in fatherlist]
        fatherlist = fatherlist + [len(rulelist) - 1]
        endlist = [x + 2 for x in endlist]
        endlist = [0, 1] + endlist + [len(rulelist) - 1]

        pdata.append(
            {
                "nl": tokenizer.encode(nl),
                "rulelist": rulelist,
                "fatherlist": fatherlist,
                "endlist": endlist,
            }
        )
    return pdata, rules
