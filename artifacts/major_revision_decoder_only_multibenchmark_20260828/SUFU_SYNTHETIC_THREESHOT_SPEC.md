# SuFu synthetic three-shot prompt set

This file documents the corrected SuFu few-shot condition.  The prompt set is
`inputs/sufu_synthetic_minimal_three.json` and is fixed for every model.  It
contains exactly three small, complete SuFu source programs:

* return the first list element, or zero;
* count occurrences of the integer two;
* sum elements below five.

The programs are independent of the 58-task SuFu test split.  They contain no
tests, interpreter outputs, target suffixes, or benchmark task identifiers.
Each source was checked with `SuFu.sufu_model.parser` and
`visit(...).type_check(TypeCtx())`; all three parse and type-check
successfully.  The input file fingerprint used for manifests is
`331d8cefb9abdbb4231f77c4f8ea1af97694ef9cc043edc3b2d12531d6889090`.

For the formal comparison, run `run_decoder_only_sufu.py` with
`--few_shot_k 3 --few_shot_dataset` pointing to this file and keep the same
`prompt_mode`, candidate count, seed, and scorer as the zero-shot control.
Tests and expected outputs remain confined to the scorer; they are never
serialized into model messages.
