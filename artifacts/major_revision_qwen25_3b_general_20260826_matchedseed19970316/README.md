# Qwen2.5-3B Base Java/Coq checkpoint sweep and iterative feedback

Status: complete evidence, 2026-08-26. This directory supplements rather
than modifies the frozen 2026-08-24 result package.

## Matched checkpoint sweep

- Base: official non-Coder, non-Instruct `Qwen/Qwen2.5-3B`.
- Train data: the same 673 clean Java rows; no validation rows.
- Seed: 19970316; full fine-tuning for 20 passes; saves at 5/10/15/20.
- Ordinary target: prompt followed by the complete Java source.
- Method target: Coq representation with syntax pruning only. CoqView and
  the Coq checker are disabled.
- Evaluation: fixed MBJP 67-task test set, ten candidates per task.

| checkpoint | ordinary pass@1 | ordinary pass@10 | Coq-syntax pass@1 | Coq-syntax pass@10 | ordinary compile errors | Coq compile errors | Coq missing |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 5 | 30/67 | 49/67 | 22/67 | 34/67 | 98/670 | 63/664 | 6 |
| 10 | 37/67 | 46/67 | 22/67 | 36/67 | 37/670 | 94/670 | 0 |
| 15 | 38/67 | 48/67 | 23/67 | 36/67 | 32/670 | 85/670 | 0 |
| 20 | 38/67 | 48/67 | 22/67 | 36/67 | 36/670 | 84/670 | 0 |

This is a negative result for the Coq-syntax arm at all saved checkpoints.
The eight score JSONs in `scores/` are the result authority. MBJP must not be
used to select a deliberately weak ordinary checkpoint and a strong method
checkpoint. A single paper-facing checkpoint needs a training-only selection
rule; otherwise report the trajectory.

## Untuned-Base iterative feedback

This experiment loads the untouched Base model. Each round sees only the
task and, after a standalone compilation failure, `javac` diagnostics. It
never receives hidden tests or test results.

| condition | pass@1 | pass@10 | scorer compile errors |
|---|---:|---:|---:|
| exact round-0 control | 13/67 (19.40%) | 49/67 (73.13%) | 433/670 |
| final, at most two repairs | 14/67 (20.90%) | 52/67 (77.61%) | 404/670 |

The final run contains all 670 candidates. It made 1,004 model calls,
including 334 repair calls; consumed 407,356 input and 413,579 output tokens;
and recorded 7,806.13 summed candidate-seconds. The trajectory summary is
`iterative_cost_summary.json`; exact initial and final scores are in
`scores/iterative_qwen25_3b_base_{round0,final}.json`.

The Java adapter was corrected before the formal run to compile a public top-
level type under its required filename and to exclude echoed diagnostic text
from extracted source. These changes affect standalone compilation only and
do not expose semantic tests. The pre-fix and fixed one-problem smoke outputs
are retained separately for provenance.
