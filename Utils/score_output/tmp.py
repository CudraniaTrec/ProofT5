import json
with open("checkpoint-510.jsonl", "r") as f:
    data = [json.loads(line) for line in f]
for index, item in enumerate(data):
    codes_top10 = item["code"]
    for i, code in enumerate(codes_top10):
        with open(f"/data4/hzc/ProofT5/Utils/output/Qwen2.5-0.5B_sufu_test_ans/{index}_{i}.txt", "w") as f:
            f.write(code)