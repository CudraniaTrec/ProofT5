# SuFu realistic train-like three-shot protocol

The first synthetic replacement set demonstrated the right SuFu operators,
but its tasks were still toy reductions.  For the paper-facing follow-up we
use three disjoint training-split programs from the sanitized file
`inputs/sufu_few_shot_train_noio_notest.json`.  They are substantially closer
to the benchmark distribution and contain no `tests`, interpreter `output`,
or test-split rows:

* `incre-tests-synduce-constraints-sortedlist-parallel_max2` — a nested
  `CList`/partition program with sortedness checks and compressed alignment;
* `incre-tests-synduce-list-last` — recursive flattening of a nested list and
  extraction of the last element;
* `incre-tests-synduce-ptree-maxsum` — a tree-structured recursive maximum-sum
  computation with multiple helper definitions.

The examples are selected by task ID so that the exact three sources remain
auditable without copying or rewriting the sanitized training file.  The
paper-facing SuFu capability baseline uses high-information full-source
prompting: the complete target description and public prefix are shown, rich
demonstrations are given, and the model is instructed to return one complete
program.  The source-prefix/no-chat protocol is retained only as a restricted
format control.  The runner no longer duplicates each demonstration's prefix.

```bash
--few_shot_dataset artifacts/major_revision_decoder_only_multibenchmark_20260828/inputs/sufu_few_shot_train_noio_notest.json \
--few_shot_ids incre-tests-synduce-constraints-sortedlist-parallel_max2,incre-tests-synduce-list-last,incre-tests-synduce-ptree-maxsum \
--few_shot_k 3 --prompt_mode full_source --guidance_profile high_information
```

The earlier minimal and hand-written synthetic sets remain in the artifact as
diagnostics.  They must not be mixed with this train-like F3 row.  Under the
capability-oriented full-source protocol, MiMo-7B reaches 4/10 on the pilot
and 8/58 on the full test; the matching score files are listed in
`SUFU_REALISTIC_TRAINLIKE_RESULTS.md`.
