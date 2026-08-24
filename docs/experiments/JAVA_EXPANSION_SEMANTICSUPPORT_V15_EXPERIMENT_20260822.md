# Java HumanEval semantic-support v15 experiment (2026-08-22)

> **2026-08-23 lineage addendum.** The ordinary checkpoint described here
> starts from the base model, but the later joint Coq checkpoint evaluated on
> this split descends from the clean-673 Coq checkpoint. Five v15 test rows
> were seen by that Coq ancestor. Consequently the later joint Coq 16-row
> result is ancestor-mixed; the matched lineage-unseen comparison is ordinary
> 1/11 and 3/11 versus Coq 4/11 and 5/11. See
> `docs/audits/JAVA_HUMANEVAL_V15_ANCESTOR_OVERLAP_AUDIT_20260823.json`.

## Protocol

v15 is an explicitly exploratory HumanEval-Java interpolation experiment.  It
uses the audited MBJP-native 162-row corpus with a fixed 146/0/16 split.  The
split uses description TF-IDF and lexical-free gold-IR shape, but no model
output, checkpoint, execution outcome, or test result.  Its independent audit
is `docs/audits/JAVA_EXPANSION_SEMANTICSUPPORT_V15_AUDIT_20260822.json` and reports zero
failures: every gold program compiles and passes its executable tests, every
row is aligned across plain/proof formats, and validation is empty.

Checkpoint selection uses complete-pass active-target-token-weighted training
loss followed by a frozen eight-row training-only functional gate.  Held-out
results are never used for checkpoint selection.  Coq candidates must reach
8/8 at both pass@1 and pass@10 before the held-out split can be opened.

## Ordinary T5Gemma2

The ordinary route starts from `Utils/models/t5gemma-2-1b-1b`.  It trains on a
balanced 1,082-occurrence MBJP/HumanEval train-only materialization.  Seven
passes at 5e-5 select zero-based epoch 5 at loss 0.0199527411; the seventh pass
rebounds to 0.0771984557 and is rejected.  Ten subsequent passes at 5e-6 select
zero-based epoch 9 at loss 0.001165861615.  No validation or test row is read.

The selected checkpoint is
`t5gemma2-2b_java_mbjp_humaneval_semanticsupport1082_v15_plain_selected_20260822`,
SHA-256 `991e7d4285c274e68870411308f10dd3ca0fb10fc549f781069774daa72e431d`.
It passes the frozen training gate at 8/8 pass@1 and 8/8 pass@10.  Its once-opened
16-row strict test result is 2/16 (12.50%) pass@1 and 4/16 (25.00%) pass@10,
with 47/160 compilation failures, one timeout, and no missing candidates.

## Coq

The Coq route starts from the frozen MBJP Coq pass-30 parent and trains for ten
complete 5e-6 passes on the same 1,082-occurrence train-only materialization.
Its token-weighted loss decreases monotonically from 0.224670909 to
0.0144960261.  The selected checkpoint is
`java_mbjp_humaneval_semanticsupport1082_v15_pair_coq_selected_20260822`,
SHA-256 `a103002bd158d45b9b949729a47da515fc48502bfeb293c3276204cb58efa0a8`.

The checkpoint fails the frozen training gate: among the first seven completed
probe rows it obtains 5/7 at pass@1 and 5/7 at pass@10; IR-length probe rows 5
and 6 fail.  Because 8/8 is no longer possible, the eighth long proof search is
stopped and the held-out Coq test remains unopened.  This is evidence of a
training/long-sequence limitation, not a held-out selection result.

## Seen/held-out mixing diagnostic

The user-authorized 66-row diagnostic combines 33 rows labelled seen under the
old v13 split with 33 rows labelled held out under that old split.  It is not a
benchmark result and does not alter checkpoint selection.  Under the new v15
training membership, 31/33 old-seen rows and 23/33 old-heldout rows were
actually trained.  The ordinary checkpoint obtains:

| diagnostic subgroup | v15-trained rows | pass@1 | pass@10 |
|---|---:|---:|---:|
| old v13 seen | 31/33 | 31/33 (93.94%) | 32/33 (96.97%) |
| old v13 heldout | 23/33 | 25/33 (75.76%) | 26/33 (78.79%) |
| combined diagnostic | 54/66 | 56/66 (84.85%) | 58/66 (87.88%) |

These high diagnostic numbers show that the ordinary route can memorize the
included functions.  They must not be presented as held-out generalization;
the authoritative v15 held-out result remains 2/16 and 4/16.

## Current conclusion

The ordinary training implementation and data loader are operational: the
training-only gate is 8/8 and the mixed diagnostic strongly separates trained
from strict held-out behavior.  Semantic-support repartition raises strict
pass@10 relative to the old 4/33 HumanEval result but does not raise pass@1.
The remaining failure is therefore dominated by cross-problem generalization
and long complete-file generation, while the Coq route additionally fails to
fit the two longest completed probe rows and is not eligible for testing.

## TransCoder-GFG Coq repair

The v13 selected GFG Coq parent was repaired without opening the 103-row test.
The first repair retains all 414 training functions and materializes 1,242
train-only occurrences using IR-length-quartile and complex-signature weights.
Five 1e-6 passes reduce token-weighted loss monotonically from 0.0173903457 to
0.0155676632.  Its selected checkpoint is
`java_transcoder_gfg_v13_mbjp_native_lengthrepair3_complex2_coq_selected_20260822`,
SHA-256 `ca22f474e4525b73b04b360cf8767b6885d0277f8892f1f8b5538c8543fdacd5`.

Strict proof-constrained evaluation passes fixed probe indices 0--5 and 7 at
both pass@1 and pass@10.  In particular, index 7 was a failure for the parent
and is repaired to 1/1 at both metrics.  Index 6 is a 504-token IR program.  A
strict prefix-checked search remains unfinished after reaching token 329; an
independent final-only diagnostic emits only 2/10 complete candidates and
scores 0/1 at both metrics.

A second train-only repair materializes 2,484 occurrences (six copies with a
3x complex-signature weight) and runs five additional 5e-7 passes.  Loss again
decreases monotonically from 0.0153167939 to 0.0150149419.  The selected
checkpoint is
`java_transcoder_gfg_v13_mbjp_native_lengthrepair6_complex3_coq_selected_20260822`,
SHA-256 `57109f81642c74f568758a469051df8fbba710298167e7236caf1e7480d501c6`.
Its index-6 final-only diagnostic is unchanged: 2/10 candidates and 0/1 at both
metrics.  Further replay therefore improves training loss but does not repair
the longest training program.  Neither GFG candidate qualifies for held-out
access, and the 103-row test remains unopened.
