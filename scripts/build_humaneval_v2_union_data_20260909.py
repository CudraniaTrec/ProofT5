"""Build the aligned v2 union curriculum for the HumanEval aligned-retrain.

Curriculum (leak-free w.r.t. the frozen HumanEval-Java v15 16-task test set):
  proof/plain both sides, identical task set:
    - MBJP   608 rows: benchmark=='mbjp' rows of the clean-673 task dir
                     (its 65 HumanEval rows are EXCLUDED; HumanEval is taken
                     from the v15 fixed train split instead)
    - HumanEval v15 train 146 rows (fixed 90/10 split, disjoint from test)
    - TransCoder-GFG v13 train 414 rows
  Total 1168 tasks. All three source dirs are hash-audited in
  artifacts/major_revision_20260824/MANIFEST.json.

Leakage rule: a union row is rejected if its java body equals any of the 16
v15-test java bodies (the frozen test.pkl). HE v15 train is disjoint by the
published split; MBJP/GFG rows are cross-benchmark and cannot match HE tests;
the check is still run exhaustively over all 1168 rows.
"""

import hashlib
import json
import os
import pickle
import shutil
import sys

REPO = "/data2/x/hzc/prooft5"
OUT = f"{REPO}/Utils/data/java_mbjp_hev15_gfg414_union_t5gemma2_20260909"

MBJP_PROOF = f"{REPO}/Utils/data/mbjp_humaneval_half_train_t5gemma2_20260731/train.pkl"
MBJP_PLAIN = f"{REPO}/t5_llm/data/java_mbjp_humaneval_half_train_t5.json"
HEV15_DIR = f"{REPO}/Utils/data/java_humaneval_mbjp_native_semanticsupport_split90_10_t5gemma2_20260822_v15"
GFG414_DIR = f"{REPO}/Utils/data/java_transcoder_gfg_mbjp_native_prompt_split80_20_t5gemma2_20260819_v13"


def h(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def main():
    # ---- sources -------------------------------------------------------
    mbjp_proof = pickle.load(open(MBJP_PROOF, "rb"))
    mbjp_rows = [r for r in mbjp_proof if r.get("benchmark") == "mbjp"]
    hev15_rows = pickle.load(open(f"{HEV15_DIR}/train.pkl", "rb"))
    gfg_rows = pickle.load(open(f"{GFG414_DIR}/train.pkl", "rb"))
    assert len(mbjp_rows) == 608, len(mbjp_rows)
    assert len(hev15_rows) == 146, len(hev15_rows)
    assert len(gfg_rows) == 414, len(gfg_rows)

    test_pkl = pickle.load(open(f"{HEV15_DIR}/test.pkl", "rb"))
    test_bodies = {r["java_code"].strip() for r in test_pkl}
    assert len(test_bodies) == 16

    # ---- proof union ---------------------------------------------------
    proof_union = mbjp_rows + hev15_rows + gfg_rows
    dup = []
    seen = set()
    for r in proof_union:
        key = (r["java_code"].strip(), tuple(r["nl"]))
        if key in seen:
            dup.append(key)
        seen.add(key)
    leaked = [
        (r["java_code"].strip()[:60])
        for r in proof_union
        if r["java_code"].strip() in test_bodies
    ]
    print(f"proof union rows: {len(proof_union)} (608+146+414)")
    print(f"proof duplicates: {len(dup)}")
    print(f"proof HE-test leaks: {len(leaked)}")

    # ---- plain union ---------------------------------------------------
    mbjp_plain_all = json.load(open(MBJP_PLAIN))
    mbjp_plain = [
        r for r in mbjp_plain_all if r.get("type") == "train" and r.get("benchmark") == "mbjp"
    ]
    assert len(mbjp_plain) == 608, len(mbjp_plain)
    norm = []
    for r in mbjp_plain:
        code, prompt = r["code"], r["prompt"]
        body = code[len(prompt):] if code.startswith(prompt) else code
        nr = {k: v for k, v in r.items() if k != "code"}
        nr["canonical_solution"] = body.strip()
        nr["type"] = "train"
        norm.append(nr)
    he_plain = json.load(open(f"{HEV15_DIR}/train_t5_plain_format.json"))
    gfg_plain = json.load(open(f"{GFG414_DIR}/train_t5_plain_format.json"))
    for r in he_plain:
        r["type"] = "train"
    for r in gfg_plain:
        r["type"] = "train"
    plain_union = norm + he_plain + gfg_plain
    print(f"plain union rows: {len(plain_union)}")

    # ---- leakage check on plain (by test case body present in plain test) ----
    plain_test_bodies = {r["test"].strip() for r in test_pkl}
    leaked_plain = sum(1 for r in plain_union if r.get("test", "").strip() in plain_test_bodies)
    print(f"plain rows sharing a test-case body with HE test: {leaked_plain}")

    # ---- write union task dir ------------------------------------------
    os.makedirs(OUT, exist_ok=True)
    with open(f"{OUT}/train.pkl", "wb") as f:
        pickle.dump(proof_union, f)
    with open(f"{OUT}/train_t5_plain_format.json", "w") as f:
        json.dump(plain_union, f, indent=1)
    # empty valid/test, config, rules, tokenizers
    with open(f"{OUT}/valid.pkl", "wb") as f:
        pickle.dump([], f)
    with open(f"{OUT}/test.pkl", "wb") as f:
        pickle.dump([], f)
    cfg = json.load(open(f"{HEV15_DIR}/config.json"))
    cfg.update(
        {
            "train_rows": len(proof_union),
            "valid_rows": 0,
            "test_rows": 0,
            "NlLen": 512,
            "CodeLen": 747,
            "max_code_len": 719,
            "data_revision": "humaneval-v2-union-mbjp608-he146-gfg414-20260909",
            "task": "java_mbjp_hev15_gfg414_union_t5gemma2_20260909",
        }
    )
    with open(f"{OUT}/config.json", "w") as f:
        json.dump(cfg, f, indent=1)
    shutil.copy(f"{HEV15_DIR}/rules.pkl", f"{OUT}/rules.pkl")
    shutil.copy(f"{HEV15_DIR}/coq_tokenizer.pkl", f"{OUT}/coq_tokenizer.pkl")
    shutil.copy(f"{HEV15_DIR}/tokenizer.pkl", f"{OUT}/tokenizer.pkl")

    print("OUT:", OUT)
    for p in ["train.pkl", "train_t5_plain_format.json", "rules.pkl", "config.json"]:
        print(f"{p}\t{h(f'{OUT}/{p}')}")


if __name__ == "__main__":
    main()
