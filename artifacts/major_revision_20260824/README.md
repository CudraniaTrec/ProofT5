# Major-revision frozen artifact package (2026-08-24)

This directory is the stable entry point for the Java expansion experiments.
The authoritative interpretation, datasets, checkpoints, output directories,
and limitations are recorded in `docs/MAJOR_REVISION_FINAL_PACKAGE_20260824.md`.

`scores/` contains immutable copies of the final functional score JSON files.
The original candidate programs remain under the paths recorded in
`MANIFEST.json`; they are not duplicated here because the output directories
contain the complete ordered candidate set.

HumanEval-Java v15 is a fixed 146/0/16 split with no overlap between its
test tasks and the checkpoint's training rows.

The TransCoder-GFG ProofT5 score is fail-closed over all 103 problems. Problem
44 produced no completed output after more than two hours of isolated decoding,
so all ten candidates for that problem are counted as failures.
