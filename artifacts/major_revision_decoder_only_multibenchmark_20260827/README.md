# Decoder-only multi-benchmark pilot (2026-08-27)

This artifact is a model-selection pilot for the expanded decoder-only control
comparison.  It does not replace the frozen major-revision results.  The
HumanEval-Java v15 and TransCoder-GFG v13 rows below use the sanitized inputs
under `inputs/`, which contain no JavaDoc input/output examples.  SuFu uses the
frozen original 58-task test split and the source-prefix protocol; its tests
and interpreter outputs are used only by the scorer.

The current candidate pool intentionally excludes Llama-family checkpoints;
MiMo-7B Base is the larger non-Llama candidate requested for this round.

## Protocol

* HumanEval-Java v15: 16 tasks; TransCoder-GFG v13: 103 tasks; SuFu original:
  58 tasks.  The pilot uses one greedy candidate per task (`pass@1`) to rank
  candidates before the expensive 10-candidate run.
* Code-completion Base checkpoints use `prefix_completion` (or SuFu
  `prompt_mode=prefix`) without a chat template.  Qwen3 uses the standard
  full-source chat-template prompt.  This is recorded in each candidate
  manifest; no hidden tests or target outputs are sent to any model.
* The first six MBJP values are existing 10-candidate no-I/O control rows and
  are shown for context; MiMo additionally has a new one-candidate MBJP pilot
  marked with `†`.

## Pilot results

`HE`, `GFG`, and `SuFu` are one-candidate pass@1 counts.  `MBJP` is the
existing no-I/O ten-candidate row and therefore shows pass@1 / pass@10.

| model | size | MBJP (existing) | HumanEval-Java v15 pilot | GFG-v13 pilot | SuFu-original pilot |
|---|---:|---:|---:|---:|---:|
| CodeGemma-2B PT | 2B | 29/67 / 48/67 | 5/16 | 40/103 | 0/58 |
| Gemma-2-2B Base | 2B | 23/67 / 43/67 | 3/16 | 27/103 | 0/58 |
| StarCoder2-3B Base | 3B | 21/67 / 50/67 | 5/16 | 39/103 | 0/58 |
| SmolLM3-3B Base | 3B | 28/67 / 42/67 | 6/16 | 33/103 | 0/58 |
| Granite-3.3-2B Base | 2B | 24/67 / 41/67 | 6/16 | 26/103 | 0/58 |
| Qwen3-4B Base | 4B | 34/67 / 60/67* | 8/16 | 25/103 | 0/58 |
| MiMo-7B Base | 7B | 34/67† | 3/16 | 38/103 | 0/58 |

The Qwen3 MBJP row is from the earlier Qwen-inclusive full-source artifact
(marked `*`); it is retained as context and should not be pooled with the
prefix/no-I/O rows without a protocol note.  The MiMo MBJP value (†) is a
one-candidate pilot, whereas the other MBJP values are frozen ten-candidate
rows; it is therefore shown for model selection and is not a pass@10 result.
MiMo is now scored from a valid
ModelScope-LFS re-download.  The first HF transfer had correct file lengths but
zero-valued transformer layers; those files are preserved with
`.hf_corrupt_20260827`/`.invalid_ms*` suffixes and are not scored.  During
validation we also found that MiMo Base continued the chat transcript after
emitting a Java class.  The runner now strips role markers only after a closed
class and can stop at the first balanced class; the reported MiMo Java rows
use this corrected path (`valid3`).  MiMo's SuFu row uses the completed prefix
run (`pilot_mimo_sufu_prefix_zero_valid`) and has no missing or timed-out
candidates.

## Reproducibility

Generation uses `baselines/java_baselines/run_decoder_only_zero_few_shot.py`
and `run_decoder_only_sufu.py`; Java scoring uses `score_java_no_write.py` and
SuFu scoring uses `score_sufu_no_write.py`.  Candidate trees and trajectory
files are under the corresponding `Utils/output/<task>_test_ans/` directories
with `pilot_*_20260827` tags.  Full pass@10 should be run only after selecting
the model(s) from this pilot; it should use the same prompts, seeds, and
sanitized inputs.
