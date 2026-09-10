# Major-revision evaluation supplement

This directory contains the machine-readable evidence used by the revised
Evaluation and Appendix sections.

## RQ2 runtime

The four JSONL files in rq2_runtime_220m/ (added 2026-09-08) record the same
58 SuFu test tasks with the TyFlow-220M model under the no-check,
syntactic-pruning, type-pruning, and full dynamic-context configurations; the
paper's Time column (5.70 / 5.34 / 11.07 / 15.62 s) is computed from the
wall_seconds field of these files. Timing protocol: identical checkpoint,
decoding toggles, beam size, candidate multiplier, and vocabulary as the
functional-metric runs; the four configurations were executed sequentially on
a single GPU (CUDA_VISIBLE_DEVICES=0) with batch_size_eval=1, and all 4 x 58
tasks completed.

The four JSONL files in rq2_runtime_2b/ are the earlier 2B-model measurement
of the same protocol; they are superseded by rq2_runtime_220m/ as the source
of the paper's Time column and kept only for the record.

A 2026-09-08 reproduction of the base and syntactic-pruning configurations
(rq2_runtime_220m_rerun_20260908/, same script, same GPU, same protocol)
gives 5.66 versus 5.32 s/task (-5.97%) with identical step counts
(183.2 versus 164.6 mean decoding steps per task), confirming that the
negative Time delta of syntactic pruning is a real early-termination effect:
the search stops once every beam completes, and masking ill-formed decisions
lets beams finish sooner. Decoding is deterministic, so the step counts
replicate exactly; wall time varies by about one percent between runs.

Per-decoding-step wall times (total wall / total steps), reported alongside
per-task time in the paper's Time column group: base 31.1 ms/step,
+ syntactic pruning 32.4 (+4.2%), + type pruning 43.7 (+40.5%),
+ dynamic typing context 59.6 (+91.6%). Every component strictly increases
the per-step cost; syntactic pruning alone reduces the per-task total
because its 10% step reduction outweighs its 4% per-step overhead.

## Combined Java statistics

java_statistics_combined.json records the merged task counts, intervals,
and paired tests for MBJP, HumanEval-Java, and TransCoder-GFG. The merged unit
is 186 Java tasks. The score inputs remain in
../major_revision_20260824/scores/.

A by_scale.220M block is appended to the same JSON; it covers the
220M (CodeT5-220M vs TyFlow-220M) MBJP comparison only, because tab:model-results
reports the 220M scale on MBJP alone and the HumanEval-Java / TransCoder-GFG
220M per-task arrays were not preserved alongside the frozen aggregate counts.

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
