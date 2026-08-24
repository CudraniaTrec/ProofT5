"""
<program> := <command> ... <command>

<command> := Inductive <Name> = <name> <type> | ... | <name> <type>;     
                                                               /* Define inductive data types */
          |  <Name> = <type>;                                  /* Define type abbrevations */  
          |  <name> = <term>;                                  /* Define functions or constants */

<type>    := {<type>, ..., <type>}                             /* Product types */
          |  <type> -> <type>                                  /* Arrow types */
          |  Reframe <type>                                    /* Annotated types */
          |  Unit | Int | Bool | <Name>                        /* Basic types or defined inductive types */

<term>    := unit | <integer> | true | false | <name>          /* Basic values or variables*/
          |  + | - | * | / | < | <= | > | >= | == | and | or | not       
                                                               /* Builtin operators */
          |  <term> <term>                                     /* Function applications */
          |  \<name>:<type>. <term>                            /* Lambda expressions */
          |  fix <term>                                        /* Recursions defined using the fix point */
          |  let <name> = <term> in <term>                     /* Let bindings */
          |  if <term> then <term> else <term>                 /* Branch expressions */
          |  {<term>, ..., <term>}                             /* Tuple constructors */
          |  <term>.<integer>                                  /* Tuple projections */
          |  match <term> with <pattern> -> <term> | ... | <pattern> -> <term> end 
                                                               /* Pattern matching */
          |  rewrite <term> | label <term> | unlabel <term>    /* Annotated terms */

<pattern> := _ | <name>                                        /* Matching without conditions */
          |  <name> <pattern>                                  /* Matching constructors */
          |  {<pattern>, ..., <pattern>}                       /* Matching for tuples*/
"""

terms_need_dict = {}
name2cls = {}
class_w_type = {
    "program": ["ProgramCons", "ProgramNil", "ProgramUnk"], # 3
    "command": ["CommandInductive", "CommandType", "CommandTerm", "CommandUnk"], # 4
    "tydef": ["TypeDefCons", "TypeDef", "TypeDefUnk"], # 3
    "type": ["TypeUser", "TypeUnit", "TypeInt", "TypeBool", "TypeArrow", "TypeReframe", "TypeProd", "TypeUnk"], # 8
    "term": ["TermUnit", "TermInt", "TermTrue", "TermFalse", "TermVar", "TermOp", "TermApp", "TermLambda", "TermFix", "TermLet", "TermIf", "TermTuple", "TermProj", "TermMatch", "TermRewrite", "TermLabel", "TermUnlabel", "TermParenthesis", "TermUnk"], # 20
    "matchcase": ["MatchCase", "MatchCaseCons", "MatchCaseUnk"], # 3
    "pattern": ["PatternDefault", "PatternVar", "PatternConstructor", "PatternTuple", "PatternUnk"], # 5
}

from copy import copy, deepcopy
from tqdm import tqdm
import json, os, shutil, subprocess, re, traceback, pickle
from transformers import AutoTokenizer

repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
tokenizer_path = os.path.join(repo_root, "Utils/data/tokenizer.pkl")
if not os.path.exists(tokenizer_path):
    tokenizer_path = "/data4/hzc/ProofT5/Utils/data/tokenizer.pkl"
try:
    with open(tokenizer_path, 'rb') as f:
        tokenizer = pickle.load(f)
except (ModuleNotFoundError, TypeError):
    from transformers.models.roberta.tokenization_roberta import RobertaTokenizer
    tokenizer = RobertaTokenizer(
        os.path.join(repo_root, "Utils", "models", "codet5-small", "vocab.json"),
        os.path.join(repo_root, "Utils", "models", "codet5-small", "merges.txt"),
    )
    for rel_path in [("coq_model", "new_tokens.json"), ("SuFu", "new_tokens.json")]:
        token_file = os.path.join(repo_root, *rel_path)
        if os.path.exists(token_file):
            with open(token_file, "r") as f:
                tokenizer.add_tokens(json.load(f))

def run_sufu_executor(executor_path, test_file_path):
    ocamlrun_path = shutil.which("ocamlrun")
    cmd = [ocamlrun_path, executor_path, test_file_path] if ocamlrun_path else [executor_path, test_file_path]
    return subprocess.run(cmd, capture_output=True, text=True)

def get_sufu_surface_executor():
    candidates = [
        os.path.join(repo_root, "SuFu/SuFu/surface/f"),
        os.path.join(repo_root, "SuFu/surface/f"),
        "/data4/hzc/ProofT5/SuFu/SuFu/surface/f",
    ]
    return next((path for path in candidates if os.path.exists(path)), candidates[0])

# internal class for type checking
class TypeCtx:
    def __init__(self):
        self.ctx = {} # map from term name to SufuType
        self.ty_ctx = {"PList":SufuType("PList")} # map from type name to list of SufuType
        self.labelable = False # whether we can (un)label a term
        self.subject = None # match subject type
        self.constructors = {} # map from constructor name to args type and return type

    def to_str(self):
        return f"ctx {self.ctx} ty_ctx {self.ty_ctx} constructors {self.constructors} label {self.labelable} match {self.subject}"

class SufuType:
    def __init__(self, ty, *args):
        self.ty = ty # string
        self.args = args # list of SufuType
    
    def __eq__(self, other):
        if not isinstance(other, SufuType):
            return False
        if self.ty == "Unk" or other.ty == "Unk":
            return True 
        if self.ty != other.ty:
            return False
        if len(self.args) != len(other.args):
            return False
        for i in range(len(self.args)):
            if self.args[i] != other.args[i]:
                return False
        return True
    
    def __ne__(self, other):
        return not self.__eq__(other)
    
    def __repr__(self):
        if self.ty == "Arrow":
            return f"{self.args[0]} -> {self.args[1]}"
        elif self.ty == "Reframe":
            return f"Reframe {self.args[0]}"
        elif self.ty == "Prod":
            return f"{{{self.args[0]},{self.args[1]}}}"
        else:
            return f"{self.ty}"
        
    def apply(self, arg):
        if self.ty == "Unk":
            return self
        assert self.ty == "Arrow", f"{self.ty} can't be applied"
        assert self.args[0] == arg, f"Apply error {self.args[0]} != {arg.ty}"
        return self.args[1]
    
    def apply_fix(self):
        if self.ty == "Unk":
            return self
        assert self.ty == "Arrow", f"fixpoint arg {self.ty} not a function type"
        assert self.args[0] == self.args[1], f"fixpoint type mismatch: {self.args[0]} != {self.args[1]}"
        return self.args[0]
    
    def proj(self, index):
        if self.ty == "Unk":
            return self
        elif index == 1:
            if self.ty == "Prod":
                return self.args[0]
            else:
                return self
        else:
            assert self.ty == "Prod", f"{self.ty} can't be projected"
            return self.args[1].proj(index-1)
    
    def is_scalar(self):
        if self.ty in ["Unit", "Int", "Bool"]:
            return True
        elif self.ty == "Prod":
            return self.args[0].is_scalar() and self.args[1].is_scalar()
        elif self.ty == "Reframe":
            return self.args[0].is_base()
        else:
            return False
    
    def is_base(self):
        if self.ty == "Prod":
            return self.args[0].is_base() and self.args[1].is_base()
        elif self.ty == "Reframe":
            return self.args[0].is_base()
        else:
            return self.ty != "Arrow"
    
    def unlabel(self):
        if self.ty == "Unk":
            return self
        assert self.ty == "Reframe", f"{self.ty} can't be unlabeled"
        return self.args[0]
    
    def label(self):
        if self.ty == "Unk":
            return self
        assert self.is_base(), f"{self.ty} can't be labeled"
        return SufuType("Reframe", self)

    def rewrite(self):
        if self.ty == "Unk":
            return self
        assert self.is_scalar(), f"{self.ty} can't be rewritten"
        return self
    
    def is_tuple(self):
        return self.ty == "Prod"
    
    def to_type_class(self):
        if self.ty == "Unit":
            return TypeUnit()
        elif self.ty == "Int":
            return TypeInt()
        elif self.ty == "Bool":
            return TypeBool()
        elif self.ty == "Arrow":
            return TypeArrow(self.args[0].to_type_class(), self.args[1].to_type_class())
        elif self.ty == "Reframe":
            return TypeReframe(self.args[0].to_type_class())
        elif self.ty == "Prod":
            return TypeProd(self.args[0].to_type_class(), self.args[1].to_type_class())
        else:
            return TypeUser(self.ty)
    
    def tokenize(self):
        return self.to_type_class().tokenize()

# sufu ast node
class AstNode(type):
    def __init__(cls, name, bases, dct):
        super().__init__(name, bases, dct)
        tname = name

        terms_need = dct["terms_need"]
        terms_need_dict[tname] = terms_need
        args_name = dct["args_name"]
        name2cls[tname] = cls

        origin_init = cls.__init__
        def new_init(self, *args, **kwargs):
            assert len(terms_need)>=len(args), f"args length too long for {tname}: {[class_type(arg) for arg in args]}"
            self.incomplete_field_id = 0
            for i in range(len(terms_need)):
                if i >= len(args):
                    setattr(self, args_name[i], findUnk[terms_need[i]])
                else:
                    assert class_type(args[i]) == terms_need[i], f"actual type: {class_type(args[i])} != target type: {terms_need[i]}, args[i]({type(args[i])}):{args[i].to_str({})}"
                    arg = args[i]
                    # Direct constructors are used by the tree-sitter reader
                    # with already-complete, plain strings.  Incremental beam
                    # construction instead starts with an empty field and
                    # later calls set_incomplete_field with BPE pieces.  The
                    # old code applied the BPE-only `value_complete` rule to
                    # both paths, so every parsed identifier/integer remained
                    # marked incomplete and the offline type checker silently
                    # skipped whole commands.
                    if isinstance(arg, str) and arg:
                        arg = arg.replace('Ġ', '')
                    setattr(self, args_name[i], arg)
                    if (
                        (isinstance(arg, str) and bool(arg))
                        or value_complete(arg)
                        or (tname == "TypeUser" and arg in predefined_type)
                    ):
                        self.incomplete_field_id +=1
            origin_init(self)
        cls.__init__ = new_init

        def get_incomplete_field(self):
            return getattr(self, args_name[self.incomplete_field_id])
        cls.get_incomplete_field = get_incomplete_field

        def set_incomplete_field(self, value):
            value_origin = value
            if isinstance(value, str):
                value = value.replace('Ġ', '')
            setattr(self, args_name[self.incomplete_field_id], value)
            if value_complete(value_origin):
                self.incomplete_field_id += 1
        cls.set_incomplete_field = set_incomplete_field

        def incomplete(self):
            return self.incomplete_field_id < len(args_name)
        cls.incomplete = incomplete

        def tokenize(self):
            tokens = [tname]
            for i in range(len(args_name)):
                f = getattr(self, args_name[i])
                if isinstance(f, str):
                    ftokens = tokenizer.tokenize(' '+f)[::-1] #encounter Ġ means end
                else:
                    ftokens = f.tokenize()
                tokens+=ftokens
            return tokens
        # if cls doesn't have tokenize, add it
        if not hasattr(cls, "tokenize"):
            cls.tokenize = tokenize
        
        def extract_ctx(self):
            ctx = self.type_check(TypeCtx())
            ret = []
            for key in ctx.ty_ctx:
                if isinstance(ctx.ty_ctx[key], SufuType):
                    ret += tokenizer.tokenize(key)+ ctx.ty_ctx[key].tokenize() + [tokenizer.sep_token]
            for key in ctx.ctx:
                if isinstance(ctx.ctx[key], SufuType):
                    ret += tokenizer.tokenize(key)+ ctx.ctx[key].tokenize() + [tokenizer.sep_token]
            for key in ctx.constructors:
                if isinstance(ctx.constructors[key], tuple):
                    ret += tokenizer.tokenize(key) + ctx.constructors[key][0].tokenize() + ctx.constructors[key][1].tokenize() + [tokenizer.sep_token]
            if ctx.subject:
                ret += tokenizer.tokenize("subject") + ctx.subject.tokenize() + [tokenizer.sep_token]
            if ctx.labelable:
                ret += tokenizer.tokenize("label")
            else:
                ret += tokenizer.tokenize("unlabel")
            return ret
        cls.extract_ctx = extract_ctx

# type_check returns tctx
class ProgramCons(metaclass=AstNode):
    # command | program
    ty = "program"
    terms_need = ["command", "program"]
    args_name = ["cmd", "prog"]

    def to_str(self, ctx):
        return f"{self.cmd.to_str(ctx)}\n{self.prog.to_str(ctx)}"

    def type_check(self, tctx):
        new_tctx = self.cmd.type_check(tctx)
        return self.prog.type_check(new_tctx)

class ProgramNil(metaclass=AstNode):
    # ;
    ty = "program"
    terms_need = []
    args_name = []

    def to_str(self, ctx):
        return ""

    def type_check(self, tctx):
        return tctx

class ProgramUnk(metaclass=AstNode):
    # ??
    ty = "program"
    terms_need = []
    args_name = []

    def to_str(self, ctx):
        return "??"

    def type_check(self, tctx):
        return tctx

# type_check returns tctx
class CommandInductive(metaclass=AstNode):
    # Inductive name = tydef
    ty = "command"
    terms_need = ["string", "tydef"]
    args_name = ["name", "tydef"]

    def to_str(self, ctx):
        return f"Inductive {self.name} = {self.tydef.to_str(ctx)};"

    def type_check(self, tctx):
        if self.incomplete():
            return tctx
        tctx.ty_ctx[self.name] = SufuType(self.name)
        tydef = self.tydef.type_check(tctx)
        for constructor in tydef:
            tctx.constructors[constructor] = (tydef[constructor], SufuType(self.name))
            tctx.ctx[constructor] = SufuType("Arrow", tydef[constructor], SufuType(self.name))
        return tctx

class CommandType(metaclass=AstNode):
    # name = ty
    ty = "command"
    terms_need = ["string", "type"]
    args_name = ["name", "ty_"]

    def to_str(self, ctx):
        return f"{self.name} = {self.ty_.to_str(ctx)};"
    
    def type_check(self, tctx):
        if self.incomplete():
            return tctx
        tydef = self.ty_.type_check(tctx)
        tctx.ty_ctx[self.name] = tydef
        return tctx

class CommandTerm(metaclass=AstNode):
    # name = term
    ty = "command"
    terms_need = ["string", "term"]
    args_name = ["name", "term"]

    def to_str(self, ctx):
        return f"{self.name} = {self.term.to_str(ctx)};"
    
    def type_check(self, tctx):
        if self.incomplete():
            return tctx
        term_ty = self.term.type_check(tctx)
        tctx.ctx[self.name] = term_ty
        return tctx

class CommandUnk(metaclass=AstNode):
    # ??
    ty = "command"
    terms_need = []
    args_name = []

    def to_str(self, ctx):
        return "??"
    
    def type_check(self, tctx):
        return tctx

# type_check returns {name1: sufuty1, name2: sufuty2, ...}
class TypeDef(metaclass=AstNode):
    # name ty
    ty = "tydef"
    terms_need = ["string", "type"]
    args_name = ["name", "ty_"]

    def to_str(self, ctx):
        return f"{self.name} {self.ty_.to_str(ctx)}"

    def type_check(self, tctx):
        if self.incomplete():
            return {}
        return {self.name: self.ty_.type_check(tctx)}

class TypeDefCons(metaclass=AstNode):
    # tydef | tydef
    ty = "tydef"
    terms_need = ["tydef", "tydef"]
    args_name = ["tydef1", "tydef2"]

    def to_str(self, ctx):
        return f"{self.tydef1.to_str(ctx)} | {self.tydef2.to_str(ctx)}"
    
    def type_check(self, tctx):
        tydef1 = self.tydef1.type_check(tctx)
        tydef2 = self.tydef2.type_check(tctx)
        return {**tydef1, **tydef2}

class TypeDefUnk(metaclass=AstNode):
    # ??
    ty = "tydef"
    terms_need = []
    args_name = []

    def to_str(self, ctx):
        return "??"
    
    def type_check(self, tctx):
        return {}

# type_check returns SufuType   
class TypeUser(metaclass=AstNode):
    # name
    ty = "type"
    terms_need = ["string"]
    args_name = ["name"]

    def to_str(self, ctx):
        return self.name
    
    def type_check(self, tctx):
        if self.incomplete():
            return SufuType("Unk")
        assert self.name in tctx.ty_ctx, f"{self.name} not in ty_ctx"
        return tctx.ty_ctx[self.name]
    
    def tokenize(self):
        return [self.name]
    
class TypeUnit(metaclass=AstNode):
    # Unit
    ty = "type"
    terms_need = []
    args_name = []

    def to_str(self, ctx):
        return "Unit"
    
    def type_check(self, tctx):
        return SufuType("Unit")

class TypeInt(metaclass=AstNode):
    # Int
    ty = "type"
    terms_need = []
    args_name = []

    def to_str(self, ctx):
        return "Int"

    def type_check(self, tctx):
        return SufuType("Int")

class TypeBool(metaclass=AstNode):
    # Bool
    ty = "type"
    terms_need = []
    args_name = []

    def to_str(self, ctx):
        return "Bool"
    
    def type_check(self, tctx):
        return SufuType("Bool")

class TypeArrow(metaclass=AstNode):
    # ty -> ty
    ty = "type"
    terms_need = ["type", "type"]
    args_name = ["ty1", "ty2"]

    def to_str(self, ctx):
        return f"{self.ty1.to_str(ctx)} -> {self.ty2.to_str(ctx)}"
    
    def type_check(self, tctx):
        ty1 = self.ty1.type_check(tctx)
        ty2 = self.ty2.type_check(tctx)
        return SufuType("Arrow", ty1, ty2)

class TypeReframe(metaclass=AstNode):
    # Reframe ty
    ty = "type"
    terms_need = ["type"]
    args_name = ["ty_"]

    def to_str(self, ctx):
        return f"Compress {self.ty_.to_str(ctx)}"

    def type_check(self, tctx):
        return SufuType("Reframe", self.ty_.type_check(tctx))

class TypeProd(metaclass=AstNode):
    # {ty, ..., ty}
    ty = "type"
    terms_need = ["type", "type"]
    args_name = ["ty1", "ty2"]

    def to_str(self, ctx):
        new_ctx = copy(ctx)
        new_ctx["curly_brackets"] = True
        ty1 = self.ty1.to_str(new_ctx)
        if isinstance(self.ty2, TypeProd):
            new_ctx["curly_brackets"] = False
        ty2 = self.ty2.to_str(new_ctx)
        if "curly_brackets" in ctx and ctx["curly_brackets"]==False:
            return f"{ty1}, {ty2}"
        else:
            return f"{{{ty1}, {ty2}}}"
    
    def type_check(self, tctx):
        ty1 = self.ty1.type_check(tctx)
        ty2 = self.ty2.type_check(tctx)
        return SufuType("Prod", ty1, ty2)

class TypeUnk(metaclass=AstNode):
    # ??
    ty = "type"
    terms_need = []
    args_name = []

    def to_str(self, ctx):
        return "??"
    
    def type_check(self, tctx):
        return SufuType("Unk")

# type_check returns SufuType
class TermUnit(metaclass=AstNode):
    # unit
    ty = "term"
    terms_need = []
    args_name = []

    def to_str(self, ctx):
        return "unit"
    
    def type_check(self, tctx):
        return SufuType("Unit")

class TermInt(metaclass=AstNode):
    # integer
    ty = "term"
    terms_need = ["string"]
    args_name = ["int"]

    def to_str(self, ctx):
        return self.int
    
    def type_check(self, tctx):
        return SufuType("Int")

class TermTrue(metaclass=AstNode):
    # true
    ty = "term"
    terms_need = []
    args_name = []

    def to_str(self, ctx):
        return "true"
    
    def type_check(self, tctx):
        return SufuType("Bool")

class TermFalse(metaclass=AstNode):
    # false
    ty = "term"
    terms_need = []
    args_name = []

    def to_str(self, ctx):
        return "false"
    
    def type_check(self, tctx):
        return SufuType("Bool")

class TermVar(metaclass=AstNode):
    # name
    ty = "term"
    terms_need = ["string"]
    args_name = ["name"]

    def to_str(self, ctx):
        return self.name
    
    def type_check(self, tctx):
        if self.incomplete():
            return SufuType("Unk")
        assert self.name in tctx.ctx, f"{self.name} not in ctx"
        return tctx.ctx[self.name]


_PATH_TERM_CLASSES = {
    "TermUnit",
    "TermInt",
    "TermTrue",
    "TermFalse",
    "TermVar",
    "TermTuple",
    "TermProj",
    "TermParenthesis",
}
_APP_TERM_CLASSES = _PATH_TERM_CLASSES | {
    "TermLabel",
    "TermUnlabel",
    "TermRewrite",
    "TermApp",
    "TermFix",
    "TermOp",
}


def _surface_path_term(term, ctx):
    rendered = term.to_str(ctx)
    if type(term).__name__ in _PATH_TERM_CLASSES:
        return rendered
    return f"({rendered})"


def _surface_app_term(term, ctx):
    rendered = term.to_str(ctx)
    if type(term).__name__ in _APP_TERM_CLASSES:
        return rendered
    return f"({rendered})"

class TermOp(metaclass=AstNode):
    # + | - | * | / | < | <= | > | >= | == | and | or | not
    ty = "term"
    terms_need = ["string"]
    args_name = ["op"]
    def to_str(self, ctx):
        return self.op
    
    def type_check(self, tctx):
        if self.op in ["+", "-", "*", "/"]:
            return SufuType("Arrow", SufuType("Int"), SufuType("Arrow", SufuType("Int"), SufuType("Int")))
        elif self.op in ["<", "<=", ">", ">=", "=="]:
            return SufuType("Arrow", SufuType("Int"), SufuType("Arrow", SufuType("Int"), SufuType("Bool")))
        elif self.op in ["and", "or"]:
            return SufuType("Arrow", SufuType("Bool"), SufuType("Arrow", SufuType("Bool"), SufuType("Bool")))
        elif self.op == "not":
            return SufuType("Arrow", SufuType("Bool"), SufuType("Bool"))
        else:
            assert self.incomplete(), f"{self.op} not in + - * / < <= > >= == and or not"
            return SufuType("Unk")

class TermApp(metaclass=AstNode):
    # term term
    ty = "term"
    terms_need = ["term", "term"]
    args_name = ["term1", "term2"]

    def to_str(self, ctx):
        # AppTerm accepts an AppTerm on the left but only a PathTerm on the
        # right.  Preserve operator syntax (`+ x y`, not the invalid `(+) x`)
        # while adding parentheses exactly when a generated argument is not a
        # PathTerm, e.g. `sort (unlabel tmp)`.
        return f"{_surface_app_term(self.term1, ctx)} {_surface_path_term(self.term2, ctx)}"
    
    def type_check(self, tctx):
        func_ty = self.term1.type_check(tctx)
        arg_ty = self.term2.type_check(tctx)
        return func_ty.apply(arg_ty)

class TermLambda(metaclass=AstNode):
    # \name:ty. term
    ty = "term"
    terms_need = ["string", "type", "term"]
    args_name = ["name", "ty_", "term"]

    def to_str(self, ctx):
        return f"\\{self.name}:{self.ty_.to_str(ctx)}. {self.term.to_str(ctx)}"
    
    def type_check(self, tctx):
        if self.incomplete():
            return SufuType("Unk")
        ty_binder = self.ty_.type_check(tctx)
        new_tctx = deepcopy(tctx)
        new_tctx.ctx[self.name] = ty_binder
        ty_val = self.term.type_check(new_tctx)
        return SufuType("Arrow", ty_binder, ty_val)

class TermFix(metaclass=AstNode):
    # fix term
    ty = "term"
    terms_need = ["term"]
    args_name = ["term"]

    def to_str(self, ctx):
        return f"fix {_surface_path_term(self.term, ctx)}"
    
    def type_check(self, tctx):
        ty_fix = self.term.type_check(tctx)
        return ty_fix.apply_fix()

class TermLet(metaclass=AstNode):
    # let name = term in term
    ty = "term"
    terms_need = ["string", "term", "term"]
    args_name = ["name", "val", "term"]

    def to_str(self, ctx):
        return f"let {self.name} = {self.val.to_str(ctx)} in {self.term.to_str(ctx)}"
    
    def type_check(self, tctx):
        if self.incomplete():
            return SufuType("Unk")
        ty_val = self.val.type_check(tctx)
        new_tctx = deepcopy(tctx)
        new_tctx.ctx[self.name] = ty_val
        return self.term.type_check(new_tctx)

class TermIf(metaclass=AstNode):
    # if term then term else term
    ty = "term"
    terms_need = ["term", "term", "term"]
    args_name = ["cond", "then_", "else_"]

    def to_str(self, ctx):
        return f"if {self.cond.to_str(ctx)} then {self.then_.to_str(ctx)} else {self.else_.to_str(ctx)}"
    
    def type_check(self, tctx):
        ty_cond = self.cond.type_check(tctx)
        ty_then = self.then_.type_check(tctx)
        ty_else = self.else_.type_check(tctx)
        assert ty_cond == SufuType("Bool"), f"If condition {ty_cond} is not Bool"
        assert ty_then == ty_else, f"If branch {ty_then} and {ty_else} are not same"
        return ty_then

class TermTuple(metaclass=AstNode):
    # {term, ..., term}
    ty = "term"
    terms_need = ["term", "term"]
    args_name = ["term1", "term2"]

    def to_str(self, ctx):
        new_ctx = copy(ctx)
        new_ctx["curly_brackets"] = True
        term1 = self.term1.to_str(new_ctx)
        if isinstance(self.term2, TermTuple):
            new_ctx["curly_brackets"] = False
        term2 = self.term2.to_str(new_ctx)
        if "curly_brackets" in ctx and ctx["curly_brackets"]==False:
            return f"{term1}, {term2}"
        else:
            return f"{{{term1}, {term2}}}"
    
    def type_check(self, tctx):
        ty_term1 = self.term1.type_check(tctx)
        ty_term2 = self.term2.type_check(tctx)
        return SufuType("Prod", ty_term1, ty_term2)

class TermProj(metaclass=AstNode):
    # term.integer
    ty = "term"
    terms_need = ["term", "string"]
    args_name = ["term", "int"]

    def to_str(self, ctx):
        return f"{_surface_path_term(self.term, ctx)}.{self.int}"

    def type_check(self, tctx):
        if self.incomplete():
            return SufuType("Unk")
        index = int(self.int)
        ty_term = self.term.type_check(tctx)
        return ty_term.proj(index)

class TermMatch(metaclass=AstNode):
    # match term with matchcase
    ty = "term"
    terms_need = ["term", "matchcase"]
    args_name = ["term", "matchcase"]

    def to_str(self, ctx):
        return f"match {self.term.to_str(ctx)} with {self.matchcase.to_str(ctx)} end"

    def type_check(self, tctx):
        ty_term = self.term.type_check(tctx)
        new_tctx = deepcopy(tctx)
        new_tctx.subject = ty_term
        ty_matchcase = self.matchcase.type_check(new_tctx)
        return ty_matchcase

class TermRewrite(metaclass=AstNode):
    # rewrite term
    ty = "term"
    terms_need = ["term"]
    args_name = ["term"]

    def to_str(self, ctx):
        return f"align {_surface_path_term(self.term, ctx)}"
    
    def type_check(self, tctx):
        new_tctx = deepcopy(tctx)
        new_tctx.labelable = True
        return self.term.type_check(new_tctx).rewrite()

class TermLabel(metaclass=AstNode):
    # label term
    ty = "term"
    terms_need = ["term"]
    args_name = ["term"]

    def to_str(self, ctx):
        return f"label {_surface_path_term(self.term, ctx)}"
    
    def type_check(self, tctx):
        assert tctx.labelable, "Label is not allowed here"
        return self.term.type_check(tctx).label()

class TermUnlabel(metaclass=AstNode):
    # unlabel term
    ty = "term"
    terms_need = ["term"]
    args_name = ["term"]

    def to_str(self, ctx):
        return f"unlabel {_surface_path_term(self.term, ctx)}"
    
    def type_check(self, tctx):
        assert tctx.labelable, "Unlabel is not allowed here"
        return self.term.type_check(tctx).unlabel()

class TermParenthesis(metaclass=AstNode):
    # (term)
    ty = "term"
    terms_need = ["term"]
    args_name = ["term"]

    def to_str(self, ctx):
        return f"({self.term.to_str(ctx)})"

    def type_check(self, tctx):
        return self.term.type_check(tctx)

class TermUnk(metaclass=AstNode):
    # ??
    ty = "term"
    terms_need = []
    args_name = []

    def to_str(self, ctx):
        return "??"

    def type_check(self, tctx):
        return SufuType("Unk")

# type_check returns SufuType
class MatchCase(metaclass=AstNode):
    # pattern -> term
    ty = "matchcase"
    terms_need = ["pattern", "term"]
    args_name = ["pattern", "term"]

    def to_str(self, ctx):
        return f"{self.pattern.to_str(ctx)} -> {self.term.to_str(ctx)}"
    
    def type_check(self, tctx):
        new_tctx = self.pattern.type_check(tctx)
        return self.term.type_check(new_tctx)

class MatchCaseCons(metaclass=AstNode):
    # matchcase | matchcase
    ty = "matchcase"
    terms_need = ["matchcase", "matchcase"]
    args_name = ["matchcase1", "matchcase2"]

    def to_str(self, ctx):
        return f"{self.matchcase1.to_str(ctx)} | {self.matchcase2.to_str(ctx)}"
    
    def type_check(self, tctx):
        ty_matchcase1 = self.matchcase1.type_check(tctx)
        ty_matchcase2 = self.matchcase2.type_check(tctx)
        assert ty_matchcase1 == ty_matchcase2, f"Matchcase {ty_matchcase1} and {ty_matchcase2} are not same"
        return ty_matchcase1 

class MatchCaseUnk(metaclass=AstNode):
    # ??
    ty = "matchcase"
    terms_need = []
    args_name = []

    def to_str(self, ctx):
        return "??"
    
    def type_check(self, tctx):
        return SufuType("Unk")

class PatternDefault(metaclass=AstNode):
    # _
    ty = "pattern"
    terms_need = []
    args_name = []

    def to_str(self, ctx):
        return "_"
    
    def type_check(self, tctx):
        return tctx

class PatternVar(metaclass=AstNode):
    # name
    ty = "pattern"
    terms_need = ["string"]
    args_name = ["name"]

    def to_str(self, ctx):
        return self.name
    
    def type_check(self, tctx):
        if self.incomplete():
            return tctx
        new_tctx = deepcopy(tctx)
        new_tctx.ctx[self.name] = tctx.subject
        return new_tctx

class PatternConstructor(metaclass=AstNode):
    # name pattern
    ty = "pattern"
    terms_need = ["string", "pattern"]
    args_name = ["constructor", "pattern"]

    def to_str(self, ctx):
        return f"{self.constructor} {self.pattern.to_str(ctx)}"

    def type_check(self, tctx):
        if self.incomplete():
            return tctx
        tyarg, tyret = tctx.constructors[self.constructor]
        assert tyret == tctx.subject, f"Constructor {self.constructor} is not applicable to {tctx.subject}"
        new_tctx = deepcopy(tctx)
        new_tctx.subject = tyarg
        return self.pattern.type_check(new_tctx)

class PatternTuple(metaclass=AstNode):
    # {pattern, ..., pattern}
    ty = "pattern"
    terms_need = ["pattern", "pattern"]
    args_name = ["pattern1", "pattern2"]

    def to_str(self, ctx):
        new_ctx = copy(ctx)
        new_ctx["curly_brackets"] = True
        pattern1 = self.pattern1.to_str(new_ctx)
        if isinstance(self.pattern2, PatternTuple):
            new_ctx["curly_brackets"] = False
        pattern2 = self.pattern2.to_str(new_ctx)
        if "curly_brackets" in ctx and ctx["curly_brackets"]==False:
            return f"{pattern1}, {pattern2}"
        else:
            return f"{{{pattern1}, {pattern2}}}"
    
    def type_check(self, tctx):
        if self.incomplete():
            return tctx
        assert tctx.subject.is_tuple(), f"Pattern {self.pattern1} and {self.pattern2} are not tuple to {tctx.subject}"
        sub1, sub2 = tctx.subject.args
        new_tctx = deepcopy(tctx)
        new_tctx.subject = sub1
        new_tctx = self.pattern1.type_check(new_tctx)
        new_tctx.subject = sub2
        new_tctx = self.pattern2.type_check(new_tctx)
        return new_tctx
        
class PatternUnk(metaclass=AstNode):
    # ??
    ty = "pattern"
    terms_need = []
    args_name = []

    def to_str(self, ctx):
        return "??"
    
    def type_check(self, tctx):
        return tctx

# return an xxxUnk() object according to class_type
findUnk = {
    "program": ProgramUnk(),
    "command": CommandUnk(),
    "tydef": TypeDefUnk(),
    "type": TypeUnk(),
    "term": TermUnk(),
    "matchcase": MatchCaseUnk(),
    "pattern": PatternUnk(),
    "string": ""
}

# judge the class_type of the object
def class_type(obj):
    if hasattr(obj, "ty"):
        return obj.ty
    else:
        return "string"

# add predefined words to tokenizer
def get_path(relative_path):
    path = os.path.split(os.path.realpath(__file__))[0]
    return os.path.join(path, relative_path)
predefined_class = []
for t in class_w_type:
    predefined_class += class_w_type[t]
assert set(predefined_class) == set(name2cls.keys()), f"Predefined class inconsistant with name2cls:\n{set(predefined_class)} / \n{set(name2cls.keys())}"
assert set(predefined_class) == set(terms_need_dict.keys()), f"Predefined class inconsistant with terms_need_dict:\n{set(predefined_class)} / \n{set(terms_need_dict.keys())}"
with open(get_path("info.json"), 'r') as f:
    predefined_type = list(json.load(f)["types"].keys())
print(f"Predefined length: {len(predefined_class)}(class) + {len(predefined_type)}(type)")
with open(get_path("new_tokens.json"), "w") as f:
    json.dump(predefined_class + predefined_type, f, indent=4)
with open(get_path("sufu.json"), 'r') as f:
    sufu_progs = json.load(f)
code_token_len = [len(tokenizer.tokenize(prog['code'])) for prog in sufu_progs]

# incremental parsing
def class_type_str(obj_name):
    if obj_name in predefined_class:
        return [class_type(name2cls[obj_name])]
    elif obj_name in predefined_type:
        return ["type", "string"]
    else:
        return ["string"]

def value_complete(value): # if a value(str/astnode) is complete
    if isinstance(value, str):
        return bool(value) and value[0]=='Ġ'
    else:
        return not value.incomplete()
        
def complete(node, terms_need, token):  
    assert node.incomplete(), f"{node} is already complete"
    f = node.get_incomplete_field()
    if isinstance(f, str): # should implement a str
        assert terms_need[0] == "string", f"{token} is not a string"
        f = token+f
        node.set_incomplete_field(f)
        if f[0] == 'Ġ':
            terms_need = terms_need[1:]
        return node, terms_need
    else: # should implement an astnode
        if 'Unk' in type(f).__name__:
            if isinstance(f, TypeUnk) and token in predefined_type:
                f = TypeUser(token)
                terms_need = terms_need[1:]
            else:
                assert token in predefined_class, f"{token} is not a predefined class"
                f = name2cls[token]()
                terms_need = terms_need_dict[token] + terms_need[1:]
            node.set_incomplete_field(f)
            return node, terms_need
        else:
            f, terms_need = complete(f, terms_need, token)
            node.set_incomplete_field(f)
            return node, terms_need

def detokenize(tokens):            
    assert tokens[0] == "ProgramCons", f"invalid tokens: {tokens}"
    node = ProgramCons()
    terms_need = terms_need_dict["ProgramCons"]
    type_ctxes = [] # len(type_ctxes) = len(tokens) - 1
    for token in tokens[1:]:
        assert terms_need[0] in class_type_str(token), f"{token} mismatch the term needed: {terms_need}"
        type_ctxes.append(node.extract_ctx())
        node, terms_need = complete(node, terms_need, token)
        if len(terms_need) == 0:
            break
    assert len(terms_need) == 0 and not node.incomplete(), f"{node} is not complete"
    assert len(type_ctxes) == len(tokens) - 1, f"len(type_ctxes) ({len(type_ctxes)}) != len(tokens) - 1({len(tokens) - 1})"
    return node, type_ctxes

# tree-sitter parser
from tree_sitter import Language, Parser
SUFU_LANGUAGE = Language(get_path("tree-sitter-sufu/sufu.so"), "sufu")
parser = Parser()
parser.set_language(SUFU_LANGUAGE)
def visit(node, info):
    if hasattr(node, "type"):
        match node.type:
            case "source_file":
                ret = ProgramNil()
                for n in node.children[-1::-1]:
                    ret = ProgramCons(visit(n, info), ret)
                return ret
            # command
            case "inductive_command":
                type_name = visit(node.children[1], info)
                tydef = visit(node.children[3], info)
                return CommandInductive(type_name, tydef)
            case "type_abbreviation_command":
                type_name = visit(node.children[0], info)
                typedef = visit(node.children[2], info)
                return CommandType(type_name, typedef)
            case "definition_command":
                term_name = visit(node.children[0], info)
                term_def = visit(node.children[2], info)
                return CommandTerm(term_name, term_def)
            # typedef
            case "typedef_single":
                constructor = visit(node.children[0], info)
                base_type = visit(node.children[1], info)
                return TypeDef(constructor, base_type)
            case "typedef_cons":
                ret = visit(node.children[-1], info)
                for n in node.children[-3::-2]:
                    ret = TypeDefCons(visit(n, info), ret)
                return ret
            # type
            case "type_product":
                assert node.child_count >= 5, f"type product: {node.sexp()}"
                ret = visit(node.children[-2], info)
                for n in node.children[-4::-2]:
                    ret = TypeProd(visit(n, info), ret)
                return ret
            case "type_arrow":
                return TypeArrow(visit(node.children[0], info), visit(node.children[2], info))
            case "type_reframe":
                return TypeReframe(visit(node.children[1], info))
            case "type_inductive":
                return TypeUser(visit(node.children[0], info))
            case "type_unit":
                return TypeUnit()
            case "type_int":
                return TypeInt()
            case "type_bool":
                return TypeBool()
            case "type_parenthesized":
                return visit(node.children[1], info)
            # term
            case "term_unit":
                return TermUnit()
            case "term_integer":
                start, end = node.start_byte, node.end_byte
                content = info["code"][start:end]
                content = str(int(content))
                return TermInt(content)
            case "term_bool":
                start, end = node.start_byte, node.end_byte
                content = info["code"][start:end]
                if content == "true":
                    return TermTrue()
                else:
                    return TermFalse()
            case "term_var":
                start, end = node.start_byte, node.end_byte
                content = info["code"][start:end]
                return TermVar(content)
            case "term_app":
                term1 = visit(node.children[0], info)
                term2 = visit(node.children[1], info)
                return TermApp(term1, term2)
            case "term_lambda":
                binder = visit(node.children[1], info)
                ty = visit(node.children[3], info)
                body = visit(node.children[5], info)
                return TermLambda(binder, ty, body)
            case "term_fix":
                term = visit(node.children[1], info)
                return TermFix(term)
            case "term_let":
                binder = visit(node.children[1], info)
                value = visit(node.children[3], info)
                body = visit(node.children[5], info)
                return TermLet(binder, value, body)
            case "term_if":
                cond = visit(node.children[1], info)
                then_ = visit(node.children[3], info)
                else_ = visit(node.children[5], info)
                return TermIf(cond, then_, else_)
            case "term_tuple":
                assert node.child_count >= 5, f"term tuple: {node.sexp()}"
                ret = visit(node.children[-2], info)
                for n in node.children[-4::-2]:
                    ret = TermTuple(visit(n, info), ret)
                return ret
            case "term_proj":
                base_term = visit(node.children[0], info)
                index = visit(node.children[2], info).to_str({})
                return TermProj(base_term, index)
            case "term_match":
                term = visit(node.children[1], info)
                match_cases = visit(node.children[3], info)
                return TermMatch(term, match_cases)
            case "term_rewrite":
                term = visit(node.children[1], info)
                return TermRewrite(term)
            case "term_label":
                term = visit(node.children[1], info)
                return TermLabel(term)
            case "term_unlabel":
                term = visit(node.children[1], info)
                return TermUnlabel(term)
            case "term_op":
                start, end = node.start_byte, node.end_byte
                content = info["code"][start:end]
                return TermOp(content)
            case "term_parenthesized":
                return TermParenthesis(visit(node.children[1], info))
            case "match_case":
                ret = visit(node.children[-2], info)
                for n in node.children[-4::-2]:
                    ret = MatchCaseCons(visit(n, info), ret)
                return ret
            case "match_case_single":
                pattern, term = visit(node.children[0], info), visit(node.children[2], info)
                return MatchCase(pattern, term)
            case "pattern_default":
                return PatternDefault()
            case "pattern_var":
                start, end = node.start_byte, node.end_byte
                content = info["code"][start:end]
                return PatternVar(content)
            case "pattern_tuple":
                assert node.child_count >= 5, f"pattern tuple: {node.sexp()}"
                ret = visit(node.children[-2], info)
                for n in node.children[-4::-2]:
                    ret = PatternTuple(visit(n, info), ret)
                return ret
            case "pattern_constructor":
                constructor = visit(node.children[0], info)
                args = visit(node.children[1], info)
                return PatternConstructor(constructor, args)
            case "identifier":
                start, end = node.start_byte, node.end_byte
                return info["code"][start:end]
            case "Identifier":
                start, end = node.start_byte, node.end_byte
                return info["code"][start:end]
            case _:
                assert False, "unknown node type: " + node.type
    else:
        assert False, f"unknown node type({type(node)}): {node.to_sexp()}"

# check parser/type checker/tokenizer
def replace_ptree(code):
    lines = [l.strip() for l in code.splitlines() if l.strip()]
    for i in range(len(lines)):
        if lines[i].startswith("Inductive PTree"):
            if lines[i+1].startswith("Inductive PList"):
                lines[i] = lines[i][:-1]
                lines[i+1] = lines[i+1].replace("Inductive", 'with')
                break
    return "\n".join(lines)
def check_corr(code, prog, testid=0):
    code = replace_ptree(code)
    full_code = code+"\n"+prog["tests"]
    test_file_path = f"SuFu/test{testid}.f"
    with open(test_file_path, "w") as f:
        f.write(full_code)
    interpreter_path = get_sufu_surface_executor()
    res = run_sufu_executor(interpreter_path, test_file_path)
    if res.stdout.strip() == prog["output"].strip():
        return True
    else:
        print(f"{res.stdout}\n{'='*50}\n{prog["output"]}")
        return False

def check_one(prog, is_name=False):
    if is_name:
        with open("sufu.json", 'r') as f:
            progs = json.load(f)
        prog = [p for p in progs if p["file_name"] == prog][0]
    code = prog["code"]
    if is_name: # debug mode
        print(code)
        with open("tree-sitter-sufu/example-file", 'w') as f:
            f.write(code)
    node = parser.parse(bytes(code, "utf8")).root_node
    sufu_node = visit(node, {"code": code})
    sufu_node.type_check(TypeCtx())
    tokens = sufu_node.tokenize()
    tokens = tokenizer.convert_ids_to_tokens(tokenizer.convert_tokens_to_ids(tokens))
    sufu_node, type_ctxes = detokenize(tokens)
    new_code = sufu_node.to_str({})
    if check_corr(new_code, prog):
        lib_node = parser.parse(bytes(prog["lib_code"], "utf8")).root_node
        lib_code_tokens = visit(lib_node, {"code": prog["lib_code"]}).tokenize()[:-1] # remove last ProgramNil
        assert lib_code_tokens == tokens[:len(lib_code_tokens)], f"libcode tokens mistatch: {lib_code_tokens}\n{tokens}"
        return tokens, lib_code_tokens, type_ctxes
    else:
        assert False, f"check_corr failed"

def check_all():
    error_cnt = 0
    dataset = []
    dataset_typectx = []
    with open("sufu.json", 'r') as f:
        progs = json.load(f)
    for prog in tqdm(progs):
        try:
            tokens, lib_tokens, type_ctxes = check_one(prog)
            data = {
                "file_name": prog["file_name"],
                "nl": tokenizer.encode(prog["desc"]),
                "nl_raw": f"**{prog["desc"]}**",
                "rulelist": [1]+tokenizer.convert_tokens_to_ids(tokens)+[2],
                "prefix": tokenizer.convert_tokens_to_ids(lib_tokens),
                "prefix_raw": prog["lib_code"],
                "postfix": tokenizer.convert_tokens_to_ids(tokens[len(lib_tokens):]),
                "postfix_raw": prog["task_code"],
                "code": prog["code"],
                "tests": prog["tests"],
                "output": prog["output"],
            }
            dataset.append(data)
            new_data = deepcopy(data)
            encoded_type_ctxes = [tokenizer.convert_tokens_to_ids(tc) for tc in type_ctxes]
            new_data["coqview"] = encoded_type_ctxes
            dataset_typectx.append(new_data)
        except Exception as e:
            error_cnt += 1
            print(prog["file_name"])
            print(e)
            traceback.print_exc()
    print(f"error count: {error_cnt}")
    # plot distribution
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(2, 3, figsize=(18, 10))
    axes = axes.flatten()  # 将二维 axes 转为一维便于遍历
    data_list = [
        ([len(d["nl"]) for d in dataset], 'NL Length', 'blue'),
        ([len(d["rulelist"]) for d in dataset], 'Rulelist Length', 'green'),
        ([len(d["prefix"]) for d in dataset], 'Prefix Length', 'orange'),
        ([len(d["rulelist"]) - len(d["prefix"]) for d in dataset], 'Postfix Length', 'red'),
        ([max([len(tc) for tc in d["coqview"]]) for d in dataset_typectx], 'Type Context Length', 'purple'),
    ]
    for ax, (data, label, color) in zip(axes, data_list):
        ax.hist(data, bins=50, color=color, alpha=0.7, edgecolor='black')
        ax.set_title(label)
        ax.set_xlabel('Length')
        ax.set_ylabel('Frequency')
        ax.grid(True, linestyle='--', alpha=0.5)
    for i in range(len(data_list), len(axes)):
        fig.delaxes(axes[i])
    plt.tight_layout()
    plt.savefig("length_distribution_clear.png")
    print(f"""
max nl langth: {max([len(d["nl"]) for d in dataset])}, min nl langth: {min([len(d["nl"]) for d in dataset])}, avg nl langth: {sum([len(d["nl"]) for d in dataset])/len(dataset)}
max rulelist length: {max([len(d["rulelist"]) for d in dataset])}, min rulelist length: {min([len(d["rulelist"]) for d in dataset])}, avg rulelist length: {sum([len(d["rulelist"]) for d in dataset])/len(dataset)}
max prefix length: {max([len(d["prefix"]) for d in dataset])}, min prefix length: {min([len(d["prefix"]) for d in dataset])}, avg prefix length: {sum([len(d["prefix"]) for d in dataset])/len(dataset)}
max postfix length: {max([len(d["rulelist"])-len(d["prefix"]) for d in dataset])}, min postfix length: {min([len(d["rulelist"])-len(d["prefix"]) for d in dataset])}, avg postfix length: {sum([len(d["rulelist"])-len(d["prefix"]) for d in dataset])/len(dataset)}
max type_ctx length: {max([len(tc) for d in dataset_typectx for tc in d["coqview"]])}, min type_ctx length: {min([len(tc) for d in dataset_typectx for tc in d["coqview"]])}, avg type_ctx length: {sum([len(tc) for d in dataset_typectx for tc in d["coqview"]])/len([tc for d in dataset_typectx for tc in d["coqview"]])}
max code token length: {max(code_token_len)}, min code token length: {min(code_token_len)}, avg code token length: {sum(code_token_len)/len(code_token_len)}
""")
    config = {
        "max_nl_len": max([len(d["nl"]) for d in dataset]),
        "max_code_len": max([len(d["rulelist"])-len(d["prefix"]) for d in dataset]),
        "max_coqview_len": max([len(tc) for d in dataset_typectx for tc in d["coqview"]]),
        "CodeLen": max([len(d["rulelist"]) for d in dataset]),
    }
    import random
    random.seed(2025) 
    random.shuffle(dataset)
    random.seed(2025) 
    random.shuffle(dataset_typectx)
    dump_data(dataset, config, "../Utils/data/sufucoq", dump_t5=True)
    dump_data(dataset, config, "../Utils/data/sufugrammar")
    dump_data(dataset_typectx, config, "../Utils/data/sufucoqview")

def dump_data(dataset, config, dump_data_path="../Utils/data/sufucoq", dump_t5=False):
    train_set = dataset[:int(len(dataset)*0.8)]
    test_set = dataset[int(len(dataset)*0.8):]
    json.dump(train_set, open(f"{dump_data_path}/train.json", "w"))
    json.dump(test_set, open(f"{dump_data_path}/test.json", "w"))
    pickle.dump(train_set, open(f"{dump_data_path}/train.pkl", "wb"))
    pickle.dump(test_set, open(f"{dump_data_path}/test.pkl", "wb"))
    pickle.dump(tokenizer, open(f"{dump_data_path}/tokenizer.pkl", "wb"))
    pickle.dump(tokenizer.get_vocab(), open(f"{dump_data_path}/rules.pkl", "wb"))
    print(f"dump {len(train_set)} train and {len(test_set)} test data to {dump_data_path}")
    if dump_t5:
        new_datas = []
        for data in train_set:
            new_data = {
                "task_id": data["file_name"],
                "prompt": f"{data["nl_raw"]}\n{data['prefix_raw']}",
                "code": data["code"],
                "postfix": data["rulelist"][len(data["prefix"]):-1], # remove start/end token
                "tests": data["tests"],
                "output": data["output"],
                "type": "train"
            }
            new_datas.append(new_data)
        for data in test_set:
            new_data = {
                "task_id": data["file_name"],
                "prompt": f"{data["nl_raw"]}\n{data['prefix_raw']}",
                "code": data["code"],
                "postfix": data["postfix_raw"],
                "tests": data["tests"],
                "output": data["output"],
                "type": "test"
            }
            new_datas.append(new_data)
        with open("../t5_llm/data/sufu_t5.json", "w") as f:
            json.dump(new_datas, f, indent=4)

        
        new_datas_codeproof = []
        special_tokens = {
            "additional_special_tokens": ["<code>", "</code>", "<proof>", "</proof>"]
        }
        tokenizer.add_special_tokens(special_tokens)
        pickle.dump(tokenizer, open(f"../t5_llm/data/tokenizer.pkl", "wb"))
        pickle.dump(tokenizer.get_vocab(), open(f"../t5_llm/data/rules.pkl", "wb"))
        for data in train_set:
            new_data = {
                "task_id": data["file_name"],
                "prompt": f"{data["nl_raw"]}\n{data['prefix_raw']}",
                "code": data["code"],
                "proof": data['rulelist'][1:-1], # remove start/end token
                "postfix": data["postfix_raw"],
                "tests": data["tests"],
                "output": data["output"],
                "type": "train"
            }
            new_datas_codeproof.append(new_data)
        for data in test_set:
            new_data = {
                "task_id": data["file_name"],
                "prompt": f"{data["nl_raw"]}\n{data['prefix_raw']}",
                "code": data["code"],
                "proof": data['rulelist'][1:-1], # remove start/end token
                "postfix": data["postfix_raw"],
                "tests": data["tests"],
                "output": data["output"],
                "type": "test"
            }
            new_datas_codeproof.append(new_data)
        with open("../t5_llm/data/sufu_t5_codeproof.json", "w") as f:
            json.dump(new_datas_codeproof, f, indent=4)

    with open(f"{dump_data_path}/config.json", "r") as f:
        new_config = json.load(f)
    for key in config:
        new_config[key] = config[key]
    with open(f"{dump_data_path}/config.json", "w") as f:
        json.dump(new_config, f, indent=4)
          
if __name__ == "__main__":
    with open("sufu.json", 'r') as f:
        progs = json.load(f)
    # t, lt, tc = check_one("incre-tests-synduce-ptree-mul", True)
    check_all()
