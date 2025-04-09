import pickle, json, os, traceback
from tree_sitter import Language, Parser
from coq_model import *

path = os.path.split(os.path.realpath(__file__))[0]
DSL_LANGUAGE = Language("Utils/tree_sitter_dsl/parser.so", "dsl")
parser = Parser()
parser.set_language(DSL_LANGUAGE)

def visit(node, code, info={}):
    name = node.type
    if name in ["expression", "update_expression", "primary_expression", 
                "statement", "local_variable_declaration", "comment"]:
        return visit(node.children[0], code, info)
    elif name == "identifier":
        text = code[node.start_byte:node.end_byte]
        return text
    elif name == "integer_literal":
        text = code[node.start_byte:node.end_byte]
        return TmInteger(text)
    elif name == "character_literal":
        text = code[node.start_byte:node.end_byte]
        if text[0] == "'" and text[-1] == "'":
            text = text[1:-1]
        return TmChar(text)
    elif name == "floating_point_literal":
        text = code[node.start_byte:node.end_byte]
        return TmFloat(text)
    elif name == "string_literal":
        text = code[node.start_byte:node.end_byte]
        if text[0] == '"' and text[-1] == '"':
            text = text[1:-1]
        return TmString(text)
    elif name == "true":
        return TmTrue()
    elif name == "false":
        return TmFalse()
    elif name == "null":
        return TmNull()
    elif name == "int":
        return TyInt()
    elif name == "char":
        return TyChar()
    elif name == "double":
        return TyFloat()
    elif name == "string":
        return TyString()
    elif name == "bool":
        return TyBool()
    elif name == "void":
        return TyVoid()
    elif name == "type_identifier":
        text = code[node.start_byte:node.end_byte]
        return TyClass(text)
    elif name == "array_type":
        ty = visit(node.child_by_field_name('element'), code, info)
        dimensions = visit(node.child_by_field_name('dimensions'), code, info)
        for _ in range(dimensions):
            ty = TyArray(ty)
        return ty
    elif name == "dimensions":
        return node.child_count // 2
    elif name == "generic_type":
        ty = visit(node.children[0], code, info)
        newinfo = info.copy()
        newinfo['generic_type_base'] = ty
        return visit(node.children[1], code, newinfo)
    elif name == "type_arguments0":
        base = info['generic_type_base']
        return TyGeneric0(base)
    elif name == "type_arguments1":
        base = info['generic_type_base']
        ty0 = visit(node.children[1], code, info)
        return TyGeneric1(base, ty0)
    elif name == "type_arguments2":
        base = info['generic_type_base']
        ty0 = visit(node.children[1], code, info)
        ty1 = visit(node.children[3], code, info)
        return TyGeneric2(base, ty0, ty1)
    elif name == "cast_expression":
        ty = visit(node.child_by_field_name('type'), code, info)
        expr = visit(node.child_by_field_name('value'), code, info)
        return TmConversion(ty, expr)
    elif name == "assignment_expression":
        lhs = visit(node.child_by_field_name('left'), code, info)
        if isinstance(lhs, str):
            lhs = TmVar(lhs)
        rhs = visit(node.child_by_field_name('right'), code, info)
        return TmAssign(lhs, rhs)
    elif name == "instanceof_expression":
        expr = visit(node.child_by_field_name('left'), code, info)
        ty = visit(node.child_by_field_name('right'), code, info)
        return TmInstanceOf(ty, expr)
    elif name == "ternary_expression":
        cond = visit(node.child_by_field_name('condition'), code, info)
        consequence = visit(node.child_by_field_name('consequence'), code, info)
        alternative = visit(node.child_by_field_name('alternative'), code, info)
        return TmChoose(cond, consequence, alternative)
    elif name == "binary_expression":
        op_node = node.child_by_field_name('operator')
        op = code[op_node.start_byte:op_node.end_byte]
        lhs = visit(node.child_by_field_name('left'), code, info)
        rhs = visit(node.child_by_field_name('right'), code, info)
        match op:
            case "+":
                return TmAdd(lhs, rhs)
            case "-":
                return TmSub(lhs, rhs)
            case "*":
                return TmMul(lhs, rhs)
            case "/":
                return TmDiv(lhs, rhs)
            case "%":
                return TmMod(lhs, rhs)
            case "<":
                return TmLt(lhs, rhs)
            case "<=":
                return TmLe(lhs, rhs)
            case ">":
                return TmGt(lhs, rhs)
            case ">=":
                return TmGe(lhs, rhs)
            case "==":
                return TmEq(lhs, rhs)
            case "!=":
                return TmNe(lhs, rhs)
            case "&&":
                return TmAnd(lhs, rhs)
            case "||":
                return TmOr(lhs, rhs)
            case "&":
                return TmBitAnd(lhs, rhs)
            case "|":
                return TmBitOr(lhs, rhs)
            case "^":
                return TmBitXor(lhs, rhs)
            case "<<":
                return TmShiftL(lhs, rhs)
            case ">>":
                return TmShiftR(lhs, rhs)
            case _:
                assert False, f"Binary operator {op} not supported"
    elif name == "unary_expression":
        op_node = node.child_by_field_name('operator')
        op = code[op_node.start_byte:op_node.end_byte]
        expr = visit(node.child_by_field_name('operand'), code, info)
        match op:
            case "-":
                return TmNeg(expr)
            case "!":
                return TmNot(expr)
            case "~":
                return TmBitNot(expr)
            case _:
                assert False, f"Unary operator {op} not supported"
    elif name == "post_inc":
        expr = visit(node.children[0], code, info)
        return TmPostInc(expr)
    elif name == "post_dec":
        expr = visit(node.children[0], code, info)
        return TmPostDec(expr)
    elif name == "pre_inc":
        expr = visit(node.children[1], code, info)
        return TmPreInc(expr)
    elif name == "pre_dec":
        expr = visit(node.children[1], code, info)
        return TmPreDec(expr)
    elif name == "variable_identifier":
        text = code[node.start_byte:node.end_byte]
        if text in class_name_vocab:
            return TmType(TyClass(text))
        else:
            return TmVar(text)
    elif name == "parenthesized_expression":
        return TmParenthesis(visit(node.children[1], code, info))
    elif name == "object_creation_expression":
        ty = visit(node.child_by_field_name('type'), code, info)
        args = visit(node.child_by_field_name('arguments'), code, info)
        return TmNew(ty, args)
    elif name == "argument_list":
        if len(node.children) == 2:
            return TmList0()
        else:
            return visit(node.children[1], code, info)
    elif name == "term_list":
        if len(node.children) == 1:
            return TmList1(visit(node.children[0], code, info), TmList0())
        else:
            return TmList1(visit(node.children[0], code, info), visit(node.children[2], code, info))
    elif name == "field_access":
        base = visit(node.child_by_field_name('object'), code, info)
        field = visit(node.child_by_field_name('field'), code, info)
        return TmFieldAccess(field, base)
    elif name == "array_access":
        base = visit(node.child_by_field_name('array'), code, info)
        index = visit(node.child_by_field_name('index'), code, info)
        return TmArrayAccess(base, index)
    elif name == "method_invocation":
        base = visit(node.child_by_field_name('object'), code, info)
        method = visit(node.child_by_field_name('name'), code, info)
        args = visit(node.child_by_field_name('arguments'), code, info)
        return TmMethodInvocation(method, base, args)
    elif name == "method_invocation_no_obj":
        method = visit(node.child_by_field_name('name'), code, info)
        args = visit(node.child_by_field_name('arguments'), code, info)
        return TmMethodInvocationNoObj(method, args)
    elif name == "array_creation_expression":
        base_type = visit(node.child_by_field_name('type'), code, info)
        newinfo = info.copy()
        newinfo['base_type'] = TmNewArray0(base_type)
        return visit(node.child_by_field_name('dimensions'), code, newinfo)
    elif name == "dimensions_exprs":
        base_type = info['base_type']
        if len(node.children) == 3:
            return TmNewArray1(visit(node.children[1], code, info), base_type)
        else:
            newinfo = info.copy()
            newinfo['base_type'] = TmNewArray1(visit(node.children[1], code, info), base_type)
            return visit(node.children[3], code, newinfo)
    elif name == "skip":
        return StSkip()
    elif name == "expression_statement":
        expr = visit(node.children[0], code, info)
        return StExpression(expr)
    elif name == "statements":
        if len(node.children) == 1:
            return visit(node.children[0], code, info)
        else:
            return StConcat(visit(node.children[0], code, info), visit(node.children[3], code, info))
    elif name == "do_statement":
        body = visit(node.child_by_field_name('body'), code, info)
        cond = visit(node.child_by_field_name('condition'), code, info)
        return StDoWhile(body, cond)
    elif name == "while_statement":
        cond = visit(node.child_by_field_name('condition'), code, info)
        body = visit(node.child_by_field_name('body'), code, info)
        return StWhile(cond, body)
    elif name == "if_statement":
        cond = visit(node.child_by_field_name('condition'), code, info)
        consequence = visit(node.child_by_field_name('consequence'), code, info)
        return StIf(cond, consequence)
    elif name == "if_else_statement":
        cond = visit(node.child_by_field_name('condition'), code, info)
        consequence = visit(node.child_by_field_name('consequence'), code, info)
        alternative = visit(node.child_by_field_name('alternative'), code, info)
        return StIfElse(cond, consequence, alternative)
    elif name == "for_statement":
        init = visit(node.child_by_field_name('init'), code, info)
        cond = visit(node.child_by_field_name('condition'), code, info)
        update = visit(node.child_by_field_name('update'), code, info)
        body = visit(node.child_by_field_name('body'), code, info)
        return StFor(init, cond, update, body)
    elif name == "enhanced_for_statement":
        ty = visit(node.child_by_field_name('type'), code, info)
        var = visit(node.child_by_field_name('name'), code, info)
        arr = visit(node.child_by_field_name('array'), code, info)
        body = visit(node.child_by_field_name('body'), code, info)
        return StForeach(ty, var, arr, body)
    elif name == "return_statement":
        expr = visit(node.children[1], code, info)
        return StReturn(expr)
    elif name == "break_statement":
        return StBreak()
    elif name == "continue_statement":
        return StContinue()
    elif name == "class_declaration":
        name = visit(node.child_by_field_name('name'), code, info)
        body = visit(node.child_by_field_name('body'), code, info)
        return PgClassDecl(name, body)
    elif name == "class_body":
        ret = visit(node.named_children[-1], code, info)
        for i in range(len(node.named_children) - 2, -1, -1):
            ret = PgConcat(visit(node.named_children[i], code, info), ret)
        return ret
    elif name == "method_declaration":
        modifiers = visit(node.child_by_field_name('modifiers'), code, info)
        ty = visit(node.child_by_field_name('type'), code, info)
        name = visit(node.child_by_field_name('name'), code, info)
        args = visit(node.child_by_field_name('parameters'), code, info)
        body = visit(node.child_by_field_name('body'), code, info)
        return PgMethodDecl(modifiers, ty, name, args, body)
    elif name == "modifiers":
        text = code[node.start_byte:node.end_byte]
        text = text.split("[")[1].split("]")[0]
        return text
    elif name == "variable_declaration":
        name = visit(node.child_by_field_name('name'), code, info)
        ty = visit(node.child_by_field_name('type'), code, info)
        value = visit(node.child_by_field_name('value'), code, info)
        return StDeclInit(ty, name, value)
    elif name == "variable_declaration_no_init":
        name = visit(node.child_by_field_name('name'), code, info)
        ty = visit(node.child_by_field_name('type'), code, info)
        return StDeclNoInit(ty, name)
    elif name == "array_initializer":
        if len(node.named_children) == 0:
            return TmArray0()
        else:
            return visit(node.named_children[0], code, info)
    elif name == "array_elements":
        if len(node.named_children) == 1:
            return TmArray1(visit(node.named_children[0], code, info), TmArray0())
        else:
            return TmArray1(visit(node.named_children[0], code, info), visit(node.named_children[1], code, info))
    elif name == "formal_parameters":
        if len(node.named_children) == 0:
            return StSkip()
        else:
            return visit(node.named_children[0], code, info)
    elif name == "formal_parameter_list":
        if len(node.named_children) == 1:
            return StConcat(visit(node.named_children[0], code, info), StSkip())
        else:
            return StConcat(visit(node.named_children[0], code, info), visit(node.named_children[1], code, info))
    elif name == "program":
        return visit(node.named_children[0], code, info)
    else:
        assert False, f"{code}\nNode type `{name}` not supported"

with open("coq_model/datas/mbjp.json", "r") as file:
    mbjp_datas = json.load(file)
from mxeval.execution import check_correctness_java as check

def check_java(file_num, javaCode):
    mbjp_data=[data for data in mbjp_datas if data['task_id']==f"MBJP/{file_num}"][0]
    result=check(mbjp_data,javaCode,solution_complete=True)
    if not result['passed']:
        print(f"\nError in validating java version of: {file_num}")
        print(javaCode)
        print(result['result'])
        return False
    return True

def to_java(node):
    java_code = node.to_java()
    java_default_packages = ["java.lang.*", "java.util.*", "java.math.*", "java.io.*"]
    for package in java_default_packages:
        java_code = f"import {package};\n" + java_code
    return java_code
    
def check_correctness():
    with open("Utils/data/mbjp_dsl/mbjp_dsl_train.json") as f:
        train_data = json.load(f)
    with open("Utils/data/mbjp_dsl/mbjp_dsl_valid.json") as f:
        valid_data = json.load(f)
    with open("Utils/data/mbjp_dsl/mbjp_dsl_test.json") as f:
        test_data = json.load(f)
    datas = train_data + valid_data + test_data
    for data in datas:
        code = data["java_code"]
        tree = parser.parse(bytes(code, "utf-8"))
        node = visit(tree.root_node, code)
        javacode = to_java(node)
        if not check_java(data['num'], javacode):
            break
        print(f"Java code for {data['num']} is correct")

def trans_codet5_ans(output_dir = "Utils/output/dsl_codet5_test_ans/"):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    with open("Utils/output/test_ans_top10.json") as f:
        test_pred_text = json.load(f)
    #10个一组分组
    test_ans_top10 = []
    for i in range(0, len(test_pred_text), 10):
        test_ans_top10.append(test_pred_text[i:i+10])
    for index, codes in enumerate(test_ans_top10):
        for i in range(10):
            file_path = output_dir + f"{index}_{i}.txt"
            if os.path.exists(file_path):
                os.remove(file_path)
            with open(file_path, 'w') as f:
                try:
                    tree = parser.parse(bytes(codes[i], "utf-8"))
                    node = visit(tree.root_node, codes[i])
                    javacode = node.to_java()
                    f.write(javacode)
                except:
                    f.write("GrammarError!")

def trans_mbjp_dsl_ans():
    data_dir = "Utils/output/mbjp_dsl_test_ans/"
    for filename in os.listdir(data_dir):
        file_path = data_dir + filename
        if not file_path.endswith(".txt"):
            continue
        new_file_path = file_path.replace(".txt", ".java")
        if os.path.exists(new_file_path):
            os.remove(new_file_path)
        with open(file_path, 'r') as f:
            code = f.read()
        try:
            tree = parser.parse(bytes(code, "utf-8"))
            node = visit(tree.root_node, code)
            javacode = node.to_java()
        except Exception as e:
            print(f"Error in parsing {filename}: {e}")
            continue
        with open(new_file_path, 'w') as f:
            f.write(javacode)
        print(f"Java code for {filename} is generated")

if __name__ == "__main__":
    trans_codet5_ans()
