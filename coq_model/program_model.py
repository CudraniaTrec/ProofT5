from transformers import AutoTokenizer
from copy import deepcopy
import traceback
import pickle, os

type_name_vocab = [] # all type names
term_name_vocab = [] # all term names
statement_name_vocab = [] # all statement names
program_name_vocab = []   # all program names
class_name_vocab = [
    "Object",
    "Arrays",
    "Integer",
    "Math",
    "String",
    "Character",
    "Long",
    "Double",
    "List",
    "Set",
    "Map",
]
method_name_vocab = [
    "toUpperCase",
    "isUpperCase",
    "log",
    "put",
    "keySet",
    "replace",
    "find",
    "toBinaryString",
    "indexOf",
    "reverse",
    "push",
    "add",
    "intValue",
    "toString",
    "remove",
    "join",
    "isEmpty",
    "getKey",
    "pop",
    "append",
    "hasNext",
    "length",
    "getValue",
    "floor",
    "contains",
    "endsWith",
    "valueOf",
    "pow",
    "containsKey",
    "copyOf",
    "toArray",
    "get",
    "min",
    "sort",
    "size",
    "concat",
    "format",
    "exit",
    "clear",
    "max",
    "sum",
    "random",
    "clone",
    "entrySet",
    "sqrt",
    "PI",
    "log10",
    "tan",
    "equals",
    "trim",
    "getOrDefault",
    "split",
    "values",
    "MIN_VALUE",
    "out",
    "copyOfRange",
    "asList",
    "next",
    "set",
    "round",
    "offerLast",
    "toCharArray",
    "parseInt",
    "substring",
    "floorDiv",
    "abs",
    "hashCode",
    "startsWith",
    "toLowerCase",
    "fill",
    "ceil",
    "isLowerCase",
    "MAX_VALUE",
    "empty",
]
terms_need_dict = {}
name2cls = {}
concrete_class_map = {
    "List": "ArrayList",
    "Set": "HashSet",
    "Map": "HashMap"
}

tokenizer = AutoTokenizer.from_pretrained(
    "Salesforce/codet5-small", min_length=4, local_files_only=True)

class CoqProof:
    partial_proof = False
    def __init__(self, tactic, params={}, children=[]):
        if tactic[:2] == "T_":  # tactic starts with T_
            self.isEapply = True
        else:
            self.isEapply = False
        self.tactic = tactic
        self.params = params
        self.children = children

    # translate into coq proof string
    def toString(self, indent=0):
        proof_str = "  " * indent
        def toStr(param):
            if "Ty" not in str(type(param)):
                return f"{param}"
            else:
                return param.to_coq()

        # main proof sentence
        if self.isEapply:
            params_list = [
                f"({k}:={toStr(self.params[k])})"
                for k in self.params
                if self.params[k]
            ]
            if len(params_list) == 0:
                proof_str += "eapply " + self.tactic + "."
            else:
                proof_str += (
                    "eapply " + self.tactic + " with" + "".join(params_list) + "."
                )
        else:
            proof_str += self.tactic + "."

        # if some parameters are not finished, add annotation
        if not CoqProof.partial_proof:
            params_not_finish = False
            for k in self.params:
                if "TyUnk" in toStr(self.params[k]) or "StrUnk" in toStr(self.params[k]):
                    params_not_finish = True
                    break
            if params_not_finish or self.tactic == "admit":
                CoqProof.partial_proof = True # mark the proof as not finished
                return "  " * indent + "simpl. Show. admit."
        else:
            return "  " * indent + "admit."

        # append proof of children
        if len(self.children) == 1:
            child_proof = self.children[0].toString(indent)
            proof_str += f"\n{child_proof}"
        else:
            for child in self.children:
                child_proof = child.toString(indent + 1)[2*(indent+1):]
                proof_str += f"\n{'  '*indent}{{ {child_proof} }}"
        return proof_str

    def __repr__(self):
        prefix="""From PLF Require Import Syntax.
Open Scope string_scope.
Example prog_well_typed : exists p, program_well_typed p.
Proof. unfold program_well_typed. eexists. eexists."""
        suffix1="""Unshelve.
all: apply TyVoid.
Defined."""
        suffix2="""Admitted."""

        CoqProof.partial_proof = False
        coq_code = self.toString()
        if CoqProof.partial_proof: # if the proof is not finished
            suffix = suffix2
        else:
            suffix = suffix1
        coqProof=f"{prefix}\n{coq_code}\n{suffix}"
        return coqProof

    def tokenization(self):
        """
        Tokenizes the proof string.

        Returns:
            List[str]: The list of tokens.
        """

        tokens = []
        if self.isEapply:
            tokens.append(self.tactic)
            # tokenize parameters
            for k in self.params:
                pvalue= self.params[k]
                # remove the quotation marks
                if pvalue[0] == '"' and pvalue[-1] == '"':
                    pvalue = pvalue[1:-1]

                ptokens = tokenizer.tokenize(pvalue)
                if pvalue.startswith('Ty') or pvalue.startswith('(Ty'): # type
                    tokens += [
                        token
                        for token in [t.replace("Ġ", "") for t in ptokens 
                                      if "(" not in t and ")" not in t]
                        if token not in [" ", tokenizer.unk_token, '"', ""]
                    ]
                else: # string
                    tokens += [
                        token
                        for token in ptokens
                        if (token not in [tokenizer.unk_token, '"', ""])
                    ] + [tokenizer.eos_token]

        elif self.tactic == "reflexivity":
            pass
        else:
            tokens.append(self.tactic)

        for child in self.children:
            tokens += child.tokenization()
        return tokens

proof_refl = CoqProof("reflexivity")

def addIndentation(string, indent=2):
    return "\n".join([f"{' '*indent}{line}" for line in string.split("\n")])

class TypeMeta(type):
    def __init__(cls, name, bases, dct):
        super().__init__(name, bases, dct)
        tname = name
        if tname not in ["Type", "TyUnk"]:
            type_name_vocab.append(tname)
            terms_need_dict[tname] = dct["terms_need"]
            name2cls[tname] = cls

        original_init = cls.__init__    
        def new_init(self, *args, **kwargs):
            self.complete = False
            original_init(self, *args, **kwargs)
        cls.__init__ = new_init

class TacticMeta(type):
    def __init__(cls, name, bases, dct):
        super().__init__(name, bases, dct)
        if name == "PgConcat":
            tname = "T_ProgramConcat"
        else:
            tname = "T_"+name[2:]
        if len(bases) > 0 and name not in ["TmUnk", "StUnk", "PgUnk"]:
            base_name = bases[0].__name__
            if base_name == "Term":
                term_name_vocab.append(tname)
            elif base_name == "Statement":
                statement_name_vocab.append(tname)
            elif base_name == "Program":
                program_name_vocab.append(tname)
            terms_need_dict[tname] = dct["terms_need"]
            name2cls[tname] = cls

        original_init = cls.__init__    
        def new_init(self, *args, **kwargs):
            self.complete = False
            original_init(self, *args, **kwargs)
        cls.__init__ = new_init
    
class Type(metaclass=TypeMeta):
    terms_need = []
class Term(metaclass=TacticMeta):
    terms_need = []
class Statement(metaclass=TacticMeta):
    terms_need = []
class Program(metaclass=TacticMeta):
    terms_need = []

# Type level
class TyUnk(Type):
    terms_need = []
    def __init__(self):
        self.complete = True

    def to_coq(self):
        return "TyUnk"
    
    def to_code(self):
        return "?"
    
    def to_java(self, context={}):
        return "?"
    
class TyInt(Type):
    terms_need = []
    def __init__(self):
        self.complete = True

    def to_coq(self):
        return "TyInt"
    
    def to_code(self):
        return "int"
    
    def to_java(self, context={}):
        if "wrapper" in context and context["wrapper"]:
            return "Integer"
        return "int"

class TyFloat(Type):
    terms_need = []
    def __init__(self):
        self.complete = True

    def to_coq(self):
        return "TyFloat"
    
    def to_code(self):
        return "double"
    
    def to_java(self, context={}):
        if "wrapper" in context and context["wrapper"]:
            return "Double"
        return "double"
    
class TyChar(Type):
    terms_need = []
    def __init__(self):
        self.complete = True

    def to_coq(self):
        return "TyChar"
    
    def to_code(self):
        return "char"
    
    def to_java(self, context={}):
        if "wrapper" in context and context["wrapper"]:
            return "Character"
        return "char"
    
class TyBool(Type):
    terms_need = []
    def __init__(self):
        self.complete = True

    def to_coq(self):
        return "TyBool"
    
    def to_code(self):
        return "bool"

    def to_java(self, context={}):
        if "wrapper" in context and context["wrapper"]:
            return "Boolean"
        return "boolean"
    
class TyString(Type):
    terms_need = []
    def __init__(self):
        self.complete = True

    def to_coq(self):
        return "TyString"
    
    def to_code(self):
        return "string"
    
    def to_java(self, context={}):
        return "String"
    
class TyArray(Type):
    terms_need = ["Type"]
    def __init__(self, *args):
        self.ty = TyUnk()
        if len(args) >= 1:
            self.ty = args[0]
            self.complete = True
        assert isinstance(self.ty, Type), f"invalid TyArray type: {self.to_coq()}"
    
    def to_coq(self):
        return f"(TyArray {self.ty.to_coq()})"
    
    def to_code(self):
        return f"{self.ty.to_code()}[]"
    
    def to_java(self, context={}):
        return f"{self.ty.to_java(context)}[]"

class TyGeneric0(Type):
    terms_need = ["ClassString"]
    def __init__(self, *args):
        self.string = "StrUnk"
        if len(args) >= 1:
            self.string = args[0]
            self.complete = True
        assert isinstance(self.string, str), f"invalid TyGeneric0 type: {self.to_coq()}"
    
    def to_coq(self):
        return f'(TyGeneric0 "{self.string}")'
    
    def to_code(self):
        return self.string+"<>"

    def to_java(self, context={}):
        base_class_name = self.string
        if "concrete" in context and context["concrete"] and base_class_name in concrete_class_map:
            base_class_name = concrete_class_map[base_class_name]
        return f"{base_class_name}<>"

class TyGeneric1(Type):
    terms_need = ["ClassString", "Type"]
    def __init__(self, *args):
        self.string = "StrUnk"
        self.ty = TyUnk()
        if len(args) >= 1:
            self.string = args[0]
        if len(args) >= 2:
            self.ty = args[1]
            self.complete = True
        assert isinstance(self.string, str) and \
               isinstance(self.ty, Type), f"invalid TyGeneric1 type: {self.to_coq()}"
        
    def to_coq(self):
        return f'(TyGeneric1 "{self.string}" {self.ty.to_coq()})'
    
    def to_code(self):
        return f"{self.string}<{self.ty.to_code()}>"
    
    def to_java(self, context={}):
        typed_context = deepcopy(context)
        typed_context["wrapper"] = True
        typed_context["concrete"] = False
        base_class_name = self.string
        if "concrete" in context and context["concrete"]:
            if base_class_name in concrete_class_map:
                base_class_name = concrete_class_map[base_class_name]
        return f"{base_class_name}<{self.ty.to_java(typed_context)}>"

class TyGeneric2(Type):
    terms_need = ["ClassString", "Type", "Type"]
    
    def __init__(self, *args):
        self.string = "StrUnk"
        self.ty1 = TyUnk()
        self.ty2 = TyUnk()
        if len(args) >= 1:
            self.string = args[0]
        if len(args) >= 2:
            self.ty1 = args[1]
        if len(args) >= 3:
            self.ty2 = args[2]
            self.complete = True
        assert isinstance(self.string, str) and \
               isinstance(self.ty1, Type) and \
               isinstance(self.ty2, Type), f"invalid TyGeneric2 type: {self.to_coq()}"
    
    def to_coq(self):
        return f'(TyGeneric2 "{self.string}" {self.ty1.to_coq()} {self.ty2.to_coq()})'
    
    def to_code(self):
        return f"{self.string}<{self.ty1.to_code()}, {self.ty2.to_code()}>"
    
    def to_java(self, context={}):
        typed_context = deepcopy(context)
        typed_context["wrapper"] = True
        typed_context["concrete"] = False
        base_class_name = self.string
        if "concrete" in context and context["concrete"] and base_class_name in concrete_class_map:
            base_class_name = concrete_class_map[base_class_name]
        return f"{base_class_name}<{self.ty1.to_java(typed_context)}, {self.ty2.to_java(typed_context)}>"

class TyArrow(Type):
    terms_need = ["Type", "Type"]
    def __init__(self, *args):
        self.ty1 = TyUnk()
        self.ty2 = TyUnk()
        if len(args) >= 1:
            self.ty1 = args[0]
        if len(args) >= 2:
            self.ty2 = args[1]
            self.complete = True
        assert isinstance(self.ty1, Type) and \
               isinstance(self.ty2, Type), f"invalid TyArrow type: {self.to_coq()}"
    
    def to_coq(self):
        return f'(TyArrow {self.ty1.to_coq()} {self.ty2.to_coq()})'
    
    def to_code(self):
        return f"{self.ty1.to_code()} -> {self.ty2.to_code()}"

    def to_java(self, context={}):
        return f"{self.ty1.to_java(context)} -> {self.ty2.to_java(context)}"
    
class TyClass(Type):
    terms_need = ["ClassString"]
    def __init__(self, *args):
        self.string = "StrUnk"
        if len(args) >= 1:
            self.string = args[0]
            self.complete = True
        assert isinstance(self.string, str), f"invalid TyClass type: {self.to_coq()}"
    
    def to_coq(self):
        return f'(TyClass "{self.string}")'
    
    def to_code(self):
        return self.string

    def to_java(self, context={}):
        return self.string

class TyVoid(Type):
    terms_need = []
    def __init__(self):
        self.complete = True

    def to_coq(self):
        return "TyVoid"
    
    def to_code(self):
        return "void"
    
    def to_java(self, context={}):
        return "void"

class TyConcat(Type):
    terms_need = ["Type", "Type"]
    def __init__(self, *args):
        self.ty1 = TyUnk()
        self.ty2 = TyUnk()
        if len(args) >= 1:
            self.ty1 = args[0]
        if len(args) >= 2:
            self.ty2 = args[1]
            self.complete = True
        assert isinstance(self.ty1, Type) and \
               isinstance(self.ty2, Type), f"invalid TyConcat type: {self.to_coq()}"
    
    def to_coq(self):
        return f"(TyConcat {self.ty1.to_coq()} {self.ty2.to_coq()})"
    
    def to_code(self):
        return f"{self.ty1.to_code()}::{self.ty2.to_code()}"
    
    def to_java(self, context={}):
        return f"{self.ty1.to_java(context)}, {self.ty2.to_java(context)}"

# Term level
class TmUnk(Term):
    terms_need = []
    def __init__(self):
        self.complete = True
    
    def to_coq(self):
        return CoqProof("admit")
    
    def to_code(self):
        return "?"

    def to_java(self, context={}):
        return "?"
    
class TmVar(Term):
    terms_need = ["String"]
    def __init__(self, *args):
        self.string = "StrUnk"
        if len(args) >= 1:
            self.string = args[0]
            self.complete = True
        assert isinstance(self.string, str), f"invalid TmVar type: {self.to_coq()}"
    
    def to_coq(self):
        return CoqProof("T_Var", params={"x": f'"{self.string}"'}, 
                        children=[proof_refl])
    
    def to_code(self):
        return self.string

    def to_java(self, context={}):
        return self.string

class TmInteger(Term):
    terms_need = ["String"]
    def __init__(self, *args):
        self.int_literal = "StrUnk"
        if len(args) >= 1:
            self.int_literal = args[0]
            self.complete = True
        assert isinstance(self.int_literal, str), f"invalid TmInteger type: {self.to_coq()}"
    
    def to_coq(self):
        return CoqProof("T_Integer", params={"n": self.int_literal})
    
    def to_code(self):
        return self.int_literal
    
    def to_java(self, context={}):
        return self.int_literal
    
class TmFloat(Term):
    terms_need = ["String"]
    def __init__(self, *args):
        self.float_literal = "StrUnk"
        if len(args) >= 1:
            self.float_literal = args[0]
            self.complete = True
        assert isinstance(self.float_literal, str), f"invalid TmFloat type: {self.to_coq()}"
    
    def to_coq(self):
        return CoqProof("T_Float", params={"f": self.float_literal})
    
    def to_code(self):
        return self.float_literal
    
    def to_java(self, context={}):
        return self.float_literal

class TmChar(Term):
    terms_need = ["String"]
    def __init__(self, *args):
        self.char_literal = "StrUnk"
        if len(args) >= 1:
            self.char_literal = str(ord(args[0]))
            self.complete = True
        assert isinstance(self.char_literal, str), f"invalid TmChar type: {self.to_coq()}"
    
    def to_coq(self):
        return CoqProof("T_Char", params={"c": f"{self.char_literal}"})
    
    def to_code(self):
        return f"'{chr(self.char_literal)}'"
    
    def to_java(self, context={}):
        return f"'{chr(self.char_literal)}'"

class TmString(Term):
    terms_need = ["StringOrEnd"]
    def __init__(self, *args):
        self.string = "StrUnk"
        if len(args) >= 1:
            self.string = args[0]
            self.complete = True
        assert isinstance(self.string, str), f"invalid TmString type: {self.to_coq()}"
    
    def to_coq(self):
        return CoqProof("T_String", params={"s": f'"{self.string}"'})
    
    def to_code(self):
        return f'"{self.string}"'
    
    def to_java(self, context={}):
        return f'"{self.string}"'
   
class TmNull(Term):
    terms_need = []
    def __init__(self):
        self.complete = True
        
    def to_coq(self):
        return CoqProof("T_Null")
    
    def to_code(self):
        return "null"
    
    def to_java(self, context={}):
        return "null"
    
class TmTrue(Term):
    terms_need = []
    def __init__(self):
        self.complete = True
        
    def to_coq(self):
        return CoqProof("T_True")
    
    def to_code(self):
        return "true"
    
    def to_java(self, context={}):
        return "true"

class TmFalse(Term):
    terms_need = []
    def __init__(self):
        self.complete = True
        
    def to_coq(self):
        return CoqProof("T_False")
    
    def to_code(self):
        return "false"
    
    def to_java(self, context={}):
        return "false"

class TmAssign(Term):
    terms_need = ["Term", "Term"]
    def __init__(self, *args):
        self.term1 = TmUnk()
        self.term2 = TmUnk()
        if len(args) >= 1:
            self.term1 = args[0]
        if len(args) >= 2:
            self.term2 = args[1]
            self.complete = True
        assert isinstance(self.term1, Term) and \
               isinstance(self.term2, Term), f"invalid TmAssign type: {self.to_coq()}"
    
    def to_coq(self):
        return CoqProof("T_Assign", children=[self.term1.to_coq(), 
                                              self.term2.to_coq()])
    
    def to_code(self):
        return f"{self.term1.to_code()} := {self.term2.to_code()}"
    
    def to_java(self, context={}):
        return f"{self.term1.to_java(context)} = {self.term2.to_java(context)}"
    
class TmConversion(Term):
    terms_need = ["Type", "Term"]
    def __init__(self, *args):
        self.ty = TyUnk()
        self.term = TmUnk()
        if len(args) >= 1:
            self.ty = args[0]
        if len(args) >= 2:
            self.term = args[1]
            self.complete = True
        assert isinstance(self.ty, Type) and \
               isinstance(self.term, Term), f"invalid TmConversion type: {self.to_coq()}"
    
    def to_coq(self):
        return CoqProof("T_Conversion", params={"T": self.ty.to_coq()}, 
                        children=[self.term.to_coq(), proof_refl])
    
    def to_code(self):
        return f"({self.ty.to_code()}) {self.term.to_code()}"
    
    def to_java(self, context={}):
        return f"({self.ty.to_java(context)}) {self.term.to_java(context)}"

class TmInstanceOf(Term):
    terms_need = ["Type", "Term"]
    def __init__(self, *args):
        self.ty = TyUnk()
        self.term = TmUnk()
        if len(args) >= 1:
            self.ty = args[0]
        if len(args) >= 2:
            self.term = args[1]
            self.complete = True
        assert isinstance(self.ty, Type) and \
               isinstance(self.term, Term), f"invalid TmInstanceOf type: {self.to_coq()}"

    
    def to_coq(self):
        return CoqProof("T_InstanceOf", params={"T": self.ty.to_coq()}, 
                        children=[self.term.to_coq()])
    
    def to_code(self):
        return f"{self.term.to_code()} hasType {self.ty.to_code()}"
    
    def to_java(self, context={}):
        return f"{self.term.to_java(context)} instanceof {self.ty.to_java(context)}"

class TmChoose(Term):
    terms_need = ["Term", "Term", "Term"]
    def __init__(self, *args):
        self.term1 = TmUnk()
        self.term2 = TmUnk()
        self.term3 = TmUnk()
        if len(args) >= 1:
            self.term1 = args[0]
        if len(args) >= 2:
            self.term2 = args[1]
        if len(args) >= 3:
            self.term3 = args[2]
            self.complete = True
        assert isinstance(self.term1, Term) and \
               isinstance(self.term2, Term) and \
               isinstance(self.term3, Term), f"invalid TmChoose type: {self.to_coq()}"
    
    def to_coq(self):
        return CoqProof("T_Choose", children=[self.term1.to_coq(), 
                                              self.term2.to_coq(), 
                                              self.term3.to_coq()])
    
    def to_code(self):
        return f"({self.term1.to_code()}) ? {self.term2.to_code()} : {self.term3.to_code()}"
    
    def to_java(self, context={}):
        return f"({self.term1.to_java(context)}) ? {self.term2.to_java(context)} : {self.term3.to_java(context)}"
    
class TmFieldAccess(Term):
    terms_need = ["String", "Term"]
    def __init__(self, *args):
        self.term = TmUnk()
        self.string = "StrUnk"
        if len(args) >= 1:
            self.string = args[0]
        if len(args) >= 2:
            self.term = args[1]
            self.complete = True
        assert isinstance(self.term, Term) and \
                isinstance(self.string, str), f"invalid TmFieldAccess type: {self.to_coq()}"
    
    def to_coq(self):
        return CoqProof("T_FieldAccess", params={"f": f'"{self.string}"'}, 
                        children=[self.term.to_coq(),
                                  proof_refl, proof_refl])
    
    def to_code(self):
        return f"{self.term.to_code()}.{self.string}"

    def to_java(self, context={}):
        return f"{self.term.to_java(context)}.{self.string}"
    
class TmArrayAccess(Term):
    terms_need = ["Term", "Term"]
    def __init__(self, *args):
        self.term1 = TmUnk()
        self.term2 = TmUnk()
        if len(args) >= 1:
            self.term1 = args[0]
        if len(args) >= 2:
            self.term2 = args[1]
            self.complete = True
        assert isinstance(self.term1, Term) and \
               isinstance(self.term2, Term), f"invalid TmArrayAccess type: {self.to_coq()}"
    
    def to_coq(self):
        return CoqProof("T_ArrayAccess", children=[self.term1.to_coq(), 
                                                   self.term2.to_coq()])
    
    def to_code(self):
        return f"{self.term1.to_code()}[{self.term2.to_code()}]"
    
    def to_java(self, context={}):
        return f"{self.term1.to_java(context)}[{self.term2.to_java(context)}]"
    
class TmNew(Term):
    terms_need = ["Type", "Term"]
    def __init__(self, *args):
        self.ty = TyUnk()
        self.param = TmUnk()
        if len(args) >= 1:
            self.ty = args[0]
        if len(args) >= 2:
            self.param = args[1]
            self.complete = True
        assert isinstance(self.ty, Type) and \
               isinstance(self.param, Term), f"invalid TmNew type: {self.to_coq()}"
    
    def to_coq(self):
        return CoqProof("T_New", params={"T": self.ty.to_coq()}, 
                        children=[proof_refl, proof_refl, 
                                  self.param.to_coq(), proof_refl])
    
    def to_code(self):
        return f"new {self.ty.to_code()}({self.param.to_code()})"

    def to_java(self, context={}):
        typed_context = deepcopy(context)
        typed_context["wrapper"] = True
        typed_context["concrete"] = True
        return f"new {self.ty.to_java(typed_context)}({self.param.to_java(context)})"

class TmNewArray0(Term):
    terms_need = ["Type"]
    def __init__(self, *args):
        self.ty = TyUnk()
        if len(args) >= 1:
            self.ty = args[0]
            self.complete = True
        assert isinstance(self.ty, Type), f"invalid TmNewArray0 type: {self.to_coq()}"
    
    def to_coq(self):
        return CoqProof("T_NewArray0", params={"T": self.ty.to_coq()})
    
    def to_code(self):
        ty_str = self.ty.to_code()
        return f"new {ty_str}"
    
    def to_java(self, context={}):
        return f"new {self.ty.to_java(context)}"

class TmNewArray1(Term):
    terms_need = ["Term", "Term"]
    def __init__(self, *args):
        self.term1 = TmUnk()
        self.term2 = TmUnk()
        if len(args) >= 1:
            self.term1 = args[0]
        if len(args) >= 2:
            self.term2 = args[1]
            self.complete = True
        assert isinstance(self.term1, Term) and \
               isinstance(self.term2, Term), f"invalid TmNewArray1 type: {self.to_coq()}"
    
    def to_coq(self):
        return CoqProof("T_NewArray1", children=[self.term1.to_coq(), 
                                                 self.term2.to_coq()])
    
    def to_code(self):
        return f"{self.term2.to_code()}[{self.term1.to_code()}]"
    
    def to_java(self, context={}):
        return f"{self.term2.to_java(context)}[{self.term1.to_java(context)}]"

class TmMethodInvocation(Term):
    terms_need = ["String", "Term", "Term"]
    def __init__(self, *args):
        self.term = TmUnk()
        self.string = "StrUnk"
        self.param = TmUnk()
        if len(args) >= 1:
            self.string = args[0]
        if len(args) >= 2:
            self.term = args[1]
        if len(args) >= 3:
            self.param = args[2]
            self.complete = True
        assert isinstance(self.term, Term) and \
               isinstance(self.param, Term) and \
               isinstance(self.string, str), f"invalid TmMethodInvocation type: {self.to_coq()}"
    
    def to_coq(self):
        return CoqProof("T_MethodInvocation", params={"m": f'"{self.string}"'}, 
                        children=[self.term.to_coq(), proof_refl, proof_refl,
                                  self.param.to_coq(), proof_refl]) 
    
    def to_code(self):
        return f"{self.term.to_code()}.{self.string}({self.param.to_code()})"
    
    def to_java(self, context={}):
        return f"{self.term.to_java(context)}.{self.string}({self.param.to_java(context)})"

class TmMethodInvocationNoObj(Term):
    terms_need = ['String', 'Term']
    def __init__(self, *args):
        self.string = "StrUnk"
        self.param = TmUnk()
        if len(args) >= 1:
            self.string = args[0]
        if len(args) >= 2:
            self.param = args[1]
            self.complete = True
        assert isinstance(self.param, Term) and \
               isinstance(self.string, str), f"invalid TmMethodInvocationNoObj type: {self.to_coq()}"
    
    def to_coq(self):
        return CoqProof("T_MethodInvocationNoObj", 
                        params={"m": f'"{self.string}"'}, 
                        children=[proof_refl, self.param.to_coq(), proof_refl])
    
    def to_code(self):
        return f"{self.string}({self.param.to_code()})"
    
    def to_java(self, context={}):
        return f"{self.string}({self.param.to_java(context)})"

class TmType(Term):
    terms_need = ["Type"]
    def __init__(self, *args):
        self.ty = TyUnk()
        if len(args) >= 1:
            self.ty = args[0]
            self.complete = True
        assert isinstance(self.ty, Type), f"invalid TmType type: {self.to_coq()}"
    
    def to_coq(self):
        return CoqProof("T_Type", params={"T": self.ty.to_coq()})
    
    def to_code(self):
        return self.ty.to_code()
    
    def to_java(self, context={}):
        typed_context = deepcopy(context)
        typed_context["wrapper"] = True
        return self.ty.to_java(typed_context)

class TmList0(Term):
    terms_need = []
    def __init__(self):
        self.complete = True

    def to_coq(self):
        return CoqProof("T_List0")

    def to_code(self):
        return ""
    
    def to_java(self, context={}):
        return ""

class TmList1(Term):
    terms_need = ["Term", "Term"]
    def __init__(self, *args):
        self.term1 = TmUnk()
        self.term2 = TmUnk()
        if len(args) >= 1:
            self.term1 = args[0]
        if len(args) >= 2:
            self.term2 = args[1]
            self.complete = True
        assert isinstance(self.term1, Term) and \
               isinstance(self.term2, Term), f"invalid TmList1 type: {self.to_coq()}"
    
    def to_coq(self):
        return CoqProof("T_List1", children=[self.term1.to_coq(), 
                                             self.term2.to_coq()])

    def to_code(self):
        ret_string = f"{self.term1.to_code()}, {self.term2.to_code()}"
        if ret_string.endswith(", "):
            ret_string = ret_string[:-2]
        return ret_string
    
    def to_java(self, context={}):
        ret_string = f"{self.term1.to_java(context)}, {self.term2.to_java(context)}"
        if ret_string.endswith(", "):
            ret_string = ret_string[:-2]
        return ret_string

class TmArray0(Term):
    terms_need = []
    def __init__(self):
        self.complete = True
    
    def to_coq(self):
        return CoqProof("T_Array0")
    
    def to_code(self):
        return "{}"
    
    def to_java(self, context={}):
        return "{}"

class TmArray1(Term):
    terms_need = ["Term", "Term"]
    def __init__(self, *args):
        self.term1 = TmUnk()
        self.term2 = TmUnk()
        if len(args) >= 1:
            self.term1 = args[0]
        if len(args) >= 2:
            self.term2 = args[1]
            self.complete = True
        assert isinstance(self.term1, Term) and \
               isinstance(self.term2, Term), f"invalid TmArray1 type: {self.to_coq()}"
    
    def to_coq(self):
        return CoqProof("T_Array1", children=[self.term1.to_coq(), 
                                              self.term2.to_coq()])
                                        
    def to_code(self):
        tm2_string = self.term2.to_code()
        assert tm2_string.startswith("{"), f"invalid tm2_string: {tm2_string}"
        return f"{{{self.term1.to_code()},{tm2_string[1:]}"
    
    def to_java(self, context={}):
        tm2_string = self.term2.to_java(context)
        assert tm2_string.startswith("{"), f"invalid tm2_string: {tm2_string}"
        return f"{{{self.term1.to_java(context)},{tm2_string[1:]}"
    
class TmParenthesis(Term):
    terms_need = ["Term"]
    def __init__(self, *args):
        self.term = TmUnk()
        if len(args) >= 1:
            self.term = args[0]
            self.complete = True
        assert isinstance(self.term, Term), f"invalid TmParenthesis type: {self.to_coq()}"
    
    def to_coq(self):
        return CoqProof("T_Parenthesis", children=[self.term.to_coq()])
    
    def to_code(self):
        return f"({self.term.to_code()})"
    
    def to_java(self, context={}):
        return f"({self.term.to_java(context)})"

class TmAdd(Term):
    terms_need = ["Term", "Term"]
    def __init__(self, *args):
        self.term1 = TmUnk()
        self.term2 = TmUnk()
        if len(args) >= 1:
            self.term1 = args[0]
        if len(args) >= 2:
            self.term2 = args[1]
            self.complete = True
        assert isinstance(self.term1, Term) and \
               isinstance(self.term2, Term), f"invalid TmAdd type: {self.to_coq()}"
    
    def to_coq(self):
        return CoqProof("T_Add", children=[self.term1.to_coq(), 
                                           self.term2.to_coq(),
                                           proof_refl])
    
    def to_code(self):
        return f"{self.term1.to_code()} + {self.term2.to_code()}"
    
    def to_java(self, context={}):
        return f"{self.term1.to_java(context)} + {self.term2.to_java(context)}"

class TmSub(Term):
    terms_need = ["Term", "Term"]
    def __init__(self, *args):
        self.term1 = TmUnk()
        self.term2 = TmUnk()
        if len(args) >= 1:
            self.term1 = args[0]
        if len(args) >= 2:
            self.term2 = args[1]
            self.complete = True
        assert isinstance(self.term1, Term) and \
                isinstance(self.term2, Term), f"invalid TmSub type: {self.to_coq()}"
    
    def to_coq(self):
        return CoqProof("T_Sub", children=[self.term1.to_coq(), 
                                           self.term2.to_coq(),
                                            proof_refl])
    
    def to_code(self):
        return f"{self.term1.to_code()} - {self.term2.to_code()}"

    def to_java(self, context={}):
        return f"{self.term1.to_java(context)} - {self.term2.to_java(context)}"

class TmMul(Term):
    terms_need = ["Term", "Term"]
    def __init__(self, *args):
        self.term1 = TmUnk()
        self.term2 = TmUnk()
        if len(args) >= 1:
            self.term1 = args[0]
        if len(args) >= 2:
            self.term2 = args[1]
            self.complete = True
        assert isinstance(self.term1, Term) and \
                isinstance(self.term2, Term), f"invalid TmMul type: {self.to_coq()}"
    
    def to_coq(self):
        return CoqProof("T_Mul", children=[self.term1.to_coq(), 
                                           self.term2.to_coq(),
                                           proof_refl])
    
    def to_code(self):
        return f"{self.term1.to_code()} * {self.term2.to_code()}"
    
    def to_java(self, context={}):
        return f"{self.term1.to_java(context)} * {self.term2.to_java(context)}"

class TmDiv(Term):
    terms_need = ["Term", "Term"]
    def __init__(self, *args):
        self.term1 = TmUnk()
        self.term2 = TmUnk()
        if len(args) >= 1:
            self.term1 = args[0]
        if len(args) >= 2:
            self.term2 = args[1]
            self.complete = True
        assert isinstance(self.term1, Term) and \
                isinstance(self.term2, Term), f"invalid TmDiv type: {self.to_coq()}"
    
    def to_coq(self):
        return CoqProof("T_Div", children=[self.term1.to_coq(), 
                                           self.term2.to_coq(),
                                           proof_refl])
    
    def to_code(self):
        return f"{self.term1.to_code()} / {self.term2.to_code()}"
    
    def to_java(self, context={}):
        return f"{self.term1.to_java(context)} / {self.term2.to_java(context)}"

class TmMod(Term):
    terms_need = ["Term", "Term"]
    def __init__(self, *args):
        self.term1 = TmUnk()
        self.term2 = TmUnk()
        if len(args) >= 1:
            self.term1 = args[0]
        if len(args) >= 2:
            self.term2 = args[1]
            self.complete = True
        assert isinstance(self.term1, Term) and \
                isinstance(self.term2, Term), f"invalid TmMod type: {self.to_coq()}"
    
    def to_coq(self):
        return CoqProof("T_Mod", children=[self.term1.to_coq(), 
                                           self.term2.to_coq(),
                                           proof_refl])
    
    def to_code(self):
        return f"{self.term1.to_code()} % {self.term2.to_code()}"
    
    def to_java(self, context={}):
        return f"{self.term1.to_java(context)} % {self.term2.to_java(context)}"

class TmNeg(Term):
    terms_need = ["Term"]
    def __init__(self, *args):
        self.term = TmUnk()
        if len(args) >= 1:
            self.term = args[0]
            self.complete = True
        assert isinstance(self.term, Term), f"invalid TmNeg type: {self.to_coq()}"
    
    def to_coq(self):
        return CoqProof("T_Neg", children=[self.term.to_coq(), proof_refl])
    
    def to_code(self):
        return f"-{self.term.to_code()}"
    
    def to_java(self, context={}):
        return f"-{self.term.to_java(context)}"

class TmPostInc(Term):
    terms_need = ["Term"]
    def __init__(self, *args):
        self.term = TmUnk()
        if len(args) >= 1:
            self.term = args[0]
            self.complete = True
        assert isinstance(self.term, Term), f"invalid TmPostInc type: {self.to_coq()}"
    
    def to_coq(self):
        return CoqProof("T_PostInc", children=[self.term.to_coq(), proof_refl])
    
    def to_code(self):
        return f"{self.term.to_code()}++"
    
    def to_java(self, context={}):
        return f"{self.term.to_java(context)}++"

class TmPostDec(Term):
    terms_need = ["Term"]
    def __init__(self, *args):
        self.term = TmUnk()
        if len(args) >= 1:
            self.term = args[0]
            self.complete = True
        assert isinstance(self.term, Term), f"invalid TmPostDec type: {self.to_coq()}"
    
    def to_coq(self):
        return CoqProof("T_PostDec", children=[self.term.to_coq(), proof_refl])
    
    def to_code(self):
        return f"{self.term.to_code()}--"
    
    def to_java(self, context={}):
        return f"{self.term.to_java(context)}--"

class TmPreInc(Term):
    terms_need = ["Term"]
    def __init__(self, *args):
        self.term = TmUnk()
        if len(args) >= 1:
            self.term = args[0]
            self.complete = True
        assert isinstance(self.term, Term), f"invalid TmPreInc type: {self.to_coq()}"
    
    def to_coq(self):
        return CoqProof("T_PreInc", children=[self.term.to_coq(), proof_refl])
    
    def to_code(self):
        return f"++{self.term.to_code()}"
    
    def to_java(self, context={}):
        return f"++{self.term.to_java(context)}"

class TmPreDec(Term):
    terms_need = ["Term"]
    def __init__(self, *args):
        self.term = TmUnk()
        if len(args) >= 1:
            self.term = args[0]
            self.complete = True
        assert isinstance(self.term, Term), f"invalid TmPreDec type: {self.to_coq()}"
    
    def to_coq(self):
        return CoqProof("T_PreDec", children=[self.term.to_coq(), proof_refl])
    
    def to_code(self):
        return f"--{self.term.to_code()}"
    
    def to_java(self, context={}):
        return f"--{self.term.to_java(context)}"

class TmBitAnd(Term):
    terms_need = ["Term", "Term"]
    def __init__(self, *args):
        self.term1 = TmUnk()
        self.term2 = TmUnk()
        if len(args) >= 1:
            self.term1 = args[0]
        if len(args) >= 2:
            self.term2 = args[1]
            self.complete = True
        assert isinstance(self.term1, Term) and \
                isinstance(self.term2, Term), f"invalid TmBitAnd type: {self.to_coq()}"
    
    def to_coq(self):
        return CoqProof("T_BitAnd", children=[self.term1.to_coq(), 
                                              self.term2.to_coq(), 
                                              proof_refl])
    
    def to_code(self):
        return f"{self.term1.to_code()} & {self.term2.to_code()}"
    
    def to_java(self, context={}):
        return f"{self.term1.to_java(context)} & {self.term2.to_java(context)}"

class TmBitOr(Term):
    terms_need = ["Term", "Term"]
    def __init__(self, *args):
        self.term1 = TmUnk()
        self.term2 = TmUnk()
        if len(args) >= 1:
            self.term1 = args[0]
        if len(args) >= 2:
            self.term2 = args[1]
            self.complete = True
        assert isinstance(self.term1, Term) and \
                isinstance(self.term2, Term), f"invalid TmBitOr type: {self.to_coq()}"
    
    def to_coq(self):
        return CoqProof("T_BitOr", children=[self.term1.to_coq(), 
                                             self.term2.to_coq(), 
                                             proof_refl])
    
    def to_code(self):
        return f"{self.term1.to_code()} | {self.term2.to_code()}"
    
    def to_java(self, context={}):
        return f"{self.term1.to_java(context)} | {self.term2.to_java(context)}"

class TmBitXor(Term):
    terms_need = ["Term", "Term"]
    def __init__(self, *args):
        self.term1 = TmUnk()
        self.term2 = TmUnk()
        if len(args) >= 1:
            self.term1 = args[0]
        if len(args) >= 2:
            self.term2 = args[1]
            self.complete = True
        assert isinstance(self.term1, Term) and \
                isinstance(self.term2, Term), f"invalid TmBitXor type: {self.to_coq()}"
    
    def to_coq(self):
        return CoqProof("T_BitXor", children=[self.term1.to_coq(), 
                                              self.term2.to_coq(), 
                                              proof_refl])
    
    def to_code(self):
        return f"{self.term1.to_code()} ^ {self.term2.to_code()}"
    
    def to_java(self, context={}):
        return f"{self.term1.to_java(context)} ^ {self.term2.to_java(context)}"

class TmBitNot(Term):
    terms_need = ["Term"]
    def __init__(self, *args):
        self.term1 = TmUnk()
        self.term2 = TmUnk()
        if len(args) >= 1:
            self.term1 = args[0]
        if len(args) >= 2:
            self.term2 = args[1]
            self.complete = True
        assert isinstance(self.term1, Term) and \
                isinstance(self.term2, Term), f"invalid TmBitNot type: {self.to_coq()}"
    
    def to_coq(self):
        return CoqProof("T_BitNot", children=[self.term.to_coq(), proof_refl])
    
    def to_code(self):
        return f"~{self.term.to_code()}"
    
    def to_java(self, context={}):
        return f"~{self.term.to_java(context)}"

class TmShiftL(Term):
    terms_need = ["Term", "Term"]
    def __init__(self, *args):
        self.term1 = TmUnk()
        self.term2 = TmUnk()
        if len(args) >= 1:
            self.term1 = args[0]
        if len(args) >= 2:
            self.term2 = args[1]
            self.complete = True
        assert isinstance(self.term1, Term) and \
                isinstance(self.term2, Term), f"invalid TmShiftL type: {self.to_coq()}"
    
    def to_coq(self):
        return CoqProof("T_ShiftL", children=[self.term1.to_coq(), 
                                              self.term2.to_coq()])
    
    def to_code(self):
        return f"{self.term1.to_code()} << {self.term2.to_code()}"
    
    def to_java(self, context={}):
        return f"{self.term1.to_java(context)} << {self.term2.to_java(context)}"

class TmShiftR(Term):
    terms_need = ["Term", "Term"]
    def __init__(self, *args):
        self.term1 = TmUnk()
        self.term2 = TmUnk()
        if len(args) >= 1:
            self.term1 = args[0]
        if len(args) >= 2:
            self.term2 = args[1]
            self.complete = True
        assert isinstance(self.term1, Term) and \
                isinstance(self.term2, Term), f"invalid TmShiftR type: {self.to_coq()}"
    
    def to_coq(self):
        return CoqProof("T_ShiftR", children=[self.term1.to_coq(), 
                                              self.term2.to_coq()])
    
    def to_code(self):
        return f"{self.term1.to_code()} >> {self.term2.to_code()}"
    
    def to_java(self, context={}):
        return f"{self.term1.to_java(context)} >> {self.term2.to_java(context)}"

class TmEq(Term):
    terms_need = ["Term", "Term"]
    def __init__(self, *args):
        self.term1 = TmUnk()
        self.term2 = TmUnk()
        if len(args) >= 1:
            self.term1 = args[0]
        if len(args) >= 2:
            self.term2 = args[1]
            self.complete = True
        assert isinstance(self.term1, Term) and \
                isinstance(self.term2, Term), f"invalid TmEq type: {self.to_coq()}"
    
    def to_coq(self):
        return CoqProof("T_Eq", children=[self.term1.to_coq(), 
                                          self.term2.to_coq(),
                                          proof_refl])
    
    def to_code(self):
        return f"{self.term1.to_code()} == {self.term2.to_code()}"
    
    def to_java(self, context={}):
        return f"{self.term1.to_java(context)} == {self.term2.to_java(context)}"

class TmNe(Term):
    terms_need = ["Term", "Term"]
    def __init__(self, *args):
        self.term1 = TmUnk()
        self.term2 = TmUnk()
        if len(args) >= 1:
            self.term1 = args[0]
        if len(args) >= 2:
            self.term2 = args[1]
            self.complete = True
        assert isinstance(self.term1, Term) and \
                isinstance(self.term2, Term), f"invalid TmNe type: {self.to_coq()}"
    
    def to_coq(self):
        return CoqProof("T_Ne", children=[self.term1.to_coq(), 
                                          self.term2.to_coq(),
                                            proof_refl])
    
    def to_code(self):
        return f"{self.term1.to_code()} != {self.term2.to_code()}"
    
    def to_java(self, context={}):
        return f"{self.term1.to_java(context)} != {self.term2.to_java(context)}"

class TmLt(Term):
    terms_need = ["Term", "Term"]
    def __init__(self, *args):
        self.term1 = TmUnk()
        self.term2 = TmUnk()
        if len(args) >= 1:
            self.term1 = args[0]
        if len(args) >= 2:
            self.term2 = args[1]
            self.complete = True
        assert isinstance(self.term1, Term) and \
                isinstance(self.term2, Term), f"invalid TmLt type: {self.to_coq()}"
    
    def to_coq(self):
        return CoqProof("T_Lt", children=[self.term1.to_coq(), 
                                          self.term2.to_coq(),
                                          proof_refl])
    
    def to_code(self):
        return f"{self.term1.to_code()} < {self.term2.to_code()}"
    
    def to_java(self, context={}):
        return f"{self.term1.to_java(context)} < {self.term2.to_java(context)}"

class TmLe(Term):
    terms_need = ["Term", "Term"]
    def __init__(self, *args):
        self.term1 = TmUnk()
        self.term2 = TmUnk()
        if len(args) >= 1:
            self.term1 = args[0]
        if len(args) >= 2:
            self.term2 = args[1]
            self.complete = True
        assert isinstance(self.term1, Term) and \
                isinstance(self.term2, Term), f"invalid TmLe type: {self.to_coq()}"
    
    def to_coq(self):
        return CoqProof("T_Le", children=[self.term1.to_coq(), 
                                          self.term2.to_coq(),
                                          proof_refl])
    
    def to_code(self):
        return f"{self.term1.to_code()} <= {self.term2.to_code()}"
    
    def to_java(self, context={}):
        return f"{self.term1.to_java(context)} <= {self.term2.to_java(context)}"

class TmGt(Term):
    terms_need = ["Term", "Term"]
    def __init__(self, *args):
        self.term1 = TmUnk()
        self.term2 = TmUnk()
        if len(args) >= 1:
            self.term1 = args[0]
        if len(args) >= 2:
            self.term2 = args[1]
            self.complete = True
        assert isinstance(self.term1, Term) and \
                isinstance(self.term2, Term), f"invalid TmGt type: {self.to_coq()}"
    
    def to_coq(self):
        return CoqProof("T_Gt", children=[self.term1.to_coq(), 
                                          self.term2.to_coq(),
                                          proof_refl])
    
    def to_code(self):
        return f"{self.term1.to_code()} > {self.term2.to_code()}"
    
    def to_java(self, context={}):
        return f"{self.term1.to_java(context)} > {self.term2.to_java(context)}"

class TmGe(Term):
    terms_need = ["Term", "Term"]
    def __init__(self, *args):
        self.term1 = TmUnk()
        self.term2 = TmUnk()
        if len(args) >= 1:
            self.term1 = args[0]
        if len(args) >= 2:
            self.term2 = args[1]
            self.complete = True
        assert isinstance(self.term1, Term) and \
                isinstance(self.term2, Term), f"invalid TmGe type: {self.to_coq()}"
    
    def to_coq(self):
        return CoqProof("T_Ge", children=[self.term1.to_coq(), 
                                          self.term2.to_coq(),
                                          proof_refl])
    
    def to_code(self):
        return f"{self.term1.to_code()} >= {self.term2.to_code()}"
    
    def to_java(self, context={}):
        return f"{self.term1.to_java(context)} >= {self.term2.to_java(context)}"

class TmAnd(Term):
    terms_need = ["Term", "Term"]
    def __init__(self, *args):
        self.term1 = TmUnk()
        self.term2 = TmUnk()
        if len(args) >= 1:
            self.term1 = args[0]
        if len(args) >= 2:
            self.term2 = args[1]
            self.complete = True
        assert isinstance(self.term1, Term) and \
                isinstance(self.term2, Term), f"invalid TmAnd type: {self.to_coq()}"
    
    def to_coq(self):
        return CoqProof("T_And", children=[self.term1.to_coq(), 
                                           self.term2.to_coq()])
    
    def to_code(self):
        return f"{self.term1.to_code()} && {self.term2.to_code()}"
    
    def to_java(self, context={}):
        return f"{self.term1.to_java(context)} && {self.term2.to_java(context)}"

class TmOr(Term):
    terms_need = ["Term", "Term"]
    def __init__(self, *args):
        self.term1 = TmUnk()
        self.term2 = TmUnk()
        if len(args) >= 1:
            self.term1 = args[0]
        if len(args) >= 2:
            self.term2 = args[1]
            self.complete = True
        assert isinstance(self.term1, Term) and \
                isinstance(self.term2, Term), f"invalid TmOr type: {self.to_coq()}"
    
    def to_coq(self):
        return CoqProof("T_Or", children=[self.term1.to_coq(), 
                                          self.term2.to_coq()])
    
    def to_code(self):
        return f"{self.term1.to_code()} || {self.term2.to_code()}"
    
    def to_java(self, context={}):
        return f"{self.term1.to_java(context)} || {self.term2.to_java(context)}"

class TmNot(Term):
    terms_need = ["Term"]
    def __init__(self, *args):
        self.term = TmUnk()
        if len(args) >= 1:
            self.term = args[0]
            self.complete = True
        assert isinstance(self.term, Term), f"invalid TmNot type: {self.to_coq()}"

    def to_coq(self):
        return CoqProof("T_Not", children=[self.term.to_coq()])
    
    def to_code(self):
        return f"!{self.term.to_code()}"
    
    def to_java(self, context={}):
        return f"!{self.term.to_java(context)}"

# Statement level
class StUnk(Statement):
    terms_need = []
    def __init__(self):
        self.complete = True
    def to_coq(self):
        return CoqProof("admit")
    def to_code(self):
        return "?"
    def to_java(self, context={}):
        return "?"
    
class StSkip(Statement):
    terms_need = []
    def __init__(self):
        self.complete = True
    def to_coq(self):
        return CoqProof("T_Skip")
    def to_code(self):
        return "skip"
    def to_java(self, context={}):
        return ""

class StDeclNoInit(Statement):
    terms_need = ["Type", "String"]
    def __init__(self, *args):
        self.ty = TyUnk()
        self.string = "StrUnk"
        if len(args) >= 1:
            self.ty = args[0]
        if len(args) >= 2:
            self.string = args[1]
            self.complete = True
        assert isinstance(self.ty, Type) and \
               isinstance(self.string, str), f"invalid StDeclNoInit type: {self.to_coq()}"
        
    def to_coq(self):
        return CoqProof("T_DeclNoInit", params={"T": self.ty.to_coq(), "x": f'"{self.string}"'})
    def to_code(self):
        return f"{self.string}: {self.ty.to_code()}"
    def to_java(self, context={}):
        typed_context = deepcopy(context)
        typed_context["concrete"] = True
        if "comma" in context and context["comma"]:
            # no typed_context here for parameters
            return f"{self.ty.to_java(context)} {self.string}"
        return f"{self.ty.to_java(typed_context)} {self.string};"

class StDeclInit(Statement):
    terms_need = ["Type", "String", "Term"]
    def __init__(self, *args):
        self.ty = TyUnk()
        self.string = "StrUnk"
        self.term = TmUnk()
        if len(args) >= 1:
            self.ty = args[0]
        if len(args) >= 2:
            self.string = args[1]
        if len(args) >= 3:
            self.term = args[2]
            self.complete = True
        assert isinstance(self.ty, Type) and \
               isinstance(self.string, str) and \
               isinstance(self.term, Term), f"invalid StDeclInit type: {self.to_coq()}"

    def to_coq(self):
        return CoqProof("T_DeclInit", 
                        params={"T": self.ty.to_coq(), "x": f'"{self.string}"'}, 
                        children=[self.term.to_coq(),proof_refl])
    def to_code(self):
        return f"{self.string}: {self.ty.to_code()} := {self.term.to_code()}"
    def to_java(self, context={}):
        typed_context = deepcopy(context)
        typed_context["concrete"] = True
        if "comma" in context and context["comma"]:
            # no typed_context here for parameters
            return f"{self.ty.to_java(context)} {self.string} = {self.term.to_java(context)}"
        return f"{self.ty.to_java(typed_context)} {self.string} = {self.term.to_java(context)};"

class StIf(Statement):
    terms_need = ["Term", "Statement"]
    def __init__(self, *args):
        self.term = TmUnk()
        self.statement = StUnk()
        if len(args) >= 1:
            self.term = args[0]
        if len(args) >= 2:
            self.statement = args[1]
            self.complete = True
        assert isinstance(self.term, Term) and \
               isinstance(self.statement, Statement), f"invalid StIf type: {self.to_coq()}"
        
    def to_coq(self):
        return CoqProof("T_If", children=[self.term.to_coq(), self.statement.to_coq()])
    def to_code(self):
        then_branch = self.statement.to_code()
        then_branch = addIndentation(then_branch)
        return f"if ({self.term.to_code()})\n{then_branch}\nend if"
    def to_java(self, context={}):
        then_branch = self.statement.to_java(context)
        then_branch = addIndentation(then_branch)
        return f"if ({self.term.to_java(context)}){{\n{then_branch}\n}}"

class StIfElse(Statement):
    terms_need = ["Term", "Statement", "Statement"]
    def __init__(self, *args):
        self.term = TmUnk()
        self.statement1 = StUnk()
        self.statement2 = StUnk()
        if len(args) >= 1:
            self.term = args[0]
        if len(args) >= 2:
            self.statement1 = args[1]
        if len(args) >= 3:
            self.statement2 = args[2]
            self.complete = True
        assert isinstance(self.term, Term) and \
               isinstance(self.statement1, Statement) and \
               isinstance(self.statement2, Statement), f"invalid StIfElse type: {self.to_coq()}"
        
    def to_coq(self):
        return CoqProof("T_IfElse", children=[self.term.to_coq(), 
                                              self.statement1.to_coq(), 
                                              self.statement2.to_coq()])
    
    def to_code(self):
        then_branch = self.statement1.to_code()
        else_branch = self.statement2.to_code()
        then_branch = addIndentation(then_branch)
        else_branch = addIndentation(else_branch)
        return f"if ({self.term.to_code()})\n{then_branch}\nelse\n{else_branch}\nend if"
    
    def to_java(self, context={}):
        then_branch = self.statement1.to_java(context)
        else_branch = self.statement2.to_java(context)
        then_branch = addIndentation(then_branch)
        else_branch = addIndentation(else_branch)
        return f"if ({self.term.to_java(context)}){{\n{then_branch}\n}} else {{\n{else_branch}\n}}"

class StWhile(Statement):
    terms_need = ["Term", "Statement"]
    def __init__(self, *args):
        self.term = TmUnk()
        self.statement = StUnk()
        if len(args) >= 1:
            self.term = args[0]
        if len(args) >= 2:
            self.statement = args[1]
            self.complete = True
        assert isinstance(self.term, Term) and \
               isinstance(self.statement, Statement), f"invalid StWhile type: {self.to_coq()}"
        
    def to_coq(self):
        return CoqProof("T_While", children=[self.term.to_coq(), self.statement.to_coq()])
    
    def to_code(self):
        body = self.statement.to_code()
        body = addIndentation(body)
        return f"while ({self.term.to_code()})\n{body}\nend while"
    
    def to_java(self, context={}):
        body = self.statement.to_java(context)
        body = addIndentation(body)
        return f"while ({self.term.to_java(context)}){{\n{body}\n}}"

class StDoWhile(Statement):
    terms_need = ["Statement", "Term"]
    def __init__(self, *args):
        self.statement = StUnk()
        self.term = TmUnk()
        if len(args) >= 1:
            self.statement = args[0]
        if len(args) >= 2:
            self.term = args[1]
            self.complete = True
        assert isinstance(self.statement, Statement) and \
               isinstance(self.term, Term), f"invalid StDoWhile type: {self.to_coq()}"
        
    def to_coq(self):
        return CoqProof("T_DoWhile", children=[self.statement.to_coq(), self.term.to_coq()])
    
    def to_code(self):
        body = self.statement.to_code()
        body = addIndentation(body)
        return f"do\n{body}\nend do\nwhile ({self.term.to_code()})"
    
    def to_java(self, context={}):
        body = self.statement.to_java(context)
        body = addIndentation(body)
        return f"do{{\n{body}\n}} while ({self.term.to_java(context)})"

class StFor(Statement):
    terms_need = ["Statement", "Term", "Term", "Statement"]
    def __init__(self, *args):
        self.statement1 = StUnk()
        self.cond_term = TmUnk()
        self.update_term = TmUnk()
        self.statement2 = StUnk()
        if len(args) >= 1:
            self.statement1 = args[0]
        if len(args) >= 2:
            self.cond_term = args[1]
        if len(args) >= 3:
            self.update_term = args[2]
        if len(args) >= 4:
            self.statement2 = args[3]
            self.complete = True
        assert isinstance(self.statement1, Statement) and \
               isinstance(self.cond_term, Term) and \
               isinstance(self.update_term, Term) and \
               isinstance(self.statement2, Statement), f"invalid StFor type: {self.to_coq()}"

    def to_coq(self):
        return CoqProof("T_For", children=[self.statement1.to_coq(), 
                                           self.cond_term.to_coq(), 
                                           self.update_term.to_coq(), 
                                           self.statement2.to_coq()])
    def to_code(self):
        init = self.statement1.to_code()
        body = self.statement2.to_code()
        condition = self.cond_term.to_code()
        update = self.update_term.to_code()
        body = addIndentation(body)
        return f"for ({init}; {condition}; {update})\n{body}\nend for"
    
    def to_java(self, context={}):
        comma_context = deepcopy(context)
        comma_context["comma"] = True
        init = self.statement1.to_java(comma_context)
        body = self.statement2.to_java(context)
        condition = self.cond_term.to_java(context)
        update = self.update_term.to_java(context)
        body = addIndentation(body)
        return f"for ({init}; {condition}; {update}){{\n{body}\n}}"

class StForeach(Statement):
    terms_need = ["Type", "String", "Term", "Statement"]
    def __init__(self, *args):
        self.ty = TyUnk()
        self.string = "StrUnk"
        self.term = TmUnk()
        self.statement = StUnk()
        if len(args) >= 1:
            self.ty = args[0]
        if len(args) >= 2:
            self.string = args[1]
        if len(args) >= 3:
            self.term = args[2]
        if len(args) >= 4:
            self.statement = args[3]
            self.complete = True
        assert isinstance(self.ty, Type) and \
               isinstance(self.string, str) and \
               isinstance(self.term, Term) and \
               isinstance(self.statement, Statement), f"invalid StForeach type: {self.to_coq()}"

    def to_coq(self):
        return CoqProof("T_Foreach", 
                        params={"T": self.ty.to_coq(), "x": f'"{self.string}"'}, 
                        children=[self.term.to_coq(), proof_refl, self.statement.to_coq()])
    
    def to_code(self):
        body = self.statement.to_code()
        body = addIndentation(body)
        return f"foreach ({self.ty.to_code()} {self.string} in {self.term.to_code()})\n{body}\nend foreach"
    
    def to_java(self, context={}):
        body = self.statement.to_java(context)
        body = addIndentation(body)
        return f"for ({self.ty.to_java(context)} {self.string} : {self.term.to_java(context)}){{\n{body}\n}}"

class StReturn(Statement):
    terms_need = ["Term"]
    def __init__(self, *args):
        self.term = TmUnk()
        if len(args) >= 1:
            self.term = args[0]
            self.complete = True
        assert isinstance(self.term, Term), f"invalid StReturn type: {self.to_coq()}"

    def to_coq(self):
        return CoqProof("T_Return", children=[self.term.to_coq(), proof_refl, proof_refl])
    
    def to_code(self):
        return f"return {self.term.to_code()}"
    
    def to_java(self, context={}):
        return f"return {self.term.to_java(context)};"

class StContinue(Statement):
    terms_need = []
    def __init__(self):
        self.complete = True
    def to_coq(self):
        return CoqProof("T_Continue")
    def to_code(self):
        return "continue"
    def to_java(self, context={}):
        return "continue;"

class StBreak(Statement):
    terms_need = []
    def __init__(self):
        self.complete = True
    def to_coq(self):
        return CoqProof("T_Break")
    def to_code(self):
        return "break"
    def to_java(self, context={}):
        return "break;"

class StExpression(Statement):
    terms_need = ["Term"]
    def __init__(self, *args):
        self.term = TmUnk()
        if len(args) >= 1:
            self.term = args[0]
            self.complete = True
        assert isinstance(self.term, Term), f"invalid StExpression type: {self.to_coq()}"
    def to_coq(self):
        return CoqProof("T_Expression", children=[self.term.to_coq()])
    def to_code(self):
        return self.term.to_code()
    def to_java(self, context={}):
        if "comma" in context and context["comma"]:
            return self.term.to_java(context)
        return self.term.to_java(context)+";"

class StConcat(Statement):
    terms_need = ["Statement", "Statement"]
    def __init__(self, *args):
        self.statement1 = StUnk()
        self.statement2 = StUnk()
        if len(args) >= 1:
            self.statement1 = args[0]
        if len(args) >= 2:
            self.statement2 = args[1]
            self.complete = True
        assert isinstance(self.statement1, Statement) and \
               isinstance(self.statement2, Statement), f"invalid StConcat type: {self.to_coq()}"
        
    def to_coq(self):
        return CoqProof("T_Concat", children=[self.statement1.to_coq(), self.statement2.to_coq()])
    
    def to_code(self):
        if self.statement2.to_code() == "skip":
            return self.statement1.to_code()
        else:
            return f"{self.statement1.to_code()};\n{self.statement2.to_code()}"
    
    def to_java(self, context={}):
        if self.statement2.to_java(context) == "":
            return self.statement1.to_java(context)
        else:
            if "comma" in context and context["comma"]:
                return f"{self.statement1.to_java(context)}, {self.statement2.to_java(context)}"
            return f"{self.statement1.to_java(context)}\n{self.statement2.to_java(context)}"

# Program level
class PgUnk(Program):
    terms_need = []
    def __init__(self):
        self.complete = True
    def to_coq(self):
        return CoqProof("admit")
    def to_code(self):
        return "?"
    def to_java(self, context={}):
        return "?"
    
class PgFieldDeclNoInit(Program):
    terms_need = ["String", "Type", "String"]
    def __init__(self, *args):
        self.modif = "StrUnk"
        self.ty = TyUnk()
        self.string = "StrUnk"
        if len(args) >= 1:
            self.modif = args[0]
        if len(args) >= 2:
            self.ty = args[1]
        if len(args) >= 3:
            self.string = args[2]
            self.complete = True
        assert isinstance(self.ty, Type) and \
               isinstance(self.modif, str) and \
               isinstance(self.string, str), f"invalid PgFieldDeclNoInit type: {self.to_coq()}"

    def to_coq(self):
        return CoqProof("T_FieldDeclNoInit", 
                        params={"modif": f'"{self.modif}"', "T": self.ty.to_coq(), "x": f'"{self.string}"'})
    def to_code(self):
        return f"[{self.modif}]\n{self.string}: {self.ty.to_code()}"
    
    def to_java(self, context={}):
        typed_context = deepcopy(context)
        typed_context["concrete"] = True
        return f"{self.modif} {self.ty.to_java(typed_context)} {self.string};"

class PgFieldDeclInit(Program):
    terms_need = ["String", "Type", "String", "Term"]
    def __init__(self, *args):
        self.modif = "StrUnk"
        self.ty = TyUnk()
        self.string = "StrUnk"
        self.term = TmUnk()
        if len(args) >= 1:
            self.modif = args[0]
        if len(args) >= 2:
            self.ty = args[1]
        if len(args) >= 3:
            self.string = args[2]
        if len(args) >= 4:
            self.term = args[3]
            self.complete = True
        assert isinstance(self.ty, Type) and \
               isinstance(self.modif, str) and \
               isinstance(self.string, str) and \
               isinstance(self.term, Term), f"invalid PgFieldDeclInit type: {self.to_coq()}"

    def to_coq(self):
        return CoqProof("T_FieldDeclInit", 
                        params={"modif": f'"{self.modif}"', "T": self.ty.to_coq(), "x": f'"{self.string}"'}, 
                        children=[self.term.to_coq(), proof_refl])
    
    def to_code(self):
        return f"[{self.modif}]\n{self.string}: {self.ty.to_code()} := {self.term.to_code()}"
    
    def to_java(self, context={}):
        typed_context = deepcopy(context)
        typed_context["concrete"] = True
        return f"{self.modif} {self.ty.to_java(typed_context)} {self.string} = {self.term.to_java(context)};"

class PgMethodDecl(Program):
    terms_need = ["String", "Type", "String", "Statement", "Statement"]
    def __init__(self, *args):
        self.modif = "StrUnk"
        self.ty = TyUnk()
        self.string = "StrUnk"
        self.param = StUnk()
        self.statement = StUnk()
        if len(args) >= 1:
            self.modif = args[0]
        if len(args) >= 2:
            self.ty = args[1]
        if len(args) >= 3:
            self.string = args[2]
        if len(args) >= 4:
            self.param = args[3]
        if len(args) >= 5:
            self.statement = args[4]
            self.complete = True
        assert isinstance(self.ty, Type) and \
               isinstance(self.string, str) and \
               isinstance(self.modif, str) and \
               isinstance(self.param, Statement) and \
               isinstance(self.statement, Statement), f"invalid PgMethodDecl type({type(self.statement)}): {self.statement.to_code()}"
        
    def to_coq(self):
        return CoqProof("T_MethodDecl", 
                        params={"modif": f'"{self.modif}"', "T": self.ty.to_coq(), "m": f'"{self.string}"'}, 
                        children=[self.param.to_coq(), proof_refl, self.statement.to_coq()])
    
    def to_code(self):
        body = self.statement.to_code()
        body = addIndentation(body)
        param = self.param.to_code().replace(";\n", ", ")
        return f"[{self.modif}]\n{self.string}({param}): {self.ty.to_code()}\n{body}\nend method"
    
    def to_java(self, context={}):
        body = self.statement.to_java(context)
        body = addIndentation(body)
        comma_context = deepcopy(context)
        comma_context["comma"] = True
        typed_context = deepcopy(context)
        typed_context["wrapper"] = True
        typed_context["concrete"] = True
        param = self.param.to_java(comma_context).replace("\n", "")
        return f"{self.modif} {self.ty.to_java(typed_context)} {self.string}({param}){{\n{body}\n}}"

class PgConstructorDecl(Program):
    terms_need = ["Statement", "Statement"]
    def __init__(self, *args):
        self.param = StUnk()
        self.statement = StUnk()
        if len(args) >= 1:
            self.param = args[0]
        if len(args) >= 2:
            self.statement = args[1]
            self.complete = True
        assert isinstance(self.param, Statement) and \
               isinstance(self.statement, Statement), f"invalid PgConstructorDecl type: {self.to_coq()}"

    def to_coq(self):
        return CoqProof("T_ConstructorDecl", children=[self.param.to_coq(), proof_refl, self.statement.to_coq()])

    def to_code(self):
        body = self.statement.to_code()
        body = addIndentation(body)
        return f"constructor({self.param.to_code()})\n{body}\nend constructor"
    
    def to_java(self, context={}):
        body = self.statement.to_java(context)
        body = addIndentation(body)
        return f"{context['class_name']}({self.param.to_java(context)}){{\n{body}\n}}"

class PgStatement(Program):
    terms_need = ["Statement"]
    def __init__(self, *args):
        self.statement = StUnk()
        if len(args) >= 1:
            self.statement = args[0]
            self.complete = True
        assert isinstance(self.statement, Statement), f"invalid PgStatement type: {self.to_coq()}"
    def to_coq(self):
        return CoqProof("T_Statement", children=[self.statement.to_coq()])
    def to_code(self):
        return self.statement.to_code()
    def to_java(self, context={}):
        return self.statement.to_java(context)
    
class PgClassDecl(Program):
    terms_need = ["String", "Program"]
    def __init__(self, *args):
        self.name = "StrUnk"
        self.component = PgUnk()
        if len(args) >= 1:
            self.name = args[0]
        if len(args) >= 2:
            self.component = args[1]
            self.complete = True
        assert isinstance(self.component, Program) and \
               isinstance(self.name, str), f"invalid PgClassDecl type: {self.to_coq()}"

    def to_coq(self):
        return CoqProof("T_ClassDecl", params={"name": f'"{self.name}"'}, 
                        children=[self.component.to_coq(), proof_refl])
    def to_code(self):
        component_string = self.component.to_code()
        component_string = addIndentation(component_string)
        return f"class {self.name}\n{component_string}\nend class"
    
    def to_java(self, context={}):
        named_context = deepcopy(context)
        named_context["class_name"] = self.name
        component_string = self.component.to_java(named_context)
        component_string = addIndentation(component_string)
        return f"class {self.name}{{\n{component_string}\n}}"
    
class PgConcat(Program):
    terms_need = ["Program", "Program"]
    def __init__(self, *args):
        self.program1 = PgUnk()
        self.program2 = PgUnk()
        if len(args) >= 1:
            self.program1 = args[0]
        if len(args) >= 2:
            self.program2 = args[1]
            self.complete = True
        assert isinstance(self.program1, Program) and \
               isinstance(self.program2, Program), f"invalid PgConcat type: {self.to_coq()}"
        
    def to_coq(self):
        return CoqProof("T_ProgramConcat", children=[self.program1.to_coq(), self.program2.to_coq()])
    
    def to_code(self):
        return f"{self.program1.to_code()}\n{self.program2.to_code()}"
    
    def to_java(self, context={}):
        return f"{self.program1.to_java(context)}\n{self.program2.to_java(context)}"

tactic_name_vocab = term_name_vocab + statement_name_vocab + program_name_vocab
predefined_vocab = type_name_vocab + tactic_name_vocab + class_name_vocab + method_name_vocab
tokenizer.add_tokens(predefined_vocab)
real_path = os.path.dirname(os.path.realpath(__file__))
rule_dict = pickle.load(open(real_path+"/datas/grammart5rules.pkl", "rb"))
for name in predefined_vocab:
    if name not in rule_dict:
        rule_dict[name] = len(rule_dict)
# for name in class_name_vocab:
#     terms_need_dict[name] = []
for name in rule_dict:
    if name not in terms_need_dict:
        terms_need_dict[name] = ["StringOrEnd"]
terms_need_dict[tokenizer.eos_token] = []

def token_type(name):
    if name in type_name_vocab:
        return "Type"
    elif name in term_name_vocab:
        return "Term"
    elif name in statement_name_vocab:
        return "Statement"
    elif name in program_name_vocab:
        return "Program"
    else:
        return "String"

## Detokenization part

class PNode():
    def __init__(self, content):
        self.completed = False
        if token_type(content) != "String": # Type / Tactic
            self.content = name2cls[content]()
            self.type = token_type(content)
            self.terms_needed_list = terms_need_dict[content]
            if self.content.complete:
                self.completed = True
        else: # String
            self.content = content
            self.type = "String"
            self.terms_needed_list = ["String"]

    @property
    def terms_needed(self):
        return len(self.terms_needed_list)
    
    def complete(self, terms):
        assert len(terms)<=self.terms_needed, f"complete terms exceeded: {self.content.__class__.__name__} \
        /{[term.content for term in terms]}"
        terms_need_truc = self.terms_needed_list[:len(terms)]
        def type_match(real_type, type_need):
            if ("String" in type_need) and real_type == "String":
                return True
            return real_type == type_need
        assert all([type_match(term.type, need) for term, need in zip(terms, terms_need_truc)]), f"complete terms type error: \
        {self.content.__class__.__name__} / {[term.content for term in terms]}"

        if self.type == "String":
            self.completed = True
            if len(terms) > 0:
                self.content += terms[0].content
            else:
                self.content += '+StrUnk'
        else: # Type / Tactic
            terms = [term.content for term in terms]
            self.content = self.content.__class__(*terms)
            if self.content.complete:
                self.completed = True

    def to_string(self):
        if self.type == "String":
            return self.content
        return str(self.content.to_coq())

# unify the right most complete terms into a partial terms to get a complete term 
# partial_mode means we can still generate the proof even if it's not complete
def unify(stack, partial_mode=False):
    # nothing to unify
    if len(stack) == 0 or (stack[-1].completed == False and not partial_mode):
        return

    # find the rightmost partial-proof
    pindex = len(stack) - 1
    while pindex >= 0 and stack[pindex].completed == True:
        pindex -= 1
    if pindex < 0:
        return

    pterm = stack[pindex]
    # no enough terms to complete the partial-proof
    if len(stack) - 1 - pindex < pterm.terms_needed:
        if not partial_mode:
            return
        else: # try to complete a proof term when its params are not enough
            try:
                pterm.complete(stack[pindex + 1 :])
                pterm.completed = True
            except Exception as e:
                pterm.completed = False
                return
    else: # complete the partial-proof
        pterm.complete(stack[pindex + 1 :])

    del stack[pindex + 1 :]
    unify(stack, partial_mode)

# Convert tokensequence back into Coqproof
def detokenization(tokens):
    # if there is no tokens at all
    if len(tokens) == 0:
        return PgUnk()
    stack = []
    for token in tokens:
        # token is a Type / Tactic
        if token_type(token) != "String":
            stack.append(PNode(token))
        else: # token is a string
            tmp_str = PNode(token.replace("Ġ", " "))
            # if the string is in a type definition Eg. TyGeneric1 List TyInt
            if stack[-1].type == "Type" and stack[-1].completed == False:
                tmp_str.completed = True
            # token stands for end of a string
            if token == tokenizer.eos_token:
                # empty string "" is a special case
                if stack[-1].type == "Term" and "TmString" in str(type(stack[-1].content)):
                    stack[-1].complete([PNode("")])
                # else stack[-1] is a string
                else:
                    assert stack[-1].type == "String", "Encounter eos token when a string is needed"
                stack[-1].completed = True
            else:
                stack.append(tmp_str)
        unify(stack)

    # tokens can't form a complete proof
    if len(stack) > 1 or (len(stack) == 1 and stack[0].completed == False):
        unify(stack, partial_mode=True)

    if len(stack) != 1:  # string / type not complete or wrong sequence
        print(f"Can't unify stack: stack has length {len(stack)}")
        return None
    return stack[0].content

def detokenization_wrapper(tokens):
    try:
        return detokenization(tokens)
    except Exception as e:
        print(f"Error in detokenization: {e}")
        # traceback.print_exc()
        print(tokens)
        return None

def extract_context(coqview):
# Extract useful context from coqview, e.g.
#     1 focused goal (shelved: 9)
#   ============================
#   {|
#     var_type :=
#       "isNotPrime" |--> <( Int -> Bool )>;
#       return' |--> <( Bool )>; "n" |--> <( Int )>; empty_map;
#     class_type := StrMap.empty ClassType
#   |} |-- ?tm1 \in ?T1
#   from which we get {"isNotPrime": "Int -> Bool", "return": "Bool", "n": "Int"}
# or
#   1 focused goal (shelved: 2)
#   ============================
#   empty_context |- ?p --> ?Gamma
#   from which we get empty
    if "empty_context" in coqview:
        context = "\n Context: empty"
    else:
        vartype_start = coqview.find("var_type :=")+len("var_type :=")
        vartype_end = coqview.find("empty_map")
        vartype_content = coqview[vartype_start:vartype_end].strip()
        vartype_items = [item.strip() for item in vartype_content.split(";") if item.strip()]
        context = "\n Context: "
        for item in vartype_items:
            name, type = item.split("|-->")
            name = name.replace('"', "").replace("'", "").strip()
            type = type.replace("<(", "").replace(")>", "").strip()
            context += f"{name.strip()} : {type.strip()}\n"
    return context


print("...Program model loaded")
if __name__ == "__main__":
    # Type
    print(f"type_name_vocab: {type_name_vocab}")
    print(f"term_name_vocab: {term_name_vocab}")
    print(f"statement_name_vocab: {statement_name_vocab}")
    print(f"program_name_vocab: {program_name_vocab}")
    # print(f"terms_need_dict: {terms_need_dict}")
    # print(f"name2cls: {name2cls}")
