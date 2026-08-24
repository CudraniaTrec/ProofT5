# Java expansion MBJP-native v13 experiment (2026-08-19)

## Scope

v13 is a prompt-protocol repair of the already frozen v10 MBJP-matched
HumanEval-Java and TransCoder-GFG splits.  It does **not** select a new test
split after observing model results.  The train/validation/test sizes remain
HumanEval 129/0/33 and GFG 414/0/103.

The parent datasets already provide an 80/20 split stratified by return type
and complex signature, and every test row has exactly three visible cases that
are also the complete executable test fixture.  v13 preserves those IDs,
canonical Java solutions, executable tests, IR/proof targets, tokenizer, and
rule artifacts byte-for-byte.  Only the prompt and its encoded `nl` field
change.

## Prompt repair

The ordinary T5Gemma2 target is the complete prompt plus canonical solution.
The v10 HumanEval prompts therefore imposed a substantial non-semantic burden:
examples used class-qualified Java assertions such as
`Objects.equals(Class.method(args), value)`, while MBJP uses a direct method
call followed by its return value.  v13:

- rewrites all recognizable visible examples as direct `method(args)` calls;
- writes the direct returned value on the following line;
- removes class qualification and the extra `Java contract` prose while
  retaining the exact `public static` Java signature;
- collapses multiline examples without changing quoted newlines (a literal
  newline becomes the Java `\n` escape);
- leaves rows without a bounded visible fixture unchanged apart from contract
  removal; no malformed fixture is invented.

The authoritative datasets are:

- `java_humaneval_mbjp_native_prompt_split80_20_t5gemma2_20260819_v13`
- `java_transcoder_gfg_mbjp_native_prompt_split80_20_t5gemma2_20260819_v13`

Their `mbjp_native_prompt_manifest.json` files report zero remaining contract
blocks or class-qualified visible calls, three direct-return examples for
every test row, and successful gold compilation/execution for all 162 and 517
programs.  Independent reconstruction verifies unchanged split membership,
canonical solution, test, and proof targets.  Maximum encoded prompt lengths
are 415 and 464; maximum ordinary-model full targets are 949 and 970 tokens,
both below the fixed 1024-token bound.

An initial local build incorrectly collapsed one newline inside a HumanEval
string literal to a space.  It was rejected before v13 training and moved to
`tmp/rejected_v13_newline_collapse_20260819/data`; the rebuilt authoritative
dataset preserves `removeVowels("abcdef\nghijklm")`.

## Training curricula

The shared audited curriculum is
`java_mbjp_humaneval_transcoder_mbjp_native_prompt1623_v13_complex2_cov4_t5gemma2_20260819`.
It retains every unique train row, has no validation/test rows, and uses the
frozen IR-quartile, complex-signature, and protected-description-neighbour
replay policy.  It does not use test model outputs, checkpoint scores, gold
Java, or gold IR for split or replay selection.

Benchmark-specific routes are:

- HumanEval: `java_mbjp_humaneval_mbjp_native_prompt1082_v13_pair_t5gemma2_20260819`
  with 541 MBJP and 541 HumanEval occurrences;
- GFG: `java_mbjp_transcoder_gfg_mbjp_native_prompt2164_v13_exposure3_pair_t5gemma2_20260819`
  with 541 MBJP and 1,623 GFG occurrences.  The three frozen GFG copies raise
  exposure per unique GFG problem from about 1.31 to 3.92, close to
  HumanEval's 4.19.

An additional expansion-only specialization task is
`java_humaneval_transcoder_mbjp_native_prompt828_v13_expansiononly_complex2_t5gemma2_20260819`.
It retains all 129 HumanEval and 414 GFG unique training rows, replays each
source to 414 occurrences, and gives complex signatures weight 2 during the
HumanEval replay.  It contains 828 train, zero validation, and zero test rows.
Its materialization uses neither test descriptions nor test model outputs,
gold Java, or gold IR; train/test semantic and task-ID overlap are both zero.
This task is reserved for a gated specialization stage after the joint model
passes fixed training probes, so the effect of removing MBJP replay can be
reported separately instead of silently changing the main curriculum.

CoqView counterparts, full benchmark tasks, and fixed eight-row training
probes were built by exact rule/proof/token trace reuse; only the new `nl` is
retained from v13.  All rows reused an existing trace and all six tasks pass
the fail-closed bounds audit with `unexpected_truncation_risk=false`.

## Results

| route | HumanEval train | HumanEval test | GFG train | GFG test | status |
|---|---:|---:|---:|---:|---|
| ordinary T5Gemma2 (complete-file target) | 129/129, 129/129 | 2/33, 8/33 | 408/414, 411/414 | 14/103, 28/103 | selected baseline |
| ordinary T5Gemma2 (solution-only ablation) | fixed probe: 8/8, 8/8 | 1/33, 1/33 | fixed probe: 8/8, 8/8 | 5/103, 8/103 | rejected on both held-out sets |
| Coq | pending | pending | pending | pending | HumanEval fixed-probe evaluation and GFG training running |
| CoqView | pending | pending | pending | pending | HumanEval training running |

Each cell reports pass@1, pass@10.  The HumanEval ordinary checkpoint is
`t5gemma2-2b_java_mbjp_humaneval_mbjp_native_prompt1082_v13_pair_frombase_stage2_selected_20260819`.
It was selected at stage-2 epoch 9 using training loss only (0.0017472).
The executable test result is 6.06% pass@1 and 24.24% pass@10, with 104 of
330 candidates failing compilation (31.52%).  This is not a large improvement
over the v12 clean-base route (3/33 and 7/33), so v13 must not be described as
a successful repair of HumanEval generalization.

The failure is concentrated in structured types, not in a globally harder
test split.  The test split has fewer complex signatures than train (48.5%
versus 59.7%) and shorter median prompts and solutions.  Nevertheless only 2
of 16 complex-signature test problems are solved in ten beams, all seven
`List<Integer>` problems fail, and all ten candidates for the one
`Optional<String>` problem fail compilation.  Simple `int` problems account
for four of the eight pass@10 successes.  The MBJP-native prompt repair makes
the train distribution fully learnable: the complete 129-row train split
reaches 129/129 at both pass@1 and pass@10, not merely 8/8 on the fixed probe.
Its 1,290 candidates have a 13.26% compilation-error rate and 70.70% mean
candidate success rate.  The resulting 100%/100% train versus 6.06%/24.24%
test gap rules out a missing-training-data or underfit-checkpoint explanation,
but the repair does not by itself provide cross-problem coverage for
structured signatures.

### Ordinary-decoder target audit

The ordinary baseline is trained to regenerate the complete input prompt
before emitting the method implementation, whereas the Coq and CoqView routes
cut the audited signature prefix and predict only its suffix.  Candidate-level
inspection shows that complete-file copying is a real decoding burden but is
not the sole explanation for the functional failures.  On the HumanEval test
set, 261/330 candidates reproduce the input prompt byte-for-byte and 329/330
retain the exact return type, method name, and parameters.  Of the 104
compilation failures, 103 still have the correct signature; most errors are
therefore in the generated method body rather than the stored prompt or loader.

A controlled joint-curriculum ablation is running with an ordinary-model
`solution` target: the model predicts only `canonical_solution`, and evaluation
concatenates that output with the exact audited row prompt before compilation.
No test content, expected value, split member, or gold solution enters
checkpoint selection.  For HumanEval, this reduces median decoder target
length from 328 to 113 tokens on train and from 267 to 77 on test; for GFG the
corresponding reductions are 348 to 114 and 331 to 100.  The run uses the
1,623-row joint MBJP/HumanEval/GFG training curriculum, empty validation, and
will be reported separately because it changes the ordinary decoding target
relative to the complete-file baseline.

The joint solution-only route completed seven 5e-5 passes followed by ten
5e-6 passes.  Training-loss selection chose the final points at 0.07177 and
0.02776 respectively.  It nevertheless fails the frozen HumanEval training
gate: only 3/8 functions pass at rank 1 and 4/8 within ten beams, with 60/80
candidate compilation failures.  The candidates have the exact audited
prompt spliced in but often contain an unrelated, type-invalid method body.
It is therefore rejected before held-out scoring.  A separate 828-row
expansion-only specialization was then run to test whether balanced repeat
exposure could repair this rare-row underfitting.  Ten 5e-5 passes reduced its
training loss monotonically from 0.14986 to 0.00376, and the selected final
checkpoint passes both frozen HumanEval and GFG training probes at 8/8 for
pass@1 and pass@10.  On the untouched HumanEval test split, however, it reaches
only 1/33 at both pass@1 and pass@10; 220/330 candidates fail compilation.
Generated bodies often implement an unrelated training function while the
exact stored prompt and signature are spliced in.  Removing prompt copying
therefore makes the training rows learnable but worsens held-out
generalization.  This ablation is rejected and is not a reported replacement
for the complete-file ordinary baseline.

The selected GFG ordinary checkpoint is
`t5gemma2-2b_java_mbjp_transcoder_gfg_mbjp_native_prompt2164_v13_exposure3_pair_frombase_stage2_selected_20260819`.
Its stage-2 epoch-9 training loss is 0.0010663.  The fixed training probe is
8/8 at both pass@1 and pass@10; the frozen 103-row test split reaches 14/103
(13.59%) and 28/103 (27.18%), with 258 of 1,030 candidates failing compilation
(25.05%).  This is better than HumanEval on pass@1, but remains a large
train-to-test generalization gap.  The complete 414-row train evaluation is
408/414 at pass@1 and 411/414 at pass@10, with all 4,140 candidates present.
The corresponding solution-only specialization is only 5/103 and 8/103 on
the same held-out split, with 559/1,030 candidates failing compilation.  It is
therefore rejected for GFG as well as HumanEval.

The first HumanEval Coq stage completed ten passes at 5e-6 and reduced its
global active-target-token-weighted loss from 1.4767 to 0.07870.  A subsequent
1e-6 continuation restarted at 0.1661 rather than continuing from 0.07870,
despite exact source-row coverage.  That continuation is rejected; its model
must not replace the first-stage selected checkpoint.  The load path emits an
expanded-embedding resize warning and requires a separate continuation audit.

The GFG Coq route completed ten one-GPU passes at 5e-6.  Its exact runtime
multiset contains all 2,164 materialized rows with no missing, extra, or
padding rows.  Global active-target-token-weighted loss decreased monotonically
from 0.36533 to 0.01521, so the complete pass-10 checkpoint was selected using
training loss only as
`java_mbjp_transcoder_gfg_mbjp_native_prompt2164_v13_exposure3_pair_coq_selected_20260819`.
Its fixed eight-row training-function evaluation is running; no held-out GFG
score was used for selection.

The original HumanEval Coq checkpoint completes its fixed probe at only 1/8
pass@1 and 2/8 pass@10.  The constrained decoder emits 60 of the requested 80
candidates; ten fail compilation and five time out.  It is therefore rejected
before held-out scoring.  A 20-pass expansion-only Coq repair completed from that
checkpoint on the 828-row complex-signature curriculum.  Its runtime multiset
matches all 828 source occurrences exactly, with no padding, and loss decreases
monotonically from 0.41786 to 0.02078.  The complete pass-20 checkpoint is
selected as
`java_humaneval_transcoder_mbjp_native_prompt828_v13_expansiononly_complex2_coq_repair_selected_20260819`;
its HumanEval fixed training probe is running.

Checkpoint selection uses complete-pass training loss and a frozen
training-only probe.  Validation remains empty.  Full training-set and frozen
test-set execution are both required before a route can be reported as
successful.
