import json
with open("opencoder-sft-java.json", 'r') as f:
    data = json.load(f)
print(len(data))
print(json.dumps(data[0], indent=2, ensure_ascii=False))