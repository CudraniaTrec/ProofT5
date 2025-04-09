from .process_utils import Node, identifiers, postfix

identifiers_java = [x + postfix for x in identifiers]
identifiers = identifiers_java

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

# modifies the tree to align the stringfy result with the original code
def giveLam(root):
    if "for_statement" in root.name and "enhance" not in root.name:
        if (
            len(root.child[2].child) > 0
            and root.child[2].child[-1].child[-1].name
            == "local_variable_declaration"+postfix
        ):
            root.child = root.child[:3] + root.child[4:]
    elif "formal_parameters" in root.name:
        node1 = Node("(_ter")
        node2 = Node(")_ter")
        child = [node1]
        for i, x in enumerate(root.child):
            if i == 0:
                child.append(x)
            else:
                child.append(Node(",_ter"))
                child.append(x)
        child.append(node2)
        root.child = child
    elif "block" in root.name and root.name[0] == "b":
        node1 = Node("{_ter")
        node2 = Node("}_ter")
        child = [node1] + root.child + [node2]
        root.child = child
    elif "array_initializer" in root.name:
        node1 = Node("{_ter")
        node2 = Node("}_ter")
        child = [node1]
        for i, x in enumerate(root.child):
            if i == 0:
                child.append(x)
            else:
                child.append(Node(",_ter"))
                child.append(x)
        child.append(node2)
        root.child = child
    elif "argument_list" in root.name:
        node1 = Node("(_ter")
        node2 = Node(")_ter")
        child = [node1]
        for i, x in enumerate(root.child):
            if i == 0:
                child.append(x)
            else:
                child.append(Node(",_ter"))
                child.append(x)
        child.append(node2)
        root.child = child
    elif "type_arguments" in root.name:
        if len(root.child) == 0 or "type_arguments" not in root.child[0].name:
            node1 = Node("<_ter")
            node2 = Node(">_ter")
            child = [node1]
            for i, x in enumerate(root.child):
                if i == 0:
                    child.append(x)
                else:
                    child.append(Node(",_ter"))
                    child.append(x)
            child.append(node2)
            root.child = child
    elif "annotation_argument_list" in root.name:
        node1 = Node("(_ter")
        node2 = Node(")_ter")
        child = [node1]
        for i, x in enumerate(root.child):
            if i == 0:
                child.append(x)
            else:
                child.append(Node(",_ter"))
                child.append(x)
        child.append(node2)
        root.child = child

    for x in root.child:
        giveLam(x)

# merge bpe tokens into one identifier
def mergeIdentifier(root):
    if root.name in identifiers:
        oname = ""
        for x in root.child:
            oname += x.name[:-4]
        oname += "_ter"
        nnode = Node(oname)
        nnode.father = root
        root.child = [nnode]
    for x in root.child:
        mergeIdentifier(x)
    return

#sequentially print all the leaf node names
def stringfy(node):
    ans = ""
    if len(node.child) == 0: #encounters a literal
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

def strfy(treestr, lang="java"):
    tree = parseTree(treestr)
    giveLam(tree)
    mergeIdentifier(tree)
    return stringfy(tree)
