# Project cleanup audit (2026-08-23)

## Safety policy

The repository contains a dirty worktree and a large untracked experiment
archive.  Untracked does not mean disposable.  Cleanup must preserve all
paper-facing datasets, selected checkpoints, candidate outputs, score JSONs,
training metrics, manifests, and audit reports until a reference-aware archive
has been made.

The first cleanup pass is intentionally conservative and recoverable.  It may
move obvious root-level compiler/cache debris into a dated quarantine, but it
must not delete models, data, outputs, `tmp` ledgers, source changes, or result
documents.

## Current structural inventory

| area | observed scale | classification |
|---|---:|---|
| `Utils/models` | 479 first-level model directories | mixed selected, parent, intermediate, rejected; audit before deletion |
| `t5_llm/models` | 106 first-level model directories | mixed base, epoch series, selected; audit before deletion |
| `Utils/output` | 263 first-level output task directories | many are cited functional ledgers; audit before deletion |
| `Utils/data` | authoritative and exploratory datasets | preserve |
| `tmp` | score JSONs, metrics, logs, runtime state, diagnostics | mixed evidence and scratch; classify by references |
| `coq_model/coq_code/mbjp` | generated problem directories observed through id 1083 | likely large scratch tree, but verify source/runtime dependencies before deletion |
| repository root | 91 `javac.*.args` files (26,696 bytes) | deleted after quarantine review |
| caches | root and 15 nested `__pycache__` directories, root `.pytest_cache` | deleted after quarantine review |

The largest directly observed `tmp` files include `tmp/sufu.log` (~66.5 MB),
old pretraining metrics, July beam-state dumps, and current formal metrics.
Size alone is not sufficient for deletion: metrics and beam-state dumps can be
the only provenance for historical claims.

The high-value cleanup cluster was subsequently audited and removed: 220 July
SuFu/CoqView diagnostic sweep directories containing 307 checkpoints occupied
2,385,888,956,416 bytes.  None was referenced by the current canonical
experiment documents.  Exact paths and gates are recorded in
`docs/CHECKPOINT_CLEANUP_MANIFEST_20260823.md`.  Canonical original-SuFu
checkpoints were outside the deletion prefix and remain preserved.

The same reference-gated pass then removed 76 superseded Java v4-v12 model
directories (1,470,411,714,560 bytes) and 22 abandoned SuFu expansion model
directories (794,486,685,696 bytes).  Total checkpoint storage removed in this
cleanup was 4,650,787,356,672 bytes.  The SuFu benchmark checkpoints were
preserved; only the abandoned extension branch was removed.

On 2026-08-24 the final Java package was frozen under
`artifacts/major_revision_20260824/`. A second reference-gated pass then
removed 17 rejected 2026-08-23 joint checkpoint directories plus one duplicate
snapshot, reclaiming another 286,469,857,154 bytes. It also removed merged
HumanEval/GFG shard outputs, obsolete probes, 133 joint temporary files, four
one-off orchestration scripts, and two superseded v14 support documents. The
selected joint `last_model.ckpt`, both final merged/fail-closed output trees,
the problem-44 log, and all paths in the frozen manifest remain present.

The final consolidation expanded this reference-gated cleanup to all
superseded Java model versions and clearly diagnostic original-paper branches.
The full 2026-08-24 checkpoint reclaim is 4,392,878,989,413 bytes. Generated
Java data now consists of 11 retained tasks instead of 249, and `tmp` was
reduced from approximately 25 GiB to 95 MiB. Base models, formal original
MBJP/SuFu checkpoints, final Java/SuFu CoqView checkpoints, source changes,
tests, raw selected data, and every frozen-manifest path remain.

The rebuildable Syncode mask cache was also removed (`cache` fell from 1.7
GiB to 256 KiB); the Java parser cache and vendored baseline sources remain.

## Preserve list: paper-facing minimum

The following must not be removed:

1. Every path cited by `artifacts/major_revision_20260824/MANIFEST.json`.
2. The frozen score and audit copies in `artifacts/major_revision_20260824/`.
3. HumanEval-v15 and GFG-v13 source task directories and split manifests.
4. The five final checkpoints and six complete/fail-closed candidate outputs.
5. Source files, tests, builders, scoring scripts, and dirty worktree changes.
6. Base models and direct parent checkpoints needed to load selected models.

## Cleanup tiers

### Tier A: safe and recoverable now

- Completed: reviewed and deleted 91 root `javac.*.args` files, root
  `__pycache__`, root `.pytest_cache`, and 15 nested Python cache directories.
- Completed: removed six empty model/cache directories.
- Do not follow symlinks and do not touch GPU processes.

### Tier B: safe after a generated reference manifest

- Completed `tmp/runtime_state` directories with no active process.
- Coq-generated `.v/.vo/.glob/.aux` candidate scratch files after confirming
  that all candidate text outputs and score JSONs are final.
- Empty evaluation directories and failed startup directories containing no
  checkpoint or score artifact.

### Tier C: explicit user decision required

- Remaining rejected/intermediate checkpoints and redundant epoch snapshots
  outside the audited July SuFu/CoqView prefix.
- Historical candidate output directories already summarized by score JSON.
- Old July/August beam-state dumps and large logs.
- Superseded v1-v14 datasets and their copied tokenizer/rule artifacts.
- Further removal of historical documents already condensed into the master
  ledger, when they contain evidence not preserved elsewhere.

## Recommended target structure

```text
docs/
  JAVA_BENCHMARK_EXPERIMENT_MASTER_20260823.md
  PROJECT_CLEANUP_AUDIT_20260823.md
  experiments/          # only after reference rewrite
Utils/
  data/                 # authoritative data tasks
  models/               # ProofT5/Coq/CoqView checkpoints
  output/               # generated candidates and score-bound outputs
t5_llm/
  data/                 # ordinary-model JSON datasets
  models/               # ordinary/base checkpoints
scripts/                # builders, audits, launchers, summarizers
tests/                  # regression tests
tmp/
  runtime_state/
  ...                   # experiment evidence pending classification
```

## Required next cleanup audit

Before deleting large artifacts, generate a machine-readable manifest with:

- absolute/relative path, apparent size, modification time, and content hash;
- whether the path is referenced by Markdown, JSON, shell, or Python files;
- checkpoint lineage role: base, parent, selected, intermediate, rejected;
- output role: complete score-bound, partial, failed, or runtime scratch;
- proposed action: keep, archive, quarantine, or delete.

Only exact paths marked `delete` in a reviewed manifest should be removed.
