from openai import OpenAI
import json, os
with open("apiKey.json", "r") as f:
    apiKey = json.load(f)
client = OpenAI(**apiKey)

def find_all_files(directory):
    """
    递归地查找指定目录下的所有文件及其路径。
    """
    res = []
    for item in os.listdir(directory):
        full_path = os.path.join(directory, item)
        if os.path.isfile(full_path):  # 如果是文件，则添加到结果列表
            res.append((full_path, item))
        elif os.path.isdir(full_path):  # 如果是目录，则递归调用
            res.extend(find_all_files(full_path))
    return res

def gen_desc(file_path, code):
    file_name = file_path.split("/")[-1]
    response = client.chat.completions.create(
        messages=[
            {
                "role": "system",
                "content": "You are a helpful assistant, you should help me generate a natural language description about the sufu program based on the file name and the code in the file. "
            },
            {
                "role": "user",
                "content": f"File name: {file_name}\nCode:\n{code}\n"
            }
        ],
        model="yunwu/o3-mini",
    )
    ans = response.choices[0].message.content
    print(ans)
    return {
        "file_name": file_name,
        "desc": ans,
        "code": code   
    }

files = find_all_files("benchmark")
labeld_files = set(os.listdir("label"))
sufu_progs = []
for file_path, file_name in files:
    with open(file_path, "r") as f:
        code = f.read()
    new_file_name = f"incre-tests-{'-'.join(file_path.split('/')[1:])}"[:-2]
    # if '@' in code:
    #     continue
    if new_file_name in labeld_files:
        labeld_files.remove(new_file_name)
        sufu_progs.append({"file_name": file_name, "desc": "", "code": code})

print(len(sufu_progs))
print(labeld_files)