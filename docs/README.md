# ProofT5 documentation index

Start with the following maintained documents:

- `MAJOR_REVISION_FINAL_PACKAGE_20260824.md`: authoritative frozen Java
  datasets, five retained checkpoints, six-row result table, interpretation,
  limitations, and artifact locations.
- `../artifacts/major_revision_20260824/MANIFEST.json`: machine-readable hashes
  and exact paths for the frozen datasets, checkpoints, scores, and candidate
  outputs.
- `SESSION_HANDOFF_MAJOR_REVISION_20260823.md`: broader zero-context
  project/paper/review handoff. Its experiment status is historical when it
  conflicts with the 2026-08-24 frozen package.
- `JAVA_BENCHMARK_EXPERIMENT_MASTER_20260823.md`: compact pointer and current
  six-row table.
- `../MODEL_TRAINING_INVENTORY.md`: canonical model lineage and training
  routes, including original MBJP and SuFu experiments.
- `../PROJECT_STRUCTURE.md`: maintained repository layout and runtime paths.
- `CHECKPOINT_CLEANUP_MANIFEST_20260823.md`: exact destructive-cleanup record.
- `PROJECT_CLEANUP_AUDIT_20260823.md`: cleanup policy and remaining risk tiers.

`experiments/` and `audits/` contain supporting historical detail. The copied
files under `../artifacts/major_revision_20260824/` are the stable paper-facing
evidence package. CoqView and rejected 2026-08-23 checkpoint branches are not
part of the final Java experiment queue.
