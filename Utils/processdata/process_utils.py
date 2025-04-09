postfix = '_blind'

onelist = [
    "argument_list",
    "formal_parameters",
    "block",
    "array_initializer",
    "switch_block",
    "type_arguments",
    "method_declaration",
    "modifiers",
    "annotation_argument_list",
    "variable_declarator",
    "throws",
    "element_value_array_initializer",
    "annotation_argument_list",
    "switch_block_statement_group",
    "class_body",
    "catch_type",
    "assert_statement",
    "try_statement",
    "local_variable_declaration",
    "try_statement",
    "constructor_body",
    "type_parameters",
    "resource_specification",
    "inferred_parameters",
    "try_with_resources_statement",
    "inits",
    "updates",
    "conditions",
]
sonelist = [
    "formal_parameters",
    "block",
    "array_initializer",
    "argument_list",
    "type_arguments",
    "annotation_argument_list",
]
identifiers = [
    "identifier",
    "type_identifier",
    "null_literal",
    "decimal_integer_literal",
    "character_literal",
    "decimal_floating_point_literal",
    "hex_integer_literal",
    "string_literal",
]

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
