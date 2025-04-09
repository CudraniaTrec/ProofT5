import os, subprocess, json, pickle
from copy import deepcopy
import myjavalang as javalang
from myjavalang.tree import *
from program_model import *
from enum import Enum
from tqdm import tqdm
from pyinstrument import Profiler
from multiprocessing import Pool

# global statistics
info = {
    "total": 0,
    "correct_list": [],
    "parse_error_list": [],
    "toJava_error_list": [],
    "toCoq_error_list": [],
    "detokenize_error_list": [],
}

len_cnt = [] # tokenized proof length
def update_progress(res, pbar):
    pbar.update(1)
    filenum = res["file_num"]
    info[res["res"] + "_list"].append(filenum)
    pbar.set_postfix_str(f"Correct {len(info['correct_list'])}")
    if "len_cnt" in res:
        len_cnt.append(res["len_cnt"])

# Section 1: converting java programs to impp programs

# extended node types
class ExNodeTypes(Enum):
    Default = 0
    StatementList = 1
    TermList = 2
    ClassComponentList = 3

# print a javalang node in json format
def print_node(node):
    import json
    def get_json(node):
        if isinstance(node, Node):
            ret = {"ty": type(node).__name__}
            ret.update({attr: get_json(getattr(node, attr)) for attr in node.attrs})
            return ret
        elif isinstance(node, list):
            return [get_json(n) for n in node]
        else:
            return str(node)
    return json.dumps(get_json(node), indent=2)

java_type_map = {
    "Object": "Object",
    "ArrayList": "List",
    "HashSet": "Set",
    "HashMap": "Map",
    "LinkedList": "List",
    "List": "List",
    "Set": "Set",
    "Map": "Map",
}

def visit(node, node_type=ExNodeTypes.Default):
    if isinstance(node, CompilationUnit):
        # ignore packages and imports
        ctypes = node.types
        assert len(ctypes) >= 1, "CompilationUnit should have at least one type"
        ret = visit(ctypes[-1]) #PgClassDecl
        for ctype in ctypes[-2::-1]:
            ret = PgConcat(ret, visit(ctype))
        return ret
    elif isinstance(node, ClassDeclaration):
        # ignore documentation, annotations, modifiers
        # unsupport type_parameters, extends, implements
        assert node.type_parameters == None, "type parameters not supported"
        assert node.extends == None, "extends not supported"
        assert node.implements == None, "implements not supported"
        body = visit(node.body, ExNodeTypes.ClassComponentList)
        return PgClassDecl(node.name, body)
    elif isinstance(node, MethodDeclaration):
        # ignore documentation, annotations
        # unsupport type_parameters, throws
        assert node.type_parameters == None, "type parameters not supported"
        assert node.throws == None, "throws not supported"
        modifiers = list(node.modifiers)
        modifier = " ".join(sorted(modifiers))
        name = node.name
        param = visit(node.parameters, ExNodeTypes.StatementList)
        ret_type = visit(node.return_type)
        body = visit(node.body, ExNodeTypes.StatementList)
        return PgMethodDecl(modifier, ret_type, name, param, body)
    elif isinstance(node, javalang.tree.Type):
        if node.dimensions and len(node.dimensions) > 0:
            tmp_node = deepcopy(node)
            tmp_node.dimensions = None
            ret = visit(tmp_node)
            for _ in node.dimensions:
                ret = TyArray(ret)
            return ret
        elif isinstance(node, BasicType):
            match node.name:
                case "int":
                    return TyInt()
                case "boolean":
                    return TyBool()
                case "void":
                    return TyVoid()
                case "char":
                    return TyChar()
                case "byte":
                    return TyInt()
                case "short":
                    return TyInt()
                case "long":
                    return TyInt()
                case "float":
                    return TyFloat()
                case "double":
                    return TyFloat()
                case _:
                    print(f"Unknown basic type: {node.name}")
                    raise NotImplementedError
        elif isinstance(node, ReferenceType):
            match node.name:
                case "Integer":
                    return TyInt()
                case "Boolean":
                    return TyBool()
                case "Character":
                    return TyChar()
                case "Float":
                    return TyFloat()
                case "Double":
                    return TyFloat()
                case "String":
                    return TyString()
                case "Byte":
                    return TyInt()
                case "Short":
                    return TyInt()
                case "Long":
                    return TyInt()
                case _:
                    assert node.name in java_type_map, f"Unknown reference type: {node.name}"
                    name = java_type_map[node.name]
                    if node.arguments == None:
                        return TyClass(name)
                    elif len(node.arguments) == 0:
                        return TyGeneric0(name)
                    elif len(node.arguments) == 1:
                        return TyGeneric1(name, visit(node.arguments[0]))
                    elif len(node.arguments) == 2:
                        return TyGeneric2(name, visit(node.arguments[0]), visit(node.arguments[1]))
                    else:
                        assert False, f"Unknown reference type: {node.name}"
        else:
            assert False, f"Unknown type: {print_node(node)}"
    elif isinstance(node, TypeArgument):
        assert node.pattern_type == None, "pattern_type not supported"
        return visit(node.type)
    elif isinstance(node, ConstructorDeclaration):
        print(f"ConstructorDeclaration: {node.name}")
        # ignore documentation, annotations
        # unsupport type_parameters, throws
        assert node.type_parameters == None, "type parameters not supported"
        assert node.throws == None, "throws not supported"
        param = visit(node.parameters, ExNodeTypes.StatementList)
        body = visit(node.body, ExNodeTypes.StatementList)
        return PgConstructorDecl(param, body)
    elif isinstance(node, FieldDeclaration):
        print(f"FieldDeclaration: {node.name}")
        # ignore documentation, annotations
        assert len(node.declarators) == 1, "FieldDeclaration should have exactly one declarator"
        modifiers = list(node.modifiers)
        modifier = " ".join(sorted(modifiers))
        ty = visit(node.type)
        name, val = visit(node.declarators[0])
        if val:
            return PgFieldDeclInit(modifier, ty, name, val)
        else:
            return PgFieldDeclNoInit(modifier, ty, name)
    elif isinstance(node, VariableDeclaration):
        # ignore annotations
        ty = visit(node.type)
        name, val = visit(node.declarators[0])
        if val:
            ret = StDeclInit(ty, name, val)
        else:
            ret = StDeclNoInit(ty, name)
        for n in node.declarators[1:]:
            name, val = visit(n)
            if val:
                ret = StConcat(ret, StDeclInit(ty, name, val))
            else:
                ret = StConcat(ret, StDeclNoInit(ty, name))
        return ret
    elif isinstance(node, VariableDeclarator):
        assert node.dimensions == None or len(node.dimensions)==0, f"VariableDeclarator should not have dimensions"
        name = node.name
        if node.initializer == None:
            return name, None
        else:
            return name, visit(node.initializer)
    elif isinstance(node, FormalParameter):
        # unsupport varargs
        assert node.varargs == False, "vararg not supported"
        ty = visit(node.type)
        return StDeclNoInit(ty, node.name)
    elif isinstance(node, IfStatement):
        cond = visit(node.condition)
        then = visit(node.then_statement)
        if node.else_statement:
            els = visit(node.else_statement)
            return StIfElse(cond, then, els)
        else:
            return StIf(cond, then)
    elif isinstance(node, WhileStatement):
        cond = visit(node.condition)
        body = visit(node.body)
        return StWhile(cond, body)
    elif isinstance(node, DoStatement):
        body = visit(node.body)
        cond = visit(node.condition)
        return StDoWhile(body, cond)
    elif isinstance(node, ForStatement):
        enhanced, control = visit(node.control)
        body = visit(node.body)
        if not enhanced:
            init, cond, update = control
            return StFor(init, cond, update, body)
        else:
            ty, name, tm = control
            return StForeach(ty, name, tm, body)
    elif isinstance(node, ForControl):
        init = visit(node.init)
        cond = visit(node.condition)
        assert len(node.update) == 1, "ForControl should have exactly one update"
        update = visit(node.update[0])
        return False, (init, cond, update)
    elif isinstance(node, EnhancedForControl):
        var = visit(node.var)
        ty, name = var.ty, var.string
        tm = visit(node.iterable)
        return True, (ty, name, tm)
    elif isinstance(node, BreakStatement):
        # unsupport goto
        assert node.goto == None, "goto not supported"
        return StBreak()
    elif isinstance(node, ContinueStatement):
        # unsupport goto
        assert node.goto == None, "goto not supported"
        return StContinue()
    elif isinstance(node, ReturnStatement):
        exp = visit(node.expression)
        return StReturn(exp)
    elif isinstance(node, StatementExpression):
        exp = visit(node.expression)
        return StExpression(exp)
    elif isinstance(node, BlockStatement):
        return visit(node.statements, ExNodeTypes.StatementList)
    elif isinstance(node, Expression) and node.parenthesized:
        new_node = deepcopy(node)
        new_node.parenthesized = False
        exp = visit(new_node)
        return TmParenthesis(exp)
    elif isinstance(node, Assignment):
        expr = visit(node.expressionl)
        val = visit(node.value)
        ty = node.type
        if ty == "=":
            return TmAssign(expr, val)
        elif ty == "+=":
            return TmAssign(expr, TmAdd(expr, val))
        elif ty == "-=":
            return TmAssign(expr, TmSub(expr, val))
        elif ty == "*=":
            return TmAssign(expr, TmMul(expr, val))
        elif ty == "/=":
            return TmAssign(expr, TmDiv(expr, val))
        elif ty == "%=":
            return TmAssign(expr, TmMod(expr, val))
        elif ty == "&=":
            return TmAssign(expr, TmBitAnd(expr, val))
        elif ty == "|=":
            return TmAssign(expr, TmBitOr(expr, val))
        elif ty == "^=":
            return TmAssign(expr, TmBitXor(expr, val))
        elif ty == "<<=":
            return TmAssign(expr, TmShiftL(expr, val))
        elif ty == ">>=":
            return TmAssign(expr, TmShiftR(expr, val))
        else:
            assert False, f"Unknown assignment operator: {ty}"
    elif isinstance(node, BinaryOperation):
        left = visit(node.operandl)
        right = visit(node.operandr)
        op = node.operator
        match op:
            case "+":
                return TmAdd(left, right)
            case "-":
                return TmSub(left, right)
            case "*":
                return TmMul(left, right)
            case "/":
                return TmDiv(left, right)
            case "%":
                return TmMod(left, right)
            case "&&":
                return TmAnd(left, right)
            case "||":
                return TmOr(left, right)
            case "&":
                return TmBitAnd(left, right)
            case "|":
                return TmBitOr(left, right)
            case "^":
                return TmBitXor(left, right)
            case "==":
                return TmEq(left, right)
            case "!=":
                return TmNe(left, right)
            case "<":
                return TmLt(left, right)
            case "<=":
                return TmLe(left, right)
            case ">":
                return TmGt(left, right)
            case ">=":
                return TmGe(left, right)
            case "<<":
                return TmShiftL(left, right)
            case ">>":
                return TmShiftR(left, right)
            case "instanceof":
                return TmInstanceOf(right, left)
            case _:
                assert False, f"Unknown binary operator: {op}"
    elif isinstance(node, TernaryExpression):
        cond = visit(node.condition)
        then = visit(node.if_true)
        els = visit(node.if_false)
        return TmChoose(cond, then, els)
    elif isinstance(node, Cast):
        ty = visit(node.type)
        exp = visit(node.expression)
        return TmConversion(ty, exp)
    elif isinstance(node, Primary) and node.prefix_operators:
        assert len(node.prefix_operators) == 1, "Primary should have exactly one prefix operator"
        op = node.prefix_operators[0]
        tmp_node = deepcopy(node)
        tmp_node.prefix_operators = None
        if op == "-":
            return TmNeg(visit(tmp_node))
        elif op == "!":
            return TmNot(visit(tmp_node))
        elif op == "~":
            return TmBitNot(visit(tmp_node))
        elif op == "++":
            return TmPreInc(visit(tmp_node))
        elif op == "--":
            return TmPreDec(visit(tmp_node))
        else:
            assert False, f"Unknown prefix operator: {op}"
    elif isinstance(node, Primary) and node.postfix_operators:
        assert len(node.postfix_operators) == 1, "Primary should have exactly one postfix operator"
        op = node.postfix_operators[0]
        if op == "++":
            tmp_node = deepcopy(node)
            tmp_node.postfix_operators = None
            return TmPostInc(visit(tmp_node))
        elif op == "--":
            tmp_node = deepcopy(node)
            tmp_node.postfix_operators = None
            return TmPostDec(visit(tmp_node))
        else:
            assert False, f"Unknown suffix operator: {op}"
    elif isinstance(node, MemberReference):
        qualifier = node.qualifier
        if qualifier == "":
            base = None
        elif qualifier[0].isupper():
            if qualifier in ["Math", "Integer", "Arrays"]:
                q = qualifier + '.' + node.member
                base = TmType(TyClass(qualifier))
            else:
                assert False, f"Unknown qualifier: {qualifier}"
        else:
            base = TmVar(qualifier)
        member = node.member
        if base == None:
            ret = TmVar(member)
        else:
            ret = TmFieldAccess(member, base)
        for n in node.selectors:
            ret = TmArrayAccess(ret, visit(n))
        return ret
    elif isinstance(node, Literal):
        val = node.value
        if val == "null":
            return TmNull()
        elif val == "true":
            return TmTrue()
        elif val == "false":
            return TmFalse()
        else:
            try:
                num = int(val)
                return TmInteger(str(num))
            except ValueError:
                try:
                    num = float(val)
                    return TmFloat(str(num))
                except ValueError:
                    if val[0] == '"':
                        return TmString(val[1:-1])
                    elif val[0] == "'":
                        return TmChar(val[1])
                    else:
                        assert False, f"Unknown literal: {val}"
    elif isinstance(node, This):
        return TmVar("this")
    elif isinstance(node, MethodInvocation):
        qualifier = node.qualifier
        if qualifier == "":
            base = None
        elif qualifier[0].isupper():
            if qualifier in ["Math", "Integer", "Arrays"]:
                q = qualifier + '.' + node.member
                base = TmType(TyClass(qualifier))
            else:
                assert False, f"Unknown qualifier: {qualifier}"
        else:
            base = TmVar(qualifier)
        method_name = node.member
        args = visit(node.arguments, ExNodeTypes.TermList)
        if base == None:
            ret = TmMethodInvocationNoObj(method_name, args)
        else:
            ret = TmMethodInvocation(method_name, base, args)
        for n in node.selectors:
            if isinstance(n, MethodInvocation):
                method_name = n.member
                args = visit(n.arguments, ExNodeTypes.TermList)
                ret = TmMethodInvocation(method_name, ret, args)
            else:
                assert False, f"Unknown selector: {n}"
        return ret
    elif isinstance(node, ClassCreator):
        assert node.body == None or len(node.body) == 0, "ClassCreator should not have body"
        assert node.constructor_type_arguments == None, "constructor_type_arguments not supported"
        ty = visit(node.type)
        args = visit(node.arguments, ExNodeTypes.TermList)
        return TmNew(ty, args)
    elif isinstance(node, ArrayCreator):
        ty = visit(node.type)
        ret = TmNewArray0(ty)
        for n in node.dimensions:
            ret = TmNewArray1(visit(n), ret)
        return ret
    elif isinstance(node, ArraySelector):
        return visit(node.index)
    elif node_type == ExNodeTypes.ClassComponentList:
        assert isinstance(node, list), "ClassComponentList should be a list"
        assert len(node) >= 1, "ClassComponentList should have at least one component"
        ret = visit(node[-1])
        for n in node[-2::-1]:
            ret = PgConcat(visit(n), ret)
        return ret
    elif node_type == ExNodeTypes.StatementList:
        assert isinstance(node, list), "StatementList should be a list"
        ret = StSkip()
        for n in node[-1::-1]:
            ret = StConcat(visit(n), ret)
        return ret
    elif node_type == ExNodeTypes.TermList:
        assert isinstance(node, list), "TermList should be a list"
        ret = TmList0()
        for n in node[-1::-1]:
            ret = TmList1(visit(n), ret)
        return ret
    else:
        assert False, f"\nUnknown node {type(node)}:"

# Section 2: translate and validate single java file

# parse and validate single java file
def parse_java_file(file_path="datas/mbjp/MBJP_1.java", java_code="", verbose=False):
    # load java code
    file_num = int(file_path.split("/")[-1].split(".")[0][5:])
    with open(file_path, "r") as f:
        code = f.read()
    if java_code:
        code = java_code
    if verbose:
        print("="*50)
        print(f"File: {file_path}")
        print(code)

    # parse java code
    try:
        tree = javalang.parse.parse(code)
        program = visit(tree)
        java_default_packages = ["java.lang.*", "java.util.*", "java.math.*", "java.io.*"]
        javaCode = program.to_java()
        for package in java_default_packages:
            javaCode = f"import {package};\n" + javaCode
        if verbose:
            print(program.to_code())
    except Exception as e:
        if verbose:
            print(f"Error in parsing {file_path}: {e}")
            import traceback
            traceback.print_exc()
        return {'res': "parse_error", 'file_num': file_num}
    
    # validate impp code(java)
    from mxeval.execution import check_correctness_java as check
    with open("datas/mbjp.json", "r") as file:
        mbjp_datas = json.load(file)
    mbjp_data=[data for data in mbjp_datas if data['task_id']==f"MBJP/{file_num}"][0]
    result=check(mbjp_data,javaCode,solution_complete=True)
    if not result['passed']:
        if verbose:
            print(f"\nError in validating java version of: {file_path}")
            print(javaCode)
            print(result['result'])
        return {'res': "toJava_error", 'file_num': file_num}
    
    # validate impp code(coq)
    coq_file_path = f"coq_code/mbjp/{file_num}/t0.v"
    os.makedirs(os.path.dirname(coq_file_path), exist_ok=True)
    with open(coq_file_path, "w") as f:
        f.write(str(program.to_coq()))
    try:
        res = subprocess.run(
                ["coqc", "-Q","coq_code/", "PLF", coq_file_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=120,
            )
    except subprocess.TimeoutExpired:
        if verbose:
            print(f"Timeout in {file_path}")
        return {'res': "toCoq_error", 'file_num': file_num}
    if res.returncode != 0:
        if verbose:
            err_msg = res.stderr.decode('utf-8')
            print(f"Error in validating coq version of {file_path}: {err_msg}")
        return {'res': "toCoq_error", 'file_num': file_num}
    else:
        vfile_path = file_path.replace(".java", ".v")
        with open(vfile_path, "w") as f:
            f.write(str(program.to_coq()))
    return {'res': "correct", 'file_num': file_num}

# translate all mbjp programs
def trans_all_mbjp_programs():
    dir_path = "datas/mbjp/"
    files = [f for f in os.listdir(dir_path) if f.endswith(".java")]
    global info
    info["total"] = len(files)
    info["correct_list"] = []
    info["parse_error_list"] = []
    info["toJava_error_list"] = []
    info["toCoq_error_list"] = []

    tbar = tqdm(files)
    with Pool(50) as p:
        for file in files:
            file_path = dir_path + file
            p.apply_async(parse_java_file, args=(file_path, "", False), 
                          callback=lambda x: update_progress(x, tbar))
        p.close()
        p.join()
    tbar.close()

    from beeprint import pp
    info["correct_cnt"] = len(info["correct_list"])
    info["parse_error_cnt"] = len(info["parse_error_list"])
    info["toJava_error_cnt"] = len(info["toJava_error_list"])
    info["toCoq_error_cnt"] = len(info["toCoq_error_list"])
    pp(info)

# Section 3: (de)tokenize and validate java files

rrule_dict = {v: k for k, v in rule_dict.items()}
# detokenize and validate single java file
def tokenize_java_file(file_path="datas/mbjp/MBJP_1.java"):
    file_num = int(file_path.split("/")[-1].split(".")[0][5:])
    with open(file_path, "r") as f:
        java_code = f.read()
    tree = javalang.parse.parse(java_code)
    program = visit(tree)

    # detokenize and validate
    tokenized_coq = program.to_coq().tokenization()
    ids=[rule_dict[token] for token in tokenized_coq]
    tokens = [rrule_dict[id] for id in ids]
    program = detokenization_wrapper(tokens)
    if not program: # returns None
        print(f"Error in detokenizing tokens: {file_path}")
        return {'res': "detokenize_error", 'file_num': file_num}
        
    # generate all coqview
    for i in range(len(tokens)-1):
        rprogram = detokenization_wrapper(tokens[:i+1])
        if not rprogram:
            print(f"Error in detokenizing tokens: {file_path}")
            return {'res': "detokenize_error", 'file_num': file_num}
        coq_file_path = f"coq_code/mbjp/{file_num}/t{i+1}.v"
        os.makedirs(os.path.dirname(coq_file_path), exist_ok=True)
        with open(coq_file_path, "w") as f:
            f.write(str(rprogram.to_coq()))
        try:
            res = subprocess.run(
                    ["coqc", "-Q","coq_code/", "PLF", coq_file_path],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=120,
                )
        except subprocess.TimeoutExpired:
            print(f"Timeout in {coq_file_path}:")
            print(rprogram.to_coq())
            return {'res': "detokenize_error", 'file_num': file_num}
        if res.returncode != 0:
            print(f"Error in validating tokens of {coq_file_path}:")
            print(rprogram.to_coq())
            return {'res': "detokenize_error", 'file_num': file_num}
        else:
            view = res.stdout.decode('utf-8')
            coqview_folder = f"datas/mbjp_coqview/{file_num}/"
            os.makedirs(coqview_folder, exist_ok=True)
            with open(coqview_folder + f"step{i+1}.txt", "w") as f:
                f.write(view)
    res = parse_java_file(file_path, java_code=program.to_java(), verbose=False)
    if res["res"] == "correct":
        # tokenize and save
        with open(file_path.replace(".java", ".pkl"), "wb") as f:
            pickle.dump(ids, f)
    res['len_cnt'] = len(ids)
    return res

# (de)tokenize and validate all java files
def tokenize_all_java_files():
    dir_path = "datas/mbjp/"
    files = [f for f in os.listdir(dir_path) 
             if f.endswith(".java") and os.path.exists(dir_path + f.replace(".java", ".v"))]
    global info
    info["total"] = len(files)
    info["correct_list"] = []
    info["parse_error_list"] = []
    info["toJava_error_list"] = []
    info["toCoq_error_list"] = []
    info["detokenize_error_list"] = []

    tbar = tqdm(files)
    with Pool(50) as p:
        for file in files:
            p.apply_async(tokenize_java_file, args=(dir_path + file,), 
                          callback=lambda x: update_progress(x, tbar))
        p.close()
        p.join()
    tbar.close()

    from beeprint import pp
    info["correct_cnt"] = len(info["correct_list"])
    info["parse_error_cnt"] = len(info["parse_error_list"])
    info["toJava_error_cnt"] = len(info["toJava_error_list"])
    info["toCoq_error_cnt"] = len(info["toCoq_error_list"])
    info["detokenize_error_cnt"] = len(info["detokenize_error_list"])
    pp(info)

    import matplotlib.pyplot as plt
    # 绘制直方图
    plt.hist(len_cnt, bins=100, edgecolor='black')
    plt.title('Distribution of Proof length')
    plt.xlabel('Length')
    plt.ylabel('Frequency')
    plt.savefig('proof_length_distribution.png')
    print(f"Average tokenized proof length: {sum(len_cnt)/len(len_cnt)}")

# remove all .v .pkl files in mbjp folder
def clean_folder(dir_path):
    files = [f for f in os.listdir(dir_path) if not f.endswith(".java")]
    for file in files:
        os.remove(dir_path + file)

if __name__ == "__main__":
    # profiler = Profiler()
    # profiler.start()
    clean_folder("datas/mbjp/")
    # parse_java_file("datas/mbjp/MBJP_430.java")
    trans_all_mbjp_programs()
    # print(tokenize_java_file("datas/mbjp/MBJP_430.java"))
    tokenize_all_java_files()
    # profiler.stop()
    # profiler.print()
   
    