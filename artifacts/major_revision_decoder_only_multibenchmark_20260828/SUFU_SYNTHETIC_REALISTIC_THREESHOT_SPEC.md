# SuFu hand-written synthetic three-shot diagnostic

The earlier `sufu_synthetic_minimal_three.json` was intentionally tiny, but it
was too far from real SuFu programs: it did not demonstrate `Compress`,
`align`, `label`, `unlabel`, the `single_pass` interface, or nested inductive
data.  This hand-written set is still independent of the 58-task test split,
but is retained as a diagnostic rather than the paper-facing F3 condition.
The paper-facing condition now uses the more complex train-like examples in
`SUFU_REALISTIC_TRAINLIKE_THREESHOT_SPEC.md`.

It contains exactly three complete, parser- and type-check validated programs:

1. `list-sum-single-pass`: a compressed single-pass list traversal followed by
   a recursive sum;
2. `double-sum-single-pass`: a recursive list map, recursive sum, and the same
   compressed single-pass interface;
3. `clist-flatten-sum`: a nested `CList`, recursive list concatenation,
   compressed flattening, and a final sum.

The examples contain no tests, interpreter outputs, target suffixes, or IDs
from the 58-task test split.  Their file fingerprint is computed from the
prompt/code fields and recorded in each generation manifest.  Use this file
only for a controlled hand-written diagnostic; the revised paper-facing F3
condition is the train-like protocol in
`SUFU_REALISTIC_TRAINLIKE_THREESHOT_SPEC.md`:

```bash
--few_shot_dataset artifacts/major_revision_decoder_only_multibenchmark_20260828/inputs/sufu_synthetic_realistic_three.json \
--few_shot_k 3 --prompt_mode full_source
```

The original minimal set remains in the artifact as a reproducibility
diagnostic; neither it nor this hand-written set should be mixed with the
train-like paper-facing SuFu F3 row.
