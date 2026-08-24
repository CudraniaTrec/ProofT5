# Java benchmark experiment master ledger

Status: frozen on 2026-08-24.

The authoritative full report is
`docs/MAJOR_REVISION_FINAL_PACKAGE_20260824.md`; the machine-readable artifact
map is `artifacts/major_revision_20260824/MANIFEST.json`. If an older report or
handoff disagrees with these two files, the frozen 2026-08-24 package wins.

| benchmark | model | train pass@1 | train pass@10 | test pass@1 | test pass@10 |
|---|---|---:|---:|---:|---:|
| MBJP (608/0/67) | T5Gemma2 | 506/608 (83.22%) | 564/608 (92.76%) | 9/67 (13.43%) | 22/67 (32.84%) |
| MBJP (608/0/67) | **ProofT5 (ours)** | not fully evaluated | not fully evaluated | **17/67 (25.37%)** | **29/67 (43.28%)** |
| HumanEval-Java v15 (146/0/16) | T5Gemma2 | 145/146 (99.32%) | 145/146 (99.32%) | 2/16 (12.50%) | 4/16 (25.00%) |
| HumanEval-Java v15 (146/0/16) | **ProofT5 (ours)** | not fully evaluated | not fully evaluated | **8/16 (50.00%)** | **9/16 (56.25%)** |
| TransCoder-GFG v13 (414/0/103) | T5Gemma2 | 408/414 (98.55%) | 411/414 (99.28%) | 14/103 (13.59%) | 28/103 (27.18%) |
| TransCoder-GFG v13 (414/0/103) | **ProofT5 (ours)** | not fully evaluated | not fully evaluated | **31/103 (30.10%)** | **48/103 (46.60%)** |

Reporting constraints:

- validation is empty in every final setting;
- HumanEval v15 is an exploratory 146/0/16 split and is ancestor-mixed;
- the matched HumanEval lineage-unseen 11-row result is ordinary 1/11 and
  3/11 versus ProofT5 4/11 and 5/11;
- GFG problem 44 is counted fail-closed as ten failed candidates after an
  isolated decoder run exceeded two hours, so its denominator remains 103;
- ProofT5 train-set cells are genuinely unmeasured, not replaced with probes;
- CoqView is not part of the frozen main table or remaining experiment queue.
