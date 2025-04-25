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
    "tydef": ["TypeDefCons", "TypeDef", "TypeDefNull", "TypeDefUnk"], # 4
    "type": ["TypeUser", "TypeUnit", "TypeInt", "TypeBool", "TypeArrow", "TypeReframe", "TypeProd", "TypeUnk"], # 8
    "term": ["TermUnit", "TermInt", "TermTrue", "TermFalse", "TermVar", "TermBinary", "TermUnary", "TermApp", "TermLambda", "TermFix", "TermLet", "TermIf", "TermTuple", "TermProj", "TermMatch", "TermRewrite", "TermLabel", "TermUnlabel", "TermParenthesis", "TermUnk"], # 20
    "matchcase": ["MatchCaseCons", "MatchCaseNil", "MatchCaseUnk"], # 3
    "pattern": ["PatternDefault", "PatternVar", "PatternConstructor", "PatternTuple", "PatternUnk"], # 5
}

from copy import copy

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
            for i in range(len(terms_need)):
                if i >= len(args):
                    setattr(self, args_name[i], findUnk[terms_need[i]])
                else:
                    assert class_type(args[i]) == terms_need[i], f"actual type: {class_type(args[i])} != target type: {terms_need[i]}, args[i]({type(args[i])}):{args[i].to_str({})}"
                    setattr(self, args_name[i], args[i])
            origin_init(self)
        cls.__init__ = new_init
    
class ProgramCons(metaclass=AstNode):
    # command | program
    ty = "program"
    terms_need = ["command", "program"]
    args_name = ["cmd", "prog"]

    def to_str(self, ctx):
        return f"{self.cmd.to_str(ctx)}\n{self.prog.to_str(ctx)}"

    def type_check(self, tctx):
        

class ProgramNil(metaclass=AstNode):
    # ;
    ty = "program"
    terms_need = []
    args_name = []

    def to_str(self, ctx):
        return ""

class ProgramUnk(metaclass=AstNode):
    # ??
    ty = "program"
    terms_need = []
    args_name = []

    def to_str(self, ctx):
        return "??"

class CommandInductive(metaclass=AstNode):
    # Inductive name = tydef
    ty = "command"
    terms_need = ["string", "tydef"]
    args_name = ["name", "tydef"]

    def to_str(self, ctx):
        return f"Inductive {self.name} = {self.tydef.to_str(ctx)}"

class CommandType(metaclass=AstNode):
    # name = ty
    ty = "command"
    terms_need = ["string", "type"]
    args_name = ["name", "ty_"]

    def to_str(self, ctx):
        return f"{self.name} = {self.ty_.to_str(ctx)}"

class CommandTerm(metaclass=AstNode):
    # name = term
    ty = "command"
    terms_need = ["string", "term"]
    args_name = ["name", "term"]

    def to_str(self, ctx):
        return f"{self.name} = {self.term.to_str(ctx)}"

class CommandUnk(metaclass=AstNode):
    # ??
    ty = "command"
    terms_need = []
    args_name = []

    def to_str(self, ctx):
        return "??"

class TypeDef(metaclass=AstNode):
    # name ty
    ty = "tydef"
    terms_need = ["string", "type"]
    args_name = ["name", "ty_"]

    def to_str(self, ctx):
        return f"{self.name} {self.ty_.to_str(ctx)}"

class TypeDefNull(metaclass=AstNode):
    # 
    ty = "tydef"
    terms_need = []
    args_name = []

    def to_str(self, ctx):
        return ""

class TypeDefCons(metaclass=AstNode):
    # tydef | tydef
    ty = "tydef"
    terms_need = ["tydef", "tydef"]
    args_name = ["tydef1", "tydef2"]

    def to_str(self, ctx):
        return f"{self.tydef1.to_str(ctx)} | {self.tydef2.to_str(ctx)}"

class TypeDefUnk(metaclass=AstNode):
    # ??
    ty = "tydef"
    terms_need = []
    args_name = []

    def to_str(self, ctx):
        return "??"

class TypeUser(metaclass=AstNode):
    # name
    ty = "type"
    terms_need = ["string"]
    args_name = ["name"]

    def to_str(self, ctx):
        return self.name

class TypeUnit(metaclass=AstNode):
    # Unit
    ty = "type"
    terms_need = []
    args_name = []

    def to_str(self, ctx):
        return "Unit"

class TypeInt(metaclass=AstNode):
    # Int
    ty = "type"
    terms_need = []
    args_name = []

    def to_str(self, ctx):
        return "Int"

class TypeBool(metaclass=AstNode):
    # Bool
    ty = "type"
    terms_need = []
    args_name = []

    def to_str(self, ctx):
        return "Bool"

class TypeArrow(metaclass=AstNode):
    # ty -> ty
    ty = "type"
    terms_need = ["type", "type"]
    args_name = ["ty1", "ty2"]

    def to_str(self, ctx):
        return f"{self.ty1.to_str(ctx)} -> {self.ty2.to_str(ctx)}"

class TypeReframe(metaclass=AstNode):
    # Reframe ty
    ty = "type"
    terms_need = ["type"]
    args_name = ["ty_"]

    def to_str(self, ctx):
        return f"Reframe {self.ty_.to_str(ctx)}"

class TypeProd(metaclass=AstNode):
    # {ty, ..., ty}
    ty = "type"
    terms_need = ["type", "type"]
    args_name = ["ty1", "ty2"]

    def to_str(self, ctx):
        new_ctx = copy(ctx)
        new_ctx["curly_brackets"] = False
        ty1, ty2 = self.ty1.to_str(new_ctx), self.ty2.to_str(new_ctx)
        if "curly_brackets" in ctx and ctx["curly_brackets"]==False:
            return f"{ty1}, {ty2}"
        else:
            return f"{{{ty1}, {ty2}}}"

class TypeUnk(metaclass=AstNode):
    # ??
    ty = "type"
    terms_need = []
    args_name = []

    def to_str(self, ctx):
        return "??"

class TermUnit(metaclass=AstNode):
    # unit
    ty = "term"
    terms_need = []
    args_name = []

    def to_str(self, ctx):
        return "unit"

class TermInt(metaclass=AstNode):
    # integer
    ty = "term"
    terms_need = ["string"]
    args_name = ["int"]

    def to_str(self, ctx):
        return self.int

class TermTrue(metaclass=AstNode):
    # true
    ty = "term"
    terms_need = []
    args_name = []

    def to_str(self, ctx):
        return "true"

class TermFalse(metaclass=AstNode):
    # false
    ty = "term"
    terms_need = []
    args_name = []

    def to_str(self, ctx):
        return "false"

class TermVar(metaclass=AstNode):
    # name
    ty = "term"
    terms_need = ["string"]
    args_name = ["name"]

    def to_str(self, ctx):
        return self.name

class TermBinary(metaclass=AstNode):
    # + | - | * | / | < | <= | > | >= | == | and | or 
    ty = "term"
    terms_need = ["string"]
    args_name = ["op"]
    def to_str(self, ctx):
        return self.op

class TermUnary(metaclass=AstNode):
    # - | not
    ty = "term"
    terms_need = ["string"]
    args_name = ["op"]
    def to_str(self, ctx):
        return self.op

class TermApp(metaclass=AstNode):
    # term term
    ty = "term"
    terms_need = ["term", "term"]
    args_name = ["term1", "term2"]

    def to_str(self, ctx):
        return f"{self.term1.to_str(ctx)} {self.term2.to_str(ctx)}"

class TermLambda(metaclass=AstNode):
    # \name:ty. term
    ty = "term"
    terms_need = ["string", "type", "term"]
    args_name = ["name", "ty_", "term"]

    def to_str(self, ctx):
        return f"\\{self.name}:{self.ty_.to_str(ctx)}. {self.term.to_str(ctx)}"

class TermFix(metaclass=AstNode):
    # fix term
    ty = "term"
    terms_need = ["term"]
    args_name = ["term"]

    def to_str(self, ctx):
        return f"fix {self.term.to_str(ctx)}"

class TermLet(metaclass=AstNode):
    # let name = term in term
    ty = "term"
    terms_need = ["string", "term", "term"]
    args_name = ["name", "val", "term"]

    def to_str(self, ctx):
        return f"let {self.name} = {self.val.to_str(ctx)} in {self.term.to_str(ctx)}"

class TermIf(metaclass=AstNode):
    # if term then term else term
    ty = "term"
    terms_need = ["term", "term", "term"]
    args_name = ["cond", "then_", "else_"]

    def to_str(self, ctx):
        return f"if {self.cond.to_str(ctx)} then {self.then_.to_str(ctx)} else {self.else_.to_str(ctx)}"

class TermTuple(metaclass=AstNode):
    # {term, ..., term}
    ty = "term"
    terms_need = ["term", "term"]
    args_name = ["term1", "term2"]

    def to_str(self, ctx):
        new_ctx = copy(ctx)
        new_ctx["curly_brackets"] = False
        term1, term2 = self.term1.to_str(new_ctx), self.term2.to_str(new_ctx)
        if "curly_brackets" in ctx and ctx["curly_brackets"]==False:
            return f"{term1}, {term2}"
        else:
            return f"{{{term1}, {term2}}}"

class TermProj(metaclass=AstNode):
    # term.integer
    ty = "term"
    terms_need = ["term", "string"]
    args_name = ["term", "int"]

    def to_str(self, ctx):
        return f"{self.term.to_str(ctx)}.{self.int}"

class TermMatch(metaclass=AstNode):
    # match term with matchcase
    ty = "term"
    terms_need = ["term", "matchcase"]
    args_name = ["term", "matchcase"]

    def to_str(self, ctx):
        return f"match {self.term.to_str(ctx)} with {self.matchcase.to_str(ctx)}"

class TermRewrite(metaclass=AstNode):
    # rewrite term
    ty = "term"
    terms_need = ["term"]
    args_name = ["term"]

    def to_str(self, ctx):
        return f"rewrite {self.term.to_str(ctx)}"

class TermLabel(metaclass=AstNode):
    # label term
    ty = "term"
    terms_need = ["term"]
    args_name = ["term"]

    def to_str(self, ctx):
        return f"label {self.term.to_str(ctx)}"

class TermUnlabel(metaclass=AstNode):
    # unlabel term
    ty = "term"
    terms_need = ["term"]
    args_name = ["term"]

    def to_str(self, ctx):
        return f"unlabel {self.term.to_str(ctx)}"

class TermParenthesis(metaclass=AstNode):
    # (term)
    ty = "term"
    terms_need = ["term"]
    args_name = ["term"]

    def to_str(self, ctx):
        return f"({self.term.to_str(ctx)})"

class TermUnk(metaclass=AstNode):
    # ??
    ty = "term"
    terms_need = []
    args_name = []

    def to_str(self, ctx):
        return "??"

class MatchCase(metaclass=AstNode):
    # pattern -> term
    ty = "matchcase"
    terms_need = ["pattern", "term"]
    args_name = ["pattern", "term"]

    def to_str(self, ctx):
        return f"{self.pattern.to_str(ctx)} -> {self.term.to_str(ctx)}"

class MatchCaseCons(metaclass=AstNode):
    # matchcase | matchcase
    ty = "matchcase"
    terms_need = ["matchcase", "matchcase"]
    args_name = ["matchcase1", "matchcase2"]

    def to_str(self, ctx):
        return f"{self.matchcase1.to_str(ctx)} | {self.matchcase2.to_str(ctx)}"

class MatchCaseUnk(metaclass=AstNode):
    # ??
    ty = "matchcase"
    terms_need = []
    args_name = []

    def to_str(self, ctx):
        return "??"

class PatternDefault(metaclass=AstNode):
    # _
    ty = "pattern"
    terms_need = []
    args_name = []

    def to_str(self, ctx):
        return "_"

class PatternVar(metaclass=AstNode):
    # name
    ty = "pattern"
    terms_need = ["string"]
    args_name = ["name"]

    def to_str(self, ctx):
        return self.name

class PatternConstructor(metaclass=AstNode):
    # name pattern
    ty = "pattern"
    terms_need = ["string", "pattern"]
    args_name = ["constructor", "pattern"]

    def to_str(self, ctx):
        return f"{self.constructor} {self.pattern.to_str(ctx)}"

class PatternTuple(metaclass=AstNode):
    # {pattern, ..., pattern}
    ty = "pattern"
    terms_need = ["pattern", "pattern"]
    args_name = ["pattern1", "pattern2"]

    def to_str(self, ctx):
        new_ctx = copy(ctx)
        new_ctx["curly_brackets"] = False
        pattern1, pattern2 = self.pattern1.to_str(new_ctx), self.pattern2.to_str(new_ctx)
        if "curly_brackets" in ctx and ctx["curly_brackets"]==False:
            return f"{pattern1}, {pattern2}"
        else:
            return f"{{{pattern1}, {pattern2}}}"
        
class PatternUnk(metaclass=AstNode):
    # ??
    ty = "pattern"
    terms_need = []
    args_name = []

    def to_str(self, ctx):
        return "??"

# return an xxxUnk() object according to class_type
findUnk = {
    "program": ProgramUnk(),
    "command": CommandUnk(),
    "tydef": TypeDefUnk(),
    "type": TypeUnk(),
    "term": TermUnk(),
    "matchcase": MatchCaseUnk(),
    "pattern": PatternUnk(),
}

# judge the class_type of the object
def class_type(obj):
    if hasattr(obj, "ty"):
        return obj.ty
    else:
        return "string"

from tree_sitter import Language, Parser
import os
path = os.path.split(os.path.realpath(__file__))[0]
SUFU_LANGUAGE = Language(path + "/tree-sitter-sufu/sufu.so", "sufu")
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
                if node.child_count <= 3:
                    tydef = TypeDefNull()
                else:
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
            case "term_binop":
                start, end = node.start_byte, node.end_byte
                content = info["code"][start:end]
                return TermBinary(content)
            case "term_unop":
                start, end = node.start_byte, node.end_byte
                content = info["code"][start:end]
                return TermUnary(content)
            case "term_parenthesized":
                return TermParenthesis(visit(node.children[1], info))
            case "match_case":
                assert node.child_count >= 4, f"match case: {node.sexp()}"
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
        assert False, "unknown node type: " + type(node)

if __name__ == "__main__":
    with open("tree-sitter-sufu/example-file", "r") as f:
        code = f.read()
    node = parser.parse(bytes(code, "utf8")).root_node
    sufu_node = visit(node, {"code": code})
    print(sufu_node.to_str({}))