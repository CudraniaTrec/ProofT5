postfix = '_dsl'
lit_postfix = '_ter'

identifiers = [
    "identifier",
    "variable_identifier",
    "type_identifier",
    "integer_literal",
    "character_literal",
    "floating_point_literal",
    "string_literal",
]
identifiers = [x + postfix for x in identifiers]

class Node:
    def __init__(self, name: str):
        self.name = name
        self.father = None
        self.child = []
        self.treestr = ""

    def printTree(self, r, sep_token="🚀"):
        s = r.name + sep_token
        for c in r.child:
            s += self.printTree(c)
        s += "^"+sep_token
        return s

    def getTreestr(self):
        if self.treestr == "":
            self.treestr = self.printTree(self)
            return self.treestr
        else:
            return self.treestr
    
    #convert to json
    def prettyprint(self, r):
        ret_obj = {}
        ret_obj["name"] = r.name
        ret_obj["child_cnt"] = len(r.child)
        ret_obj["child"] = [c.prettyprint(c) for c in r.child]
        return ret_obj
    
    def __str__(self):
        import json
        return json.dumps(self.prettyprint(self), indent=1, ensure_ascii=False)

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return False
        if self.name.lower() != other.name.lower():
            return False
        if len(self.child) != len(other.child):
            return False
        return self.getTreestr().strip() == other.getTreestr().strip()

# parse tree string with 🚀 back into tree
def parseTree(treestr):
    tokens = treestr.strip().split("🚀")[:-1]
    root = Node(tokens[0])
    currnode = root
    for i, x in enumerate(tokens[1:]):
        if x != "^":
            nnode = Node(x)
            nnode.father = currnode
            currnode.child.append(nnode)
            currnode = nnode
        else:
            currnode = currnode.father
    return root

# merge bpe tokens into one identifier
def mergeIdentifier(root):
    if root.name in identifiers:
        oname = ""
        for x in root.child:
            oname += x.name[:-4]
        oname += lit_postfix
        nnode = Node(oname)
        nnode.father = root
        root.child = [nnode]
    for x in root.child:
        mergeIdentifier(x)
    return

#sequentially print all the leaf node names
def stringfy(node):
    ans = ""
    if len(node.child) == 0: # encounters a literal
        if node.name[0] == "Ġ":
            if "string_literal" in node.father.name:
                ans += node.name[1:-4].replace("Ġ", " ")
            else:
                ans += node.name[1:-4]
        else:
            ans = node.name[:-4]
    else:
        for x in node.child:
            ans += stringfy(x) + " "
    return ans

def strfy(treestr):
    tree = parseTree(treestr)
    mergeIdentifier(tree)
    return stringfy(tree)
