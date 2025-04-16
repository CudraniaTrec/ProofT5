import json, os
os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'
from datasets import load_dataset
dataset = load_dataset("THUDM/humaneval-x", "java")
datas = []
for data in dataset["test"]:
    taskid = data.get("task_id", None)
    prompt = data.get("prompt", None)
    declaration = data.get("declaration", None)
    canonical_solution = data.get("canonical_solution", None)
    test = data.get("test", None)
    if not taskid or not prompt or not canonical_solution or not test or not declaration:
        continue
    code = declaration + canonical_solution
    if test.startswith("public "):
        test = test[7:]
    with open(f"datas/humaneval/{taskid.replace("/", "_")}.java", "w") as f:
        f.write(code)
    datas.append({
        "task_id": taskid,
        "prompt": prompt,
        "code": code,
        "test": test
    })
with open("datas/humaneval.json", "w") as f:
    json.dump(datas, f, indent=4)