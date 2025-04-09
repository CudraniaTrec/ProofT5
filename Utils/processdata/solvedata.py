from tree_sitter import Language, Parser
from tqdm import tqdm
import traceback, os, sys
from .process_utils import Node, sonelist, postfix

sys.setrecursionlimit(1000000)
path = os.path.split(os.path.realpath(__file__))[0]
JAVA_LANGUAGE = Language(path + "/parser/my-languages.so", "java")
parser = Parser()
parser.set_language(JAVA_LANGUAGE)

# transform tree-sitter tree `root` into a new tree `newroot` 
def revisitTree(root, newroot, code, cursor):
    if root.type == "comment":
        return
    newroot.name = root.type
    children = []

    haschild = cursor.goto_first_child()
    for x in root.children:
        if root.type in sonelist and not x.is_named:
            cursor.goto_next_sibling()
            continue
        fname = cursor.field_name
        tmp = None

        # the child has a field name
        if fname is not None:
            tnode = Node(fname)
            tmp = Node("init")
            tnode.child.append(tmp)
            children.append(tnode)
            tmp.father = tnode
            tnode.father = newroot
        else:
            if x.type != "comment":
                tmp = Node("init")
                children.append(tmp)
                tmp.father = newroot
        if tmp is not None:
            revisitTree(x, tmp, code, cursor)
        cursor.goto_next_sibling()
    newroot.child = children

    if haschild:
        cursor.goto_parent()
    else: # if the node is a leaf node
        ans = code[cursor.node.start_byte : cursor.node.end_byte]
        if root.type != ans:
            tnode = Node(ans)
            newroot.child.append(tnode)
            tnode.father = newroot

def modifyTree(root):
    # add _ter to each leaf node name
    def addter(root):
        if len(root.child) == 0:
            root.name += "_ter"
        else:
            for x in root.child:
                addter(x)
    
    # explicitly add inits, condition, updates node for 'for' loop
    def simplifyFor(root):
        if root.name == "for_statement":
            idx = []
            idloc = -1
            for i, x in enumerate(root.child):
                if x.name == ";_ter":
                    idx.append(i)
                # int i=0;
                if x.name == "init" and x.child[0].name == "local_variable_declaration":
                    idloc = i
            if len(idx) != 2:
                if len(idx) == 1 and idloc != -1:
                    root.child.insert(idloc + 1, Node(";_ter"))
                    idx[0] += 1
                    idx.insert(0, idloc + 1)
                else:
                    assert 0

            inits = Node("inits")
            conditions = Node("conditions")
            updates = Node("updates")
            inits.child = root.child[2 : idx[0]]
            conditions.child = root.child[idx[0] + 1 : idx[1]]
            updates.child = root.child[idx[1] + 1 : -2]

            updates.father = root
            conditions.father = root
            inits.father = root
            root.child = (
                root.child[:2]
                + [inits]
                + [root.child[idx[0]]]
                + [conditions]
                + [root.child[idx[1]]]
                + [updates]
                + root.child[-2:]
            )
        for x in root.child:
            simplifyFor(x)
        return

    # remove ; node
    def removeLam(root):
        if root.name == ";":
            root.father.child.remove(root)
            return
        for x in root.child:
            removeLam(x)

    # add _java to the each non-leaf node name
    def addjava(root):
        if len(root.child) == 0:
            return
        else:
            root.name += postfix
            for x in root.child:
                addjava(x)
        return

    addter(root)
    simplifyFor(root)
    removeLam(root)
    addjava(root)

# for each data in datas, parse the code into a tree (check if it is valid)
def parserTree(datas):
    data = []
    validids = []  # which data is valid
    for i in tqdm(range(len(datas))):
        try:
            code = datas[i]["function"]
            root_node = parser.parse(bytes(code, 'utf-8')).root_node
            cursor = root_node.walk()
            sroot = Node("init")
            revisitTree(root_node, sroot, code, cursor)
            modifyTree(sroot)

            ans = datas[i]["nl"]
            if f"ERROR{postfix}🚀class{postfix}🚀" in sroot.getTreestr():
                continue
            if f"ERROR{postfix}🚀" in sroot.getTreestr():
                assert 0
            validids.append(i)
            data.append(
                {
                    "input": ans,
                    "root": sroot.getTreestr(),
                    "code": datas[i]["function"],
                }
            )
        except Exception as e:
            try:
                print("*" * 20 + f"{e}" + "*" * 20)
                traceback.print_exc()
                print(datas[i]["function"])
            except:
                pass
            pass
    return data, validids
