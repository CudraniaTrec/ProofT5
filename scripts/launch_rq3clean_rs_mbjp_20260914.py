#!/usr/bin/env python3
"""RQ3 realignment stage 4: adaptive rejection-sampling resample rounds on the
clean673 checkpoint. Mirrors the frozen protocol: per round, resample the
problems whose compile-pass slots are still unfilled, seed = 272567 + r*1000,
then assemble control + rounds and score."""
import json, subprocess, sys, os
from collections import defaultdict

PY = "/data2/x/hzc/.uv-envs/prooft5-t5gemma-py313/bin/python"
OUTROOT = "Utils/output/mbjp_original_test_t5gemma2_20260731_test_ans"
MODEL = "t5_llm/models/t5gemma2-2b_java_clean673_noleak_b5_lr5em5_pass30_20260811_after_clean_coqview/20260811_after_clean_coqview/epoch_20"
CONTROL = f"{OUTROOT}/rq3clean_mbjp_ordinary_matched_b10_merged_20260914"
TAG_BASE = "rq3clean_mbjp_rs_round{r}_20260914"
GPU = sys.argv[1] if len(sys.argv) > 1 else "1"

def compile_errors_by_problem(path):
    d = json.load(open(path))
    errs = defaultdict(int)
    for p, c in d["compile_error_candidate_ids"]:
        errs[p] += 1
    return errs, d

def assemble(rounds):
    tag = "rq3clean_mbjp_rejectionsampling10arm_b10_20260914"
    out = f"{OUTROOT}/{tag}"
    if os.path.exists(out):
        subprocess.run(["rm", "-rf", out], check=True)  # assembly is deterministic; intermediate dir is rebuildable
    dirs = ",".join(f"{OUTROOT}/{TAG_BASE.format(r=r)}" for r in rounds)
    subprocess.run([PY, "-m", "baselines.java_baselines.run_rejection_sampling_assembly",
                    "--control_dir", CONTROL, "--resample_dirs", dirs,
                    "--output_dir", out, "--expected_problems", "67",
                    "--expected_candidates", "10", "--max_arms_per_problem", "10"],
                   check=True, stdout=open(f"tmp/rq3clean_rs_assembly_20260914.log", "ab"))
    m = json.load(open(f"{out}/baseline_manifest.json"))
    return tag, m["total_missing_slots"], m.get("unfilled_problem_slots") or m.get("problems_fully_filled")

# start from control compile errors
errs, ctrl = json.load(open("artifacts/rq3clean_mbjp_20260914/scores/ordinary_matched_score.json")), None
errs = defaultdict(int)
for p, c in json.load(open("artifacts/rq3clean_mbjp_20260914/scores/ordinary_matched_score.json"))["compile_error_candidate_ids"]:
    errs[p] += 1
rounds = []
tag = None
for r in range(2, 11):
    # unfilled = problems with any compile error among control+kept rounds; recompute from assembly
    if rounds:
        tag, missing, _ = assemble(rounds)
        counts = defaultdict(int)
        for fn in os.listdir(f"{OUTROOT}/{tag}"):
            if fn.endswith(".txt"):
                counts[int(fn.split("_")[0])] += 1
        idx = sorted(p for p in counts if counts[p] < 10)
    else:
        idx = sorted(errs)
    if not idx:
        print(f"round {r}: no unfilled problems, stop"); break
    t = TAG_BASE.format(r=r)
    if not os.path.exists(f"{OUTROOT}/{t}/baseline_manifest.json"):
        seed = 272567 + r * 1000
        log = open(f"tmp/{t}.log", "w")
        rc = subprocess.run([PY, "-m", "baselines.java_baselines.run_repilot",
            "--model", MODEL, "--model_family", "seq2seq",
            "--tokenizer", "Utils/models/t5gemma-2-1b-1b",
            "--dataset_json", "t5_llm/data/java_mbjp_original_test_t5.json", "--dataset_split", "test",
            "--score_task", "mbjp_original_test_t5gemma2_20260731", "--score_split", "test",
            "--output_tag", t, "--device", f"cuda:{GPU}", "--dtype", "bf16", "--local_files_only",
            "--candidates", "10", "--max_input_tokens", "1024", "--max_new_tokens", "1024",
            "--temperature", "0.8", "--top_k", "50", "--top_p", "0.95", "--greedy_first",
            "--decoder_control_no_jdt", "--seed", str(seed), "--indices", ",".join(map(str, idx))],
            stdout=log, stderr=subprocess.STDOUT).returncode
        if rc != 0:
            print(f"round {r} FAILED rc={rc}"); sys.exit(1)
    rounds.append(r)
    print(f"round {r} done, indices={idx[:20]}{'...' if len(idx)>20 else ''} n={len(idx)}")

tag, missing, filled = assemble(rounds)
print("final tag", tag, "missing", missing, "fully_filled", filled)
subprocess.run([PY, "score_java_no_write.py", "--task", "mbjp_original_test_t5gemma2_20260731",
                "--split", "test", "--output_tag", tag, "--timeout", "10",
                "--json_out", "artifacts/rq3clean_mbjp_20260914/scores/rejectionsampling10arm_score.json"],
               check=True, stdout=open("tmp/rq3clean_rs_score_20260914.log", "w"), stderr=subprocess.STDOUT)
d = json.load(open("artifacts/rq3clean_mbjp_20260914/scores/rejectionsampling10arm_score.json"))
print("pass1", d["pass1"], "pass10", d["pass10"], "CER", d["compile_error_rate"], d["compile_errors"], "/", d["total_tested"])
m = json.load(open(f"{OUTROOT}/{tag}/baseline_manifest.json"))
print("kept_from_arm", m["kept_from_arm"], "total_draws", m["total_draws"])
print("STAGE4_DONE")
