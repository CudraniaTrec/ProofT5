# CodeGemma-2B → ProofT5 rules, BOS-matched retraining

This directory is the protocol-corrected follow-up to
`major_revision_codegemma_rules_20260826_v5`.  It keeps the CodeGemma-2B
decoder backbone and changes the output representation to the frozen ProofT5
DSL/rule vocabulary.  The natural-language side is retokenized with the local
CodeGemma tokenizer **including its BOS token**, and the model is trained for
five pretraining passes (9,856 rows) followed by thirty Java passes (673 rows).
The MBJP test split is 67 tasks, ten candidates per task, and is never used for
training or checkpoint selection.  JavaDoc input/output examples are removed
from the model prompt; the frozen Java harness is used only for scoring.

The main evaluation uses syntax pruning only (`disable_coq_check=true`),
beam size 10, length penalty 0.1, and 298 maximum rule tokens.  All 670
candidate slots are materialized; if a grammar search cannot produce a complete
tree, an explicit invalid placeholder is written and counted as a compile
failure rather than as a missing candidate.

| checkpoint | pass@1 | pass@10 | compile errors | timeouts | missing |
|---|---:|---:|---:|---:|---:|
| epoch 5 | 17/67 (25.37%) | 27/67 (40.30%) | 171/670 | 6 | 0 |
| epoch 10 | 21/67 (31.34%) | 31/67 (46.27%) | 139/670 | 6 | 0 |
| epoch 15 | 21/67 (31.34%) | 32/67 (47.76%) | 138/670 | 6 | 0 |
| epoch 20 | 19/67 (28.36%) | 30/67 (44.78%) | 136/670 | 5 | 0 |
| epoch 25 | 18/67 (26.87%) | 31/67 (46.27%) | 145/670 | 6 | 0 |
| final | 18/67 (26.87%) | 31/67 (46.27%) | 136/670 | 6 | 0 |

The strongest standard-beam point is epoch 15.  It remains below the matched
raw CodeGemma-2B control (29/67 pass@1, 48/67 pass@10) on the same sanitized
MBJP protocol.  A diagnostic epoch-15 run with beam size 20, scoring only its
first ten slots, obtains 23/67 pass@1 and 33/67 pass@10; this is not the main
protocol and is recorded separately in
`mbjp_syntax_score_epoch15_b20_top10.json`.

The earlier v5 run omitted BOS during both training and evaluation.  Adding
BOS only at evaluation caused 2/67 and 7/67, confirming that the mismatch had
to be corrected by retraining.  The BOS-matched run improves substantially,
but the parity target is still not met; further work would require a stronger
rule-output head/training curriculum or an explicitly declared hybrid fallback
to raw CodeGemma, rather than silently changing the comparison.

The `*_complete.json` files are the authoritative rescored files after the
distributed writer finished all ranks; the first unsuffixed file is retained as
the initial score attempt for audit.  The model and data
artifacts are:

- `../Utils/models/Modelcodegemma2b_pretrain_rules_full5pass_20260827_bos_v1/`
- `../Utils/models/Modelcodegemma2b_java_rules_full30pass_20260827_bos_v1/`
- `../Utils/data/codegemma2b_causal_dsl_manifest_20260827_bos_v1.json`
