from openai import OpenAI
from tqdm import tqdm
import json, os, subprocess, re
with open("apiKey.json", "r") as f:
    apiKey = json.load(f)
client = OpenAI(**apiKey)

generator_path = "/data3/hzc/ProofT5/SuFu/SuFu/build/executor/gen"
interpreter_path = "/data3/hzc/ProofT5/SuFu/SuFu/surface/f"
test_file_path = "/data3/hzc/ProofT5/SuFu/SuFu/test.f"
test_out_path = "/data3/hzc/ProofT5/SuFu/SuFu/test.out"

def find_all_files(directory):
    res = []
    for item in os.listdir(directory):
        full_path = os.path.join(directory, item)
        if os.path.isfile(full_path):  # 如果是文件，则添加到结果列表
            res.append((full_path, item))
        elif os.path.isdir(full_path):  # 如果是目录，则递归调用
            res.extend(find_all_files(full_path))
    return res

files = find_all_files("benchmark")
labeled_files = set(os.listdir("label"))
sufu_progs = []

with open("info.json", "r") as f:
    info = json.load(f)
    info["types"] = {}
prompts = info["prompts"]

def replace_ptree(code):
    lines = [l.strip() for l in code.splitlines() if l.strip()]
    for i in range(len(lines)):
        if lines[i].startswith("Inductive PTree"):
            if lines[i+1].startswith("Inductive PList"):
                lines[i] = lines[i][:-1]
                lines[i+1] = lines[i+1].replace("Inductive", 'with')
                break
    return "\n".join(lines)

def replace_inductive(old_code, new_code):
    ret_code = ""
    pattern = r"^[A-Z]\w*\s*=\s*.*?;$" # match Xx = Yy;
    for line in new_code.split("\n"):
        if line.startswith("Inductive"):
            assert len(line.split(" "))==2, f" inductive error, line:{line}"
            type_name = line.split(" ")[1][:-1] #remove ;
            start_byte = old_code.index(f"Inductive {type_name}")
            end_byte = old_code.index(";", start_byte)
            definition = old_code[start_byte:end_byte+1]
            if type_name not in info["types"]:
                info["types"][type_name]= []
            if definition not in info["types"][type_name]:
                info["types"][type_name].append(definition)
            ret_code += definition + "\n"
        else:
            if re.match(pattern, line):
                type_name = line.split("=")[0].strip()
                if type_name not in info["types"]:
                    info["types"][type_name]= []
                if line not in info["types"][type_name]:
                    info["types"][type_name].append(line)
            ret_code += line + "\n"
    return ret_code

def filter_at(new_code, filename):
    if filename in ["incre-tests-autolifter-autolifter-base"]:
        assert False, f"ignore"
    new_code = new_code.replace("@Start ", "")
    assert new_code.count("@")== new_code.count("@Input "), f"@ error" #only @Input
    lines = new_code.splitlines()
    ret_code = ""
    for line in lines:
        if "@Input" in line:
            pattern = r'@Input\s+(\w+)\s*=\s*Int'
            line = re.sub(pattern, r'\1 = 100', line)
        ret_code += line + "\n"
    assert "@" not in ret_code, f"@ error: {ret_code}" # only @Input xx = Int
    return ret_code

def split_lib_task_code(old_code, new_code):
    commands = [command.strip() for command in new_code.split(";")]
    lib_code, task_code = "", ""
    task_code_len, task_code_commands = 0,0
    for command in commands[-1::-1]:
        if command.startswith("Inductive") or command.startswith("@"):
            break
        l = len(command.splitlines())
        task_code= command + ";\n" + task_code
        task_code_commands+=1
        task_code_len += l
        if task_code_len >= 10 or task_code_commands >= 3:
            break
    for command in commands[:-task_code_commands]:
        lib_code += command + ";\n"
    return lib_code, task_code

def gen_tests(code):
    with open(test_file_path, "w") as f:
        f.write(code)
    res = subprocess.run([generator_path], capture_output=True, text=True)
    with open(test_out_path, "r") as f:
        test_code = f.read()
    with open(test_file_path, "a") as f:
        f.write(test_code)
    res = subprocess.run([interpreter_path, test_file_path], capture_output=True, text=True)
    output = res.stdout
    # assert len(output.splitlines()) <= 30, f"too many lines({len(output.splitlines())}) in output: {output}"
    return test_code, output

def gen_desc(file_name, code, inputs, outputs):
    messages = [
            {
                "role": "system",
                "content": "You are a helpful assistant, you should help me generate a natural language description about the sufu program based on the file name, code, and the input-output of the file. "
            },
            {
                "role" : "assistant",
                "content": "OK, I will generate a natural language description about the sufu program based on the file name, code, and the input-output of the file, and wrap the description in a markdown format: ```nl\n ... \n```"
            },
    ]
    for example in prompts["examples"]:
        messages.append({
            "role": "user",
            "content": prompts["template"].replace("<file_name>", example["file_name"])
            .replace("<code>", example["code"])
            .replace("<inputs>", example["inputs"])
            .replace("<outputs>", example["outputs"])
        })
        messages.append({
            "role": "assistant",
            "content": example["prompt"]
        })
    messages.append({
        "role": "user",
        "content": prompts["template"].replace("<file_name>", file_name)
        .replace("<code>", code)
        .replace("<inputs>", inputs)
        .replace("<outputs>", outputs)
    })
    model1 = "yunwu/gpt-4.1-2025-04-14"
    model2 = "yunwu/o4-mini-2025-04-16"
    response = client.chat.completions.create(
        messages=messages,
        model=model1,
        temperature=0.1,
    )
    ans = response.choices[0].message.content
    pattern = r'```nl\s+(.*?)\s+```'
    matches = re.findall(pattern, ans, re.DOTALL)
    if len(matches)==0:
        return ans
    else:
        return matches[0]

def main():
    for file_path, file_name in tqdm(files):
        with open(file_path, "r") as f:
            code = f.read()
        new_file_name = f"incre-tests-{'-'.join(file_path.split('/')[1:])}"[:-2]
        if new_file_name in labeled_files:
            labeled_files.remove(new_file_name)
            with open("label/"+new_file_name, "r") as f:
                labeled_code = f.read()
            try:
                labeled_code = labeled_code.replace("Unit", "unit")
                labeled_code = replace_inductive(code, labeled_code)
                labeled_code = filter_at(labeled_code, new_file_name)
                lib_code, task_code = split_lib_task_code(code, labeled_code)
                test_code, output = gen_tests(replace_ptree(labeled_code))
                desc = gen_desc(new_file_name, labeled_code, test_code, output)
                # desc = ""
                sufu_progs.append({"file_name": new_file_name, "desc": desc, 
                                "code": labeled_code, "lib_code": lib_code, "task_code": task_code,
                                "tests": test_code, "output": output})
            except Exception as e:
                print(f"file:{new_file_name}, err: {e}")
            
    print(f"Generated {len(sufu_progs)} sufu programs")
    with open("sufu.json", "w") as f:
        json.dump(sufu_progs, f, indent=4)
    with open("info.json", "w") as f:
        json.dump(info, f, indent=4)
    print(f"redundant files: {labeled_files}")
    error_sufu = []
    for p in sufu_progs:
        if "test.f" in p['output']:
            error_sufu.append({
                "file_name": p['file_name'],
                "code" : p['code'],
                "tests": p['tests'],
                "output": p['output']
            })
    with open("error_sufu.json", "w") as f:
        json.dump(error_sufu, f, indent=4)
    print(f"error_sufu len: {len(error_sufu)}")

def test_gen_desc():
    file_name = "incre-tests-synduce-tailopt-mps"
    code = "\nInductive List = nil Unit | cons {Int, List};\n\nmax = \\x: Int. \\y: Int. \n    if (> x y) then x\n    else y;\n\nspec = \\xs: List. \n    (fix (\n    \\f: List -> {Int, Int}. \\xs: List. \n    match xs with\n      nil _ -> {0, 0}\n    | cons {h, t} -> \n        let r = (f t) in \n            {+ h r.1, max 0 (+ h r.2)}\n    end\n) xs).2;\n\nsnoc = fix (\n    \\f: List -> Int -> List. \\xs: List. \\w: Int. \n    match xs with\n      nil _ -> cons {w, nil unit}\n    | cons {h, t} -> cons {h, f t w}\n    end\n);\n\nrepr = fix (\n    \\f: Compress List -> List -> Compress List. \\pre: Compress List. \\xs: List. \n    match xs with\n      nil _ -> pre\n    | cons {h, t} -> f (align (label (snoc (unlabel pre ) h) ) ) t\n    end\n) (let tmp1 = (nil unit) in \n        align (label tmp1 ) );\n\nmain = \\xs: List. \n    let tmp2 = (repr xs) in \n        align (spec (unlabel tmp2 )) ;\n\n"
    inputs = "main (cons {(-3), (cons {(-1), (cons {(3), (cons {(1), (cons {(3), (nil unit)})})})})});\nmain (cons {(5), (cons {(-1), (cons {(2), (cons {(5), (cons {(4), (cons {(-2), (cons {(-1), (cons {(0), (nil unit)})})})})})})})});\nmain (cons {(-4), (cons {(-1), (cons {(4), (cons {(3), (cons {(-3), (cons {(3), (nil unit)})})})})})});\nmain (cons {(-2), (cons {(-1), (cons {(5), (cons {(-4), (cons {(-2), (nil unit)})})})})});\nmain (nil unit);\nmain (cons {(2), (cons {(-5), (cons {(-1), (cons {(-4), (nil unit)})})})});\nmain (nil unit);\nmain (cons {(-3), (cons {(1), (cons {(-3), (cons {(-3), (cons {(-4), (nil unit)})})})})});\nmain (nil unit);\nmain (cons {(3), (cons {(0), (cons {(-3), (cons {(1), (nil unit)})})})});\n"
    outputs = "\nList :: List. <nil Unit | cons {Int,List}>\n nil : Unit -> List'. <nil Unit | cons {Int,List'}>\n cons : {Int,List} -> List'. <nil Unit | cons {Int,List'}>\n max : Int -> Int -> Int\nspec : List -> Int\nsnoc : List -> Int -> List'. <nil Unit | cons {Int,List'}>\nrepr : List -> Compress List\nmain : List -> Int\n3 : Int\n15 : Int\n2 : Int\n2 : Int\n0 : Int\n2 : Int\n0 : Int\n0 : Int\n0 : Int\n3 : Int\n"
    print(gen_desc(file_name, code, inputs, outputs))

if __name__ == "__main__":
    main()