# Major-revision evaluation supplement

This directory contains the machine-readable evidence used by the revised
Evaluation and Appendix sections.

## RQ2 runtime

The four JSONL files in rq2_runtime_2b/ record the same 58 SuFu test tasks
with the 2B model under the no-check, syntactic-pruning, type-pruning, and
full dynamic-context configurations. The means reported in the paper are
computed from the wall_seconds field.

## Combined Java statistics

java_statistics_combined.json records the merged task counts, intervals,
and paired tests for MBJP, HumanEval-Java, and TransCoder-GFG. The merged unit
is 186 Java tasks. The score inputs remain in
../major_revision_20260824/scores/.

sufu_statistics.json records the 95% intervals and paired tests for the SuFu
results. Pass rates use the 58 tasks as the unit, and CER uses the generated
candidates; FSP is evaluated over task-level ranks.

## Frozen decode and rejection-sampling evidence (added 2026-09-07)

sufu_decode_stats_full_20260827.summary.json and sufu_decode_stats_full_20260827.json
are the sole evidence for every number in the paper's pruning/exhaustion table
(59.1% syntactic pruning, 8.2% type pruning, 167,295 grammar-valid expansions,
533 completed candidates with 113 = 21.2% rejected at the output boundary,
0 of 58 exhausted tasks, 330-step budget). They were copied from tmp/ (which
is not protected by git) per pending-edit items D1.

paperrecover_mbjp_rejectionsampling_b10_20260827_score_timeout10.json is the
authoritative score for the RQ3 rejection-sampling row (pass@1 = 10/67,
pass@10 = 24/67, CER = 0, 618 returned candidates), copied from tmp/ per
pending-edit item D2. SHA256SUMS covers every file in this directory.
