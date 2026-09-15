# ProofT5 documentation index

Start with the following maintained documents:

- `MAJOR_REVISION_FINAL_PACKAGE_20260824.md`: authoritative frozen Java
  datasets, five retained checkpoints, six-row result table, interpretation,
  limitations, and artifact locations.
- `../artifacts/major_revision_20260824/MANIFEST.json`: machine-readable hashes
  and exact paths for the frozen datasets, checkpoints, scores, and candidate
  outputs.
- `experiments/BASELINE_STRENGTHENING_PROTOCOL_20260909.md`: holdout-selected
  retraining protocol behind the HumanEval-Java and TransCoder-GFG baselines.
- `experiments/JAVA_JOINT23_FROZEN_EVALUATION_PROTOCOL_20260823.md`: frozen
  protocol of the 2B Java (HumanEval/GFG) TyFlow row.
- `experiments/JAVA_FROZEN_T5GEMMA_STRONG_BASELINES_20260824.md` and
  `experiments/T5GEMMA2_COMPARISON_CHECKPOINTS.md`: baseline checkpoint
  provenance for the Java and SuFu 2B rows.
- `experiments/CLEAN_JAVA_REPRODUCTION_RESULTS_20260811.md`: provenance of the
  leak-clean T5Gemma2-2B checkpoint used by the RQ3 reruns.
- `MODEL_TRAINING_INVENTORY.md`: canonical model lineage and training
  routes, including original MBJP and SuFu experiments.
- `PROJECT_STRUCTURE.md`: maintained repository layout and runtime paths.
- `CHECKPOINT_CLEANUP_MANIFEST_20260823.md`: exact destructive-cleanup record.
- `PROJECT_CLEANUP_AUDIT_20260823.md`: cleanup policy and remaining risk tiers.

The files under `../artifacts/` are the stable paper-facing evidence package
(score JSONs, frozen per-task arrays, protocol launchers, and logs).
Superseded experiment documents and one-off launch scripts were removed in the
2026-09-15 cleanup pass; they remain retrievable from git history.
