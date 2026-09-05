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
