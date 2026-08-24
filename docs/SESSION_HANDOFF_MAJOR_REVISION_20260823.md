# TyFlow / ProofT5 Major Revision session handoff

Last verified: 2026-08-24 (historical handoff retained)

Repository root: `/data2/x/hzc/prooft5`

Handoff status: **historical context, no longer the sole experiment ledger**.
Start with `docs/MAJOR_REVISION_FINAL_PACKAGE_20260824.md` and
`artifacts/major_revision_20260824/MANIFEST.json`. Those files freeze the final
six-row Java table, datasets, five retained checkpoints, candidate outputs,
limitations, and hashes. Any live-process, pending-queue, checkpoint, or score
statement below is superseded when it conflicts with the frozen package.

Git state at handoff: branch `main`, commit `695ac6e`, dirty working tree. Do
not reset, clean, or discard local changes. The paper tree itself has no Git
diff, but the experiment/code tree contains required uncommitted work.

## 0. Latest Major Revision progress (final repository freeze, 2026-08-24)

This section is the current progress report and supersedes every live-process,
pending-queue, provisional-score, and cleanup statement later in this
historical handoff. The paper-facing experiment authority is
`docs/MAJOR_REVISION_FINAL_PACKAGE_20260824.md`; exact paths and hashes are in
`artifacts/major_revision_20260824/MANIFEST.json`.

### 0.1 Frozen result status

The requested main table now contains ordinary T5Gemma2 and ProofT5 only;
CoqView was removed because its evaluation cost is not justified for this
revision. Validation is empty in all three settings. The frozen test results
are:

| benchmark | ordinary pass@1 / pass@10 | ProofT5 pass@1 / pass@10 |
|---|---:|---:|
| MBJP, 67 test tasks | 9/67 (13.43%) / 22/67 (32.84%) | **17/67 (25.37%) / 29/67 (43.28%)** |
| HumanEval-Java v15, 16 test tasks | 2/16 (12.50%) / 4/16 (25.00%) | **8/16 (50.00%) / 9/16 (56.25%)** |
| TransCoder-GFG v13, 103 test tasks | 14/103 (13.59%) / 28/103 (27.18%) | **31/103 (30.10%) / 48/103 (46.60%)** |

HumanEval's full 16-task row is an **ancestor-mixed exploratory result**:
five test tasks occur in the ProofT5 checkpoint's ancestor training lineage.
On the matched 11-task lineage-unseen subset, ordinary is 1/11 and 3/11,
versus ProofT5 4/11 and 5/11. GFG is a fixed 80/20, MBJP-aligned
interpolation split, not arbitrary raw-program OOD generalization. GFG task 44
did not terminate; it is counted as ten failures with the full 103-task
denominator. The fail-closed score records this missing task explicitly.

Complete ordinary train-set evaluations are also frozen: MBJP 506/608 and
564/608, HumanEval 145/146 and 145/146, and GFG 408/414 and 411/414. Full
ProofT5 train-set inference was not run and remains labelled “not evaluated”;
small probes were not promoted into those cells.

Five Java checkpoints are retained: one ordinary and one ProofT5 checkpoint
for MBJP, separate ordinary checkpoints for HumanEval and GFG, and one joint
HumanEval/GFG ProofT5 checkpoint. The artifact package retains the eleven
paper-facing score JSONs, split/lineage/training audits, hashes, and pointers
with manifest hashes to the six complete candidate-output trees. The original
formal-language/SuFu model assets remain available but are not part of this
Java cleanup.

### 0.2 Major Revision issue status

| reviewer workstream | latest status | evidence / remaining boundary |
|---|---|---|
| More Java benchmarks | **experiment complete** | Added normalized HumanEval-Java and TransCoder-GFG with fixed splits, tests, semantic/style audits, and full test evaluation; limitations above must remain explicit. |
| Stable gain under the T5Gemma2 route | **experiment complete** | ProofT5 improves pass@1 and pass@10 over the matched ordinary model on all three frozen test settings. |
| Reproducibility and failure-closed evaluation | **implementation complete** | Fixed datasets/checkpoints/outputs are hash-bound; scorers retain missing tasks in the denominator; distributed partition/merge and timeout regressions are tested. |
| Invalid-generation/failure analysis | **partial** | Candidate compile errors fall from 47/160 to 2/154 on HumanEval and from 258/1030 to 28/1020 on GFG. A reviewer-facing taxonomy, representative cases, and paper table/figure are still needed. |
| Confidence/statistical reliability | **partial** | Split and lineage audits are frozen; confidence intervals and paired statistical tests still need manuscript integration, especially given HumanEval's small test set. |
| SynCode, Repilot/Copiloting-style, iterative repair | **infrastructure/smoke complete; benchmark results open** | Reproducible adapters, upstream commit lock, fail-closed prompt alignment, and smoke tests exist under `baselines/java_baselines/`; no full matched benchmark numbers may be claimed yet. |
| Modern decoder-only / larger model baseline | **open** | No complete paper-facing benchmark result has been produced. |
| Scalability, pruning, runtime and cost | **partial/open** | Timeout and invalid-output evidence exists, but matched wall-clock, decoder-step, proof-check, beam-exhaustion, CPU/GPU and token/call measurements remain. |
| Theory and limitations | **open in manuscript** | Bound first-order/higher-order claims, CHC generality, dynamic-language scope, and logical-versus-search completeness. |
| LaTeX tables/plots and point-by-point response | **open** | `tosem/paper/` remains the submitted manuscript; the new results have not yet been integrated into the paper or a Major Revision response letter. |

### 0.3 Repository and verification status

- The final cleanup removed superseded checkpoints and generated scratch
  totaling approximately 4.393 TB. Only checkpoints/data/output trees named
  by the final manifest or required by the retained original experiments were
  kept.
- `third_party/` and `cache/` are reproducible local state and are gitignored.
  Java baseline upstreams are pinned by
  `baselines/java_baselines/UPSTREAM_LOCK.json` and reconstructed with
  `baselines/java_baselines/fetch_upstreams.py`.
- `SuFu/apiKey.json` was removed from the tracked tree while the ignored local
  copy was preserved. Because the credential existed in earlier Git history,
  rotate it at the provider and purge repository history if the hosting policy
  requires complete secret removal.
- The complete regression suite passes 70 tests; `git diff --check` and all
  artifact/checkpoint/candidate-tree hash audits pass.
- The only optional experiment needed to fill every train column is full
  ProofT5 inference on the three frozen training splits. It requires no new
  training or checkpoint selection. The higher-priority remaining work is the
  reviewer-requested baseline/cost analysis and manuscript integration.

## 1. Purpose of this document

This is the single starting document for a new Codex session with no prior
conversation context. It records:

- what the paper claims and where its source lives;
- the Major Revision decision and every substantive reviewer concern;
- the repository layout and the role of maintained code/data files;
- authoritative datasets, checkpoints, and current results;
- what has actually been completed, what is only diagnostic, and what remains;
- environment, testing, GPU, checkpoint-selection, and reporting constraints;
- the safest order in which to continue the revision.

The project directory is historically named `prooft5`, and many model/task
paths still use `ProofT5`, `Coq`, or `CoqView`. The paper-facing system name is
**TyFlow**. In the current experiments:

- **ordinary / plain T5Gemma2** is the text-to-code baseline;
- **Coq** is the proof/synthesis-decision representation without dynamic
  CoqView re-encoding;
- **CoqView** is the full dynamic-context model and is the closest code-level
  realization of paper-facing TyFlow-2B.

Do not call every Coq-only result “TyFlow” without explaining this distinction.

### 1.1 Historical takeover snapshot (superseded by Section 0)

This block preserves the 2026-08-23 takeover state for provenance. It is not
the current status; Section 0 and the frozen package take precedence.

At **2026-08-23 21:39 UTC**:

- branch/commit are `main` / `695ac6e`; the worktree intentionally has 15
  modified tracked entries, 39 untracked status entries (many are retained
  directories containing multiple files), and no staged files;
  `git diff --check` passes;
- the complete repository regression suite last passed **69 tests** with no
  failures (30 upstream deprecation/future warnings);
- the frozen joint Coq HumanEval-v15 split evaluation is complete at
  **8/16 (50.00%) pass@1 and 9/16 (56.25%) pass@10**, versus matching
  ordinary **2/16 (12.50%) and 4/16 (25.00%)**. A later lineage audit found
  five ancestor-seen rows, so those cells are ancestor-mixed. On the matched
  11-row lineage-unseen subset, ordinary is **1/11 and 3/11**, versus Coq
  **4/11 and 5/11**; Section 5.1 records the full score and merge hashes;
- two generation campaigns are actively running and must not be duplicated
  or interrupted. GFG-v14 Coq train-414 preserves 96 completed rows from the
  original eight shards; its remaining 318 disjoint rows were repartitioned
  at 19:20 UTC into 16 LPT shards under tags
  `formal_train_gfg414_coq_reshard16_shard{0..15}_w20_20260823`. The combined
  old/new GFG sources were at **144/414** unique completed rows, with zero
  old/new overlap and zero duplicate problem IDs. HumanEval-65 CoqView has
  four active groups and was at **50/65** completed rows (`[9,10,15,16]` of
  expected `[15,16,17,17]`);
- those campaigns use only physical GPUs `0,1,6,7`. The 16 GFG shards use
  GPUs `0,6,7` and 320 Coq workers; four HumanEval-CoqView groups use GPU `1`
  and 64 workers, for a nominal total of 384. GPUs `2--5` carry other
  workloads and remain outside this project's authorized set;
- merge/scoring parents and default-off sparse-recovery monitors are already
  waiting. After both current formal scores exist, the queued order is MBJP
  Coq/CoqView train-608, HumanEval-v15 Coq train-146, joint-checkpoint GFG-v13
  train/test, and finally the explicitly contaminated HumanEval-66 replay
  diagnostic. Waiting processes consume no GPU while their prerequisites are
  absent;
- none of the queued score files listed in the live-check command below had
  yet appeared. Do not infer completion from a wrapper existing or from a
  partial shard count.

Refresh this state rather than trusting the snapshot after taking over:

```bash
cd /data2/x/hzc/prooft5
git status --short
git diff --check
nvidia-smi
ps -eo user,pid,ppid,etime,stat,%cpu,%mem,cmd | \
  rg 'formal_train_gfg414_coq|formal_train_he65_coqview|waiting_before_mbjp|wait_hev15|wait_joint_gfg|wait_he66'
for f in \
  tmp/formal_train_gfg414_coq_lpt8_merged_20260823_score_timeout10.json \
  tmp/formal_train_he65_coqview_lpt4_merged_20260823_score_timeout10.json \
  tmp/formal_train_mbjp608_coq_lpt8_merged_20260823_score_timeout10.json \
  tmp/formal_train_mbjp608_coqview_lpt8_merged_20260823_score_timeout10.json \
  tmp/formal_train_hev15_146_coq_lpt8_merged_20260823_score_timeout10.json \
  tmp/joint23_dual_gfgv13_strict103_lpt4_merged_20260823_score_timeout10.json; do
  test -f "$f" && echo "complete $f" || echo "waiting  $f"
done
```

Do not reshard or replace these routes again. The 19:20 UTC GFG reshard is
already disjoint, hash-bound by
`tmp/formal_train_gfg414_coq_remaining318_lpt16_20260823.json`, and monitored
by the live orchestration session. It will merge the eight preserved sources
and 16 new sources into the original score filename required by the MBJP gate.
Constrained Coq search is CPU-heavy and writes a problem only after it finishes.

### 1.2 Zero-context handoff coverage audit

The following matrix was rechecked on 2026-08-23 at 21:39 UTC. It makes the
scope of “sole entry point” explicit: the new session starts here, while the
linked machine-readable or verbatim source remains authoritative when exact
detail is required.

| information needed by a new session | where it is covered here | exact authority linked from this document |
|---|---|---|
| paper identity, contribution, claims, source and build | Sections 3.1--3.3 | `tosem/paper/manuscript.{tex,pdf}` and `tosem/paper/chapters/` |
| verbatim Major Revision decision and all reviewer comments | Sections 3.1 and 9 | `tosem/review_decision_2026-06-16.txt` |
| repository directories and maintained file responsibilities | Sections 4.1--4.5 | `PROJECT_STRUCTURE.md` for the expanded runtime map |
| dataset origins, normalization, counts, splits and contamination rules | Sections 6.1--6.5 | task manifests and audits named in those sections |
| MBJP/HumanEval/GFG code-style alignment and residual differences | Sections 6.3--6.5 | `docs/audits/JAVA_THREE_SOURCE_MBJP_STYLE_ALIGNMENT_AUDIT_20260823.json` |
| model parentage, frozen checkpoints and hashes | Sections 7--7.1 | `MODEL_TRAINING_INVENTORY.md` and the experiment master |
| submitted results, reproduced results and diagnostic-only results | Sections 3.3 and 8--8.1 | complete score JSONs and retained experiment reports |
| what the Major Revision has answered, partly answered, or not answered | Section 9 | issue-by-issue board derived from the verbatim reviews |
| exact remaining experiments and manuscript work | Sections 10 and 13 | frozen protocols and the experiment master |
| environment, active jobs, GPU ownership and integrity constraints | Sections 5 and 11 | live process/GPU recheck required at session start |
| dirty Git state and deleted-checkpoint provenance | Section 12 | `docs/CHECKPOINT_CLEANUP_MANIFEST_20260823.md` |

The document intentionally does not enumerate every generated candidate,
tokenizer shard, or checkpoint tensor as an independent prose entry. Section
4.5 defines their file conventions, and the named manifests/hashes provide the
auditable per-file inventory. This avoids turning the handoff into a stale
filesystem dump while still explaining every maintained file class and every
paper-facing artifact.

## 2. Source-of-truth precedence

When files disagree, use this precedence:

1. Complete machine-readable score JSON tied to a frozen checkpoint.
2. `docs/JAVA_BENCHMARK_EXPERIMENT_MASTER_20260823.md`.
3. Retained reports under `docs/experiments/` and audits under `docs/audits/`.
4. `MODEL_TRAINING_INVENTORY.md` for the original MBJP/SuFu lineage.
5. Current LaTeX source under `tosem/paper/` for claims in the submitted paper.
6. Older names embedded in scripts/logs only as historical provenance.

Never promote a fixed probe, partial output, contaminated diagnostic split, or
training loss into a paper result.

## 3. Paper and Major Revision material

### 3.1 Submission identity

- Title: **TyFlow: A Type-Aware Approach to Neural Code Models**.
- Venue: ACM Transactions on Software Engineering and Methodology (TOSEM).
- Manuscript ID: `TOSEM-2026-0076`.
- Decision date: 2026-06-16.
- Decision: Major Revision.
- Decision and verbatim reviews:
  `tosem/review_decision_2026-06-16.txt`.
- Current compiled manuscript: `tosem/paper/manuscript.pdf`, 39 pages.
- Current LaTeX entry point: `tosem/paper/manuscript.tex`.
- Current cover letter is the original submission letter, not a Major Revision
  response: `tosem/paper/cover_letter.{md,txt}`.

The PDF was visually checked on 2026-08-23 at page 1 and the main evaluation
table on page 25. It renders normally. Its creation timestamp is 2026-06-17,
and neither the LaTeX source nor PDF currently contains the new HumanEval/GFG
experiments or the Major Revision response.

### 3.2 Paper contribution and structure

TyFlow reformulates type-correct code generation as construction of an
existential proof whose witness is the program. Typing rules are represented
as constrained Horn clauses (CHCs); the generated synthesis-decision sequence
is intended to stay isomorphic to the type derivation and to reconstruct a
well-typed program. The model jointly uses the static NL specification and a
dynamically evolving proof/type context.

The submitted manuscript presents three main contributions:

1. The proof/synthesis representation and isomorphism between type and
   synthesis derivation trees.
2. A dual-encoding encoder-decoder architecture for static NL and dynamic
   synthesis context.
3. An automated TyFlow pipeline that converts existing programs to training
   decision sequences and reconstructs programs during constrained generation.

LaTeX source map:

| file | role |
|---|---|
| `tosem/paper/manuscript.tex` | metadata, abstract, contribution summary, chapter assembly |
| `chapters/intro.tex` | motivation, four desired properties, contribution claims |
| `chapters/overview.tex` | simply typed lambda-calculus running example |
| `chapters/overview-rules.tex` | typing-rule to synthesis-rule intuition |
| `chapters/overview-LM.tex` | LM interaction and decision sequence |
| `chapters/methods_meta.tex` | formal translation from typing rules to synthesis rules |
| `chapters/methods_system.tex` | construction, resolution, isomorphism, soundness/completeness |
| `chapters/model.tex` | neural architecture and term encoding |
| `chapters/evaluation.tex` | benchmarks, metrics, RQ1-RQ4, all submitted result tables |
| `chapters/related.tex` | rejection/constrained decoding, symbolic constraints, type-guided synthesis |
| `chapters/conclusion.tex` | summary and broad CHC/generalization claims |
| `chapters/appendix.tex` | proofs and benchmark details |
| `macros.tex` | paper macros and system names |
| `bibtex.bib`, `acmart.bib` | bibliography |
| `assets/` | paper figures |

The standard local build command, run from `tosem/paper`, is:

```bash
latexmk -pdf -interaction=nonstopmode manuscript.tex
```

### 3.3 Submitted evaluation claims

The submitted paper asks four research questions:

- RQ1: comparison with ordinary code-generation models;
- RQ2: contribution of syntax pruning, type pruning, and dynamic context;
- RQ3: comparison with rejection sampling;
- RQ4: integrated decision generation versus type-first/code-first generation.

Submitted RQ1 table:

| language | model | pass@1 | pass@10 | FSP | CER |
|---|---|---:|---:|---:|---:|
| SuFu | CodeT5-220M | 24.14 | 32.76 | 7.03 | 83.10 |
| SuFu | T5Gemma2-2B | 29.31 | 37.93 | 6.69 | 61.21 |
| SuFu | TyFlow-220M | 37.93 | 46.55 | 5.48 | 0.00 |
| SuFu | TyFlow-2B | 43.10 | 50.00 | 5.03 | 0.00 |
| Java | CodeT5-220M | 10.45 | 20.90 | 8.19 | 38.51 |
| Java | T5Gemma2-2B | 17.91 | 35.82 | 6.99 | 15.22 |
| Java | TyFlow-220M | 11.94 | 28.36 | 7.94 | 3.52 |
| Java | TyFlow-2B | 23.19 | 40.30 | 6.76 | 3.12 |

These numbers remain the submitted-paper values. New clean reproduction
numbers below do not silently replace them.

## 4. Repository map

### 4.1 Top-level directories

| directory | maintained purpose |
|---|---|
| `tosem/` | submitted paper, decision letter, LaTeX, PDF, cover letter |
| `docs/` | current experiment ledger, retained reports, audits, cleanup provenance, this handoff |
| `Utils/data/` | ProofT5/Coq/CoqView task directories: pickle splits, configs, rules, tokenizers |
| `Utils/models/` | ProofT5, Coq, CoqView, and base checkpoints; mostly Git-ignored |
| `Utils/output/` | generated candidates and score-bound output directories; mostly Git-ignored |
| `Utils/processdata/` | Java parsing, AST conversion, grammar serialization |
| `Utils/score_output/` | historical Java/SuFu scorers and result CSVs |
| `Utils/evaluator/` | CodeBLEU and evaluation helpers |
| `coq_model/` | Java/Coq semantics, proof rendering, Java conversion, MXEval runner, parser support |
| `SuFu/` | SuFu benchmark, parser/type model, source/compiler toolchain |
| `t5_llm/` | ordinary CodeT5/T5Gemma2 training, data JSONs, checkpoints |
| `scripts/` | reproducible dataset builders, audits, launchers, selection and summarization tools |
| `tests/` | maintained regression tests for loaders, training, decoding, scoring, and audits |
| `selected_data/` | frozen source/split manifests for selected external data |
| `tmp/` | experiment logs, score JSONs, runtime state, and ignored evidence; not generally disposable |

IDE directories `.idea/` and `.vscode/` are local editor metadata, not
experiment inputs.

### 4.2 Core root files

| file | role |
|---|---|
| `run.py` | main ProofT5/Coq/CoqView train/eval entry point; distributed partitioning, loss and generation orchestration |
| `Dataset.py` | ProofT5 pickle loading, collation, prefix cutting, distributed zero-loss padding |
| `Model.py` | legacy CodeT5 model definitions |
| `ModelT5Gemma2.py` | T5Gemma2 ProofT5 adaptations |
| `beamsearch.py` | generic constrained beam search |
| `beamsearch_coq.py` | Java grammar/Coq/CoqView decoding and proof checks |
| `beamsearch_sufu.py` | SuFu constrained decoding and type guards |
| `beamsearch_cache.py` | cache reordering/tokenizer helpers shared by decoders |
| `beamsearch_dsl.py`, `beamsearch_sufu_cd.py` | legacy/specialized decoder variants |
| `score_java_no_write.py` | paper-facing Java functional scoring with provenance, timeouts, candidate/dataset hashes |
| `score_sufu_no_write.py` | SuFu functional scoring and output-comparison controls |
| `t5_llm/finetune_t5gemma2.py` | ordinary T5Gemma2 training/generation, target modes, checkpointing and global metrics |
| `prepare_t5gemma2_retokenized_prooft5_data.py` | fixed-vocabulary ProofT5 retokenization |
| `prepare_t5gemma2_java_coqview_promptprefix.py` | Java CoqView task preparation |
| `prepare_t5gemma2_sufu_coqview_ctxfix.py` | SuFu CoqView task preparation |
| `get_tokenizer.py` | tokenizer helper |
| `trans_dsl_program.py` | DSL-to-executable conversion |
| `run.sh`, `run_overall.sh`, `acc_config.yaml` | historical launch wrappers/config |
| `MODEL_TRAINING_INVENTORY.md` | canonical original MBJP/SuFu model lineage and historical decisions |
| `PROJECT_STRUCTURE.md` | detailed runtime and directory reference |
| `readme.md` | legacy project overview; less current than this handoff |

Important implementation fixes currently present in the dirty diff include:

- safe empty-validation loading;
- exact distributed partitioning and zero-loss padding without NaN loss;
- complete-epoch global training metrics;
- process-safe Java scoring work directories and provenance hashes;
- Coq timeout and completed-candidate handling;
- length-penalty-correct stopping and rejection of unfinished beams;
- process-specific Coq files and initial-context cache/retry support;
- task-local grammar filtering when switching pickled task vocabularies;
- SuFu surface rendering/type checks;
- linear-time Java `StConcat` rendering.

These changes are covered by the maintained tests and must not be reverted as
“unrelated cleanup.”

### 4.3 Retained scripts by responsibility

Dataset construction and normalization:

- `build_java_external_datasets.py`, `build_humaneval_java_compat_dataset.py`,
  `build_transcoder_gfg_java_dataset.py`;
- `build_half_split_expansion.py`, `prepare_selected_expansion_datasets.py`;
- `build_java_expansion_mbjp_native_prompt_v13.py`,
  `repartition_java_expansion_parent_safe_v14.py`;
- `build_java_expansion_{pair,paired_prompt,single}_curriculum.py`;
- `build_java_expansion_length_repair_task.py`;
- `build_java_expansion_eval_only_tasks.py`,
  `build_java_expansion_single_source_train_probe.py`;
- `build_complete_train_eval_task.py`, `build_complete_coqview_task.py`,
  `build_evaluation_subset_task.py`, `build_debug_overlap_training_sets.py`;
- `partition_eval_indices_by_length.py` creates deterministic, hash-bound
  longest-processing-time shards for expensive full Coq evaluations;
- `merge_candidate_output_shards.py` refuses incomplete/conflicting shards,
  requires every candidate and beam-score file, and writes an auditable merge
  manifest before a merged result can be scored;
- `build_sufu_synthetic_dataset.py` is retained for original-data provenance,
  not as authorization to restart the abandoned SuFu expansion branch.

Auditing and diagnosis:

- `audit_expanded_dataset_roundtrip.py`;
- `audit_java_expansion_parent_safe_v14.py`;
- `audit_complete_coqview_{bounds,training}.py`;
- `audit_sufu_generated_candidates.py`;
- `compute_exact_train_test_overlap.py`;
- `diagnose_java_beam_gold_survival.py`;
- `build_java_seen_unseen_diagnostic.py` creates a labelled contaminated
  diagnostic only; its result is never a held-out benchmark number.
- `build_java_joint_seen_replay_task.py` adds explicitly labelled HumanEval
  replay rows to the three-source joint task. It is a training-chain
  diagnostic only and must never define a held-out result.

Training/evaluation/selection:

- `run_clean_java_plain_t5gemma2.sh`;
- `continue_clean_java_after_coqview.sh`;
- `run_complete_coqview_training.sh`;
- `evaluate_clean_java_{plain,proof}_checkpoint.sh`;
- `evaluate_java_expansion_plain_file.sh`;
- `run_java_expansion_pair_plain_training.sh`;
- `select_{plain,coq,coqview}_checkpoint_from_training*.py`;
- `summarize_clean_java_reproduction.py`;
- `run_formal_paper_evaluation_20260802.sh`,
  `summarize_formal_paper_checkpoints.py`,
  `sweep_complete_coqview_checkpoints.sh` retain original-paper provenance.

Environment:

- `runtime_env.sh`, `check_language_runtimes.sh`,
  `build_language_runtimes.sh`.

### 4.4 Regression tests

The retained tests are not disposable experiment leftovers:

- task/data integrity: `test_complete_{train_eval,coqview}_task.py`,
  `test_evaluation_only_dataset.py`, `test_compute_exact_train_test_overlap.py`;
- distributed training/metrics: `test_distributed_eval_range.py`,
  `test_zero_loss_distributed_padding.py`,
  `test_global_training_loss_metrics.py`,
  `test_plain_checkpoint_training_log.py`;
- decoder correctness: `test_forced_gold_coqview_beam_alignment.py`,
  `test_coq_completed_timeout_guard.py`, `test_final_only_coq_check.py`,
  `test_length_penalty_termination.py`, `test_sufu_decoder_options.py`;
- rendering/scoring: `test_stconcat_render_once.py`,
  `test_score_workdir_scope.py`, `test_sufu_functional_output_comparison.py`,
  `test_sufu_type_guard_and_printer.py`;
- final audit/summarization: `test_audit_complete_coqview_{bounds,training}.py`,
  `test_audit_sufu_generated_candidates.py`,
  `test_summarize_formal_paper_checkpoints.py`.

### 4.5 Generated-artifact file conventions

The repository contains many generated candidates and checkpoints, so a
literal line-by-line inventory would be both stale and misleading. The
maintained files are covered above; generated files follow these conventions:

| location/pattern | meaning |
|---|---|
| `Utils/data/<task>/train.pkl` | proof/decision-format training rows consumed by `run.py` |
| `valid.pkl`, `test.pkl` | proof-format validation/test rows; deliberately empty for current training-only tasks |
| `train.json`, `valid.json`, `test.json` | inspectable JSON representation of the same task split |
| `*_t5_plain_format.json` | ordinary text-to-code examples for `t5_llm/finetune_t5gemma2.py` |
| `config.json` | task/model vocabulary and decoding configuration |
| `rules.{pkl,json}` | task grammar/rule inventory |
| `tokenizer.pkl`, `coq_tokenizer.pkl` | frozen task tokenizers; do not silently substitute between tasks |
| `*manifest*.json`, `*rows*.jsonl` | split/replay provenance, counts, hashes, and row-level audit trail |
| `Utils/models/Model*/last_model.ckpt` | selected or latest ProofT5/Coq/CoqView checkpoint; selection status must come from the ledger, not the filename |
| `*/epoch*_model.ckpt`, `final_model.ckpt` | intermediate/final training snapshots |
| `t5_llm/models/<model>/` | Hugging Face ordinary-model directory; normally contains config, tokenizer, and weight files |
| `Utils/output/<run>/` | generated candidate programs/proofs; meaningful only together with task, checkpoint, and decoder settings |
| `tmp/*.json` | machine-readable scores/audits; complete scored JSON has higher authority than prose |
| `tmp/*.log`, `*_metrics.jsonl` | launcher output and step/epoch metrics; loss is not functional correctness |

For an exact per-file runtime description, read `PROJECT_STRUCTURE.md`. For
model parentage and which similarly named checkpoint is authoritative, read
`MODEL_TRAINING_INVENTORY.md`; for Java-extension artifacts and scores, read
`docs/JAVA_BENCHMARK_EXPERIMENT_MASTER_20260823.md`. Files not covered by one
of those ledgers are not automatically safe to delete or safe to cite.

## 5. Environment and operating constraints

### 5.1 Execution state at handoff

At the latest handoff check on 2026-08-23 13:03 UTC:

- two formal **evaluation** routes were active; no new training was running;
- the ordinary MBJP-608 training-set evaluation was running on physical GPU
  `1` under output tag `formal_train_mbjp608_plain_retrytok_20260823`;
- six independent HumanEval-65 Coq evaluation shards were running two per
  physical GPU on GPUs `0,6,7`, under tags
  `formal_train_he65_coq_shard{0..5}_w64_20260823`;
- GPUs `2,3,4,5` were occupied and remain outside this project's authorized
  GPU set; never stop, renice, or otherwise interfere with those processes;
- the frozen paper-table checkpoints, current diagnostic checkpoints, score artifacts,
  paper source/PDF, review letter, experiment master, inventory, structure
  guide, and cleanup manifest referenced by this document all existed;
- `git diff --check` returned cleanly.

Do not launch duplicate copies of the active evaluations. A new session cannot
attach to the old Codex terminal session, but it can inspect them with:

```bash
ps -eo pid,ppid,etime,stat,%cpu,cmd | \
  rg 'formal_train_mbjp608_plain_retrytok|formal_train_he65_coq_shard'
nvidia-smi
tail -50 tmp/formal_train_mbjp608_plain_retrytok_20260823.log
tail -30 tmp/formal_train_he65_coq_shard0_w64_20260823.log
```

At 13:03 UTC, the ordinary MBJP job had been running for about 34 minutes. The
six Coq shards had been running for about one minute and had not yet written a
complete item. This is expected because the generator writes an item's ten
candidates only after the item finishes. Absence of early candidate files is
not by itself a crash. The earlier stopped Coq attempt
`formal_train_he65_coq_3gpu_w128_20260823` contains five complete items:
IDs `0,21,22,23,24` (50 candidate files plus five beam-score files). Preserve
that directory; it is an input to the final auditable merge.

Later status at 14:27 UTC: the ordinary MBJP job and its functional scorer
completed successfully, producing the audited 506/608 and 564/608 result in
Section 8. GPU `1` was then assigned to the predeclared one-time
HumanEval-v15 strict-16 evaluation of the frozen dual-rehearsal checkpoint,
under tag `joint23_dual_hegfg_hev15_strict16_frozen_20260823` and log
`tmp/joint23_dual_hegfg_hev15_strict16_frozen_20260823.log`. The six formal
HumanEval-train Coq shards remained active on GPUs `0,6,7`; 39/65 total rows
(including the preserved five-row earlier run) had complete outputs. Do not
duplicate either route.

At 14:50 UTC the strict-16 route was repartitioned for throughput without any
protocol or model change: completed ID 0 remains in the original tag, IDs
1--7 run under `joint23_dual_hegfg_hev15_strict16_shardA_20260823`, and IDs
8--15 under `joint23_dual_hegfg_hev15_strict16_shardB_20260823`. Both shard
processes share physical GPU `1` and use 32 Coq workers. Merge all three
sources with the strict merge tool before scoring; never cite a partial
wrapper's nominal 16-row score.

Latest live snapshot at 15:23 UTC:

- HumanEval-65 formal Coq train evaluation has **58/65** complete, disjoint
  per-item outputs across the preserved five-item run and six shards. Shards
  1--4 are complete; shard 0 has 3/9 and shard 5 has 9/10 outputs and both are
  still running on physical GPUs 0 and 7. Do not report or score the partial
  denominator; merge only after all IDs 0--64 exist.
- The frozen HumanEval-v15 strict-16 route has **3/16** complete outputs: ID 0
  in the original tag, two outputs in shard A, and none yet in shard B. Both
  shards remain active on physical GPU 1. This is a prespecified one-time
  evaluation, not checkpoint selection.
- The formal GFG-414 Coq train evaluation has begun LPT shard 0 of 8 on
  physical GPU 6. At this snapshot it has **0/52** completed outputs in shard
  0 and therefore **0/414** mergeable results. The seven remaining LPT shards
  have not been launched.
- No training job is active. These are generation/functional-evaluation jobs.
  GPUs 2--5 remain occupied by processes outside the authorized experiment
  set and must not be touched.
- `git diff --check` is clean. The working tree remains intentionally dirty.

The exact live tags added after the earlier snapshot are:

```text
joint23_dual_hegfg_hev15_strict16_{frozen,shardA,shardB}_20260823
formal_train_gfg414_coq_lpt8_shard0_w64_20260823
```

Candidate output counts can be refreshed without modifying state using:

```bash
find Utils/output -type d -name '<output-tag>' -print -quit
find '<resolved-output-directory>' -name '*_beam_scores.json' | wc -l
```

Completed update at 16:08 UTC: the sharded HumanEval-65 Coq train evaluation
finished and was merged with the fail-closed merge tool. The merged directory
contains exactly 65 problem IDs, 650 candidates, and 65 beam-score files. Its
formal functional result is **55/65 (84.62%) pass@1 and 60/65 (92.31%)
pass@10**, compared with the ordinary model's 49/65 and 55/65. The result has
no missing outputs; it records 28 compilation failures and four candidate
timeouts. The strict HumanEval-v15 evaluation and six GFG LPT shards remain
active; do not duplicate them. See Section 8 for the authoritative artifacts.

Live scheduling update at 16:13 UTC: strict-16 has nine complete outputs
(original ID 0, five in shard A, three in shard B). The current long-tail
items are being preserved while dedicated ID-7 and ID-13 shards run on the
same authorized physical GPU 1. An automated monitor will stop original shard
A after ID 6 and original shard B after ID 12, so their queued duplicates are
not regenerated; IDs 14 and 15 still need a supplemental shard afterward.
The earlier three-source merge monitor was intentionally stopped because its
source partition changed; create the final merge only from the completed
original/A/B/ID-7/ID-13/ID-14/ID-15 sources.

GFG LPT shards 0, 1, 2, 3, 6, and 7 are active, with completed-item counts
4, 1, 1, 0, 4, and 3 respectively at this snapshot. Shard 4 was briefly
started but deliberately paused with zero outputs to give its 32-worker CPU
budget to the strict long-tail split; resume it under a new, non-overwriting
tag. Shard 5 has not been launched. Do not treat the current 13/414 outputs as
a score.

Latest scheduling update at 16:43 UTC:

- HumanEval-v15 strict-16 has every output except ID 6. Original shard B
  completed IDs 8--12 and was stopped before its queued duplicates; dedicated
  shards completed IDs 7, 13, 14, and 15. Original shard A is generating ID 6
  and had reached approximately prefix 317 of the fixed 719-token cap. A
  fail-closed seven-source merge/scoring monitor is active and will require
  all 16 IDs before writing the strict score.
- All four balanced HumanEval-65 CoqView training-evaluation groups are active
  on physical GPU 1, 16 Coq workers each. Their immutable partition manifest
  is `tmp/formal_train_he65_coqview_lpt8_20260823.json`; paired groups contain
  15, 16, 17, and 17 rows. They will merge and score only at 65/65.
- The six active GFG shards remain on physical GPUs 0, 6, and 7. An
  orchestrator waits for the strict score, then starts GFG shards 4 and 5 on
  GPU 1 and requires exact shard counts `[52,52,51,52,51,52,52,52]` before a
  414-row merge and score.
- The final MBJP Coq and CoqView train evaluations are also pre-scheduled but
  have not started. They wait for complete GFG and HumanEval-CoqView score
  artifacts, then use the four authorized GPUs, eight LPT shards per model,
  and generation-only shard processes to avoid sixteen redundant partial
  scorers. Partition manifests are
  `tmp/formal_train_mbjp608_coq_lpt8_20260823.json` and
  `tmp/formal_train_mbjp608_coqview_lpt8_20260823.json`.

Do not start duplicate strict, GFG, HumanEval-CoqView, or MBJP jobs while these
orchestrators and their child processes survive. Recheck live processes and
score files before taking over after a host/session restart.

At 16:50 UTC the strict route had advanced to **15/16 complete**: only ID 6
remains in original shard A, at approximately prefix 344/719. All four
HumanEval-CoqView groups are active and have begun writing outputs. GFG shard
4 was started early under `formal_train_gfg414_coq_lpt8_shard4retry_w32_20260823`
using the last available 32-worker budget; shard 5 alone remains gated on the
strict score. The nominal project Coq-worker total is 384, exactly the host
core count, and no additional generation process may be added until one of
these routes releases workers. Wrapper guards prevent completed partial
HumanEval-CoqView and GFG shards from launching redundant aggregate scorers.

At 16:56 UTC a read-only functional audit of the 15 completed strict outputs
established the required trend before ID 6 finished: 8/15 are top-1 solved
and 9/15 are top-10 solved. Consequently the final 16-row Coq result has a
mathematical lower bound of **8/16 (50.00%) pass@1 and 9/16 (56.25%)
pass@10**, already above the matching ordinary-v15 checkpoint's 2/16
(12.50%) and 4/16 (25.00%). This audit cannot replace the final merge, but ID
6 can only maintain or increase these numerators. The checkpoint and strict
protocol were frozen before results were opened, and no new checkpoint may be
selected from this evidence. Source-bound partial-audit JSONs use the prefix
`tmp/joint23_strict16_partialaudit_`.

Final handoff recheck at 17:00 UTC (read-only; no process was modified):

- the strict HumanEval-v15 route remains at **15/16** complete, with ID 6
  still running in shard A; its final merged score JSON does not yet exist;
- seven GFG-414 Coq shards are active, with completed counts
  `[9,4,4,2,2,0,9,3]` for shards 0--7; shard 5 remains gated on the strict
  score, so the current total is **33/414** and is not reportable;
- all four HumanEval-65 CoqView groups are active, with counts
  `[1,1,0,1]`, or **3/65** in total; its merged score does not yet exist;
- the MBJP Coq/CoqView train evaluations remain scheduled but have not begun;
- the project still uses only physical GPUs `0,1,6,7`; GPUs `2--5` remain
  outside the authorized set. Live GPU/process state must be rechecked rather
  than assuming these timestamped counts are still current.

Queue update at 17:14 UTC:

- the matching ordinary-model full HumanEval-v15 train-146 evaluation is
  complete under tag `formal_train_hev15_146_plain_selected_20260823`:
  145/146 (99.32%) at both pass@1 and pass@10, with no missing outputs. Its
  score JSON is
  `tmp/formal_train_hev15_146_plain_selected_20260823_score_timeout10.json`
  and has SHA-256
  `a5209883dbb2ad0ca32282280d21c42ccadc905b5d5ebfcbe60bf6ef7e20d7be`;
- a frozen-checkpoint Coq train-146 evaluation waits for both MBJP train score
  artifacts, using `tmp/formal_train_hev15_146_coq_lpt8_20260823.json`;
- a GFG-v13 train-414 evaluation-only mirror was created at
  `Utils/data/gfg_v13_train414_eval_t5gemma2_20260823`; its joint-checkpoint
  train-414 and strict-test-103 evaluations wait for the HumanEval train-146
  Coq score;
- the GFG manifests are
  `tmp/formal_train_gfgv13_414_jointcoq_lpt8_20260823.json` and
  `tmp/joint23_dual_gfgv13_strict103_lpt4_20260823.json`; builder and
  partition regression tests pass (2 tests);
- the chained wait processes do not reserve GPUs or CPU while gated. They
  fail closed on missing predecessor score artifacts and use only GPUs
  `0,1,6,7` when released.

Completed strict update at 19:04 UTC:

- the frozen joint Coq checkpoint's HumanEval-v15 strict result is **8/16
  (50.00%) pass@1 and 9/16 (56.25%) pass@10**, versus matching ordinary
  **2/16 (12.50%) and 4/16 (25.00%)**;
- the final score JSON is
  `tmp/joint23_dual_hegfg_hev15_strict16_merged_20260823_score_timeout10.json`
  with SHA-256
  `f3a1db0e3f095ffd97a04dffc29f2ee4ab0e8c821b960f45d2d30be541f36f1d`;
- ID 6 exhausted constrained search after four candidates. Sparse merge mode
  copied 170/176 expected files, requires beam metadata for every problem,
  and explicitly manifests the six missing ranks; there are no missing
  problem outputs. The merge-manifest SHA-256 is
  `f3902c61027a60f1fdbe43872f48f585c28f6c0c0452b1a0bae2b84849506cc4`;
- `scripts/merge_candidate_output_shards.py` now has an explicit, default-off
  `--allow-missing-candidates` mode for beam exhaustion. Its regression tests
  pass, and the complete repository suite passes **69 tests**. Default merging
  remains fail closed;
- the strict score released GFG shard 5 on GPU 1. The original GFG full-train
  merge/scoring orchestrator remains active.
- default-off sparse-recovery monitors now cover GFG-v14, HumanEval
  CoqView, MBJP Coq/CoqView, HumanEval-v15 train-146, joint GFG train/test,
  and the 66-row seen-replay diagnostic. Each monitor waits for its original
  parent orchestrator to exit and does nothing if the formal score already
  exists; it only retries merge/scoring when constrained-beam exhaustion made
  the original strict merge fail. These monitors consume no GPU/Coq workers
  while waiting.
- a 19:08 UTC read-only audit of completed active outputs found 88 GFG
  problems with 877 real candidates: 87 have ten and one has seven after beam
  exhaustion. All 27 then-complete HumanEval-CoqView problems have ten. Beam
  metadata candidate counts exactly match candidate files for every audited
  problem, so the sparse case is genuine search exhaustion rather than an
  interrupted write.

Post-result provenance correction at 19:18 UTC: the v15 test has zero overlap
with the direct v15 training rows, but test indices `3,6,7,10,12` occur in the
clean-673 Coq ancestor's HumanEval training membership. The 8/16 and 9/16
result is therefore **split-held-out but ancestor-mixed**. A matched functional
re-score of the 11 lineage-unseen rows gives ordinary **1/11 (9.09%) pass@1,
3/11 (27.27%) pass@10** and Coq **4/11 (36.36%), 5/11 (45.45%)**. The positive
direction survives the leakage-safe comparison. Authority:
`docs/audits/JAVA_HUMANEVAL_V15_ANCESTOR_OVERLAP_AUDIT_20260823.json`.

The seen-replay route and later HumanEval/GFG curricula received prespecified
training-side probes. Rejected intermediate checkpoints are not selected.
The frozen dual-rehearsal checkpoint is the revised ProofT5 model in the
six-row table; its HumanEval result is complete and its GFG-v13 strict test is
active. See Sections 6.5, 7.1, and 8.1.

This is a timestamped observation, not a reservation. A new session must
rerun `nvidia-smi` and inspect process ownership immediately before launching
any job.

Important ordinary-training limitation discovered on 2026-08-23:
`t5_llm/finetune_t5gemma2.py` currently binds to `cuda`/GPU 0 and does not
honour `LOCAL_RANK`. Do **not** launch it through multi-process `accelerate`:
that creates duplicate independent trainings and can race-write one output
directory. Use one single-process job on one explicitly visible GPU until the
trainer is repaired and tested for DDP. The aborted duplicate route under
`Utils/data/t5gemma2-2b_java_joint3source_seenreplay4_from_joint23_lr2e6_p3_20260823`
has no valid model checkpoint.

### 5.2 Runtime setup

Python environments:

```text
/data2/x/hzc/.uv-envs/prooft5-py313
/data2/x/hzc/.uv-envs/prooft5-t5gemma-py313
```

Recommended setup:

```bash
cd /data2/x/hzc/prooft5
source /data2/x/hzc/.uv-envs/prooft5-t5gemma-py313/bin/activate
export PATH=/data2/x/hzc/.local/jdks/temurin17/bin:/home/zchuang/.opam/with-coq-8.20.1/bin:/home/zchuang/.opam/default/bin:$PATH
source scripts/runtime_env.sh
scripts/check_language_runtimes.sh
```

The environments do not permanently include pytest. The verified test command
is:

```bash
uv run --python /data2/x/hzc/.uv-envs/prooft5-t5gemma-py313/bin/python \
  --with pytest python -m pytest -q tests
```

Latest complete-suite result: **69 passed** on 2026-08-23 after adding the
sparse beam-exhaustion merge regression. The 30 emitted messages are upstream
deprecation/future warnings; there are no test failures.

### 5.3 GPU and experiment constraints

GPU constraint inherited from the experiment plan:

- use at most four GPUs;
- the previously authorized set was GPUs `0,1,6,7`;
- do not interfere with other users' jobs, especially prior jobs observed on
  GPUs `2-5`;
- GPU ownership is time-varying, so run `nvidia-smi` and inspect process users
  again before every launch.

Data/selection constraints explicitly chosen by the user:

- validation must remain empty for the current new-data routes;
- do not create a validation split merely to select a checkpoint;
- use training loss, complete training-side functional gates, or a
  prespecified final pass for checkpoint selection;
- do not select checkpoints from held-out test performance;
- always keep checkpoint path/fingerprint, task path, decoder settings,
  candidate count, missing outputs, compilation failures, and timeouts.

## 6. Authoritative datasets and splits

### 6.1 Submitted-paper data

- SuFu: paper states 290 programs, random 80/20 split, normally interpreted as
  232 train and 58 test.
- Java/MBJP: paper states a 608-task covered subset with a 90/10 split.

There is an unresolved count/protocol inconsistency that must be addressed
before revision: the current clean reproduction uses **608 MBJP training
tasks plus 67 MBJP test tasks**, whereas the submitted text describes 608
tasks total. Do not conceal or “round away” this discrepancy. Verify the
original data construction and revise the paper's dataset description/table.

### 6.2 Clean MBJP + HumanEval setting

Proof-format training task:

```text
Utils/data/mbjp_humaneval_half_train_t5gemma2_20260731
```

- train: 673 = 608 MBJP + 65 HumanEval-Java;
- validation: 0;
- test: 0;
- historical `debug.pkl`: 33 rows, excluded from clean runs.

Frozen tests:

```text
Utils/data/mbjp_original_test_t5gemma2_20260731       # 67
Utils/data/humaneval_half_test_t5gemma2_20260731     # 66
```

Ordinary-model JSONs:

```text
t5_llm/data/java_mbjp_humaneval_half_train_t5.json
t5_llm/data/java_mbjp_original_test_t5.json
t5_llm/data/java_humaneval_half_test_t5.json
```

Split manifest:

```text
selected_data/expansion_half_split_20260731/split_manifest.json
```

The documented complete-proof-signature overlap between clean train and each
test is zero.

### 6.3 TransCoder-GFG v14 setting

```text
Utils/data/java_transcoder_gfg_mbjp_native_parent_safe_split80_20_t5gemma2_20260820_v14
```

- train: 414;
- validation: 0;
- test: 103;
- fixed parent-safe 80/20 split;
- all 517 gold programs compile and pass their tests;
- ordinary/proof rows, tokenizers, and rule artifacts are aligned.

Audit:

```text
docs/audits/JAVA_EXPANSION_PARENT_SAFE_V14_AUDIT_20260820.json
```

Ordinary length-repair training task:

```text
Utils/data/java_transcoder_gfg_parent_safe_v14_lengthrepair1242_complex2_t5gemma2_20260820
```

Coq paired training task:

```text
Utils/data/java_mbjp_transcoder_gfg_parent_safe2164_v14_complex2_exposure3_pair_t5gemma2_20260820
```

Formal full-training evaluation task built on 2026-08-23:

```text
Utils/data/gfg_v14_train414_eval_t5gemma2_20260823
```

It exposes the exact frozen 414-row v14 training split as evaluation-only
`test`, keeps train/validation empty, carries parallel ordinary rows, and
records source indices and hashes in `evaluation_subset_manifest.json`.

### 6.4 Diagnostic datasets that must remain labelled

- GFG v13 `414/0/103`: stronger ordinary baseline, retained for diagnosis.
- HumanEval v14 `129/0/33`: parent-safe interpolation diagnosis.
- HumanEval v15 `146/0/16`: semantic-support exploratory split.
- HumanEval mixed 66-row diagnostic: 54 rows belong to v15 training
  membership; its high score is contaminated and is not reportable.

The user decided not to pursue a new SuFu extension benchmark. Original SuFu
remains part of the paper, but the abandoned synthetic-extension model branch
was deleted during cleanup.

### 6.5 Latest three-source joint and replay tasks

The latest joint task is:

```text
Utils/data/java_mbjp_humaneval_v15_transcoder_v13_semanticsupport1623_complex2_cov4_t5gemma2_20260822
```

- 1,623 effective training rows and 1,101 unique rows;
- source balance: MBJP 541, HumanEval-Java 146, GFG 414, replayed to 541
  occurrences per source;
- validation: 0; test: 0;
- used only for training and training-side checkpoint gates;
- strict tests remain separate from this task.

The explicit seen-replay diagnostic task is:

```text
Utils/data/java_joint3source_v15v13_humaneval_seenreplay4_20260823
```

- base joint rows: 1,623;
- 33 HumanEval diagnostic rows replayed four times: 132 occurrences;
- effective train rows: 1,755; validation: 0; test: 0;
- ordinary and proof row counts match;
- provenance, hashes, and reporting restriction are frozen in
  `seen_replay_manifest.json` inside the task directory.

This replay route was requested as an exploratory train/test-mixing check. A
score on its 66-row HumanEval diagnostic is contaminated. Report seen and
unseen membership separately and never call the aggregate held out. In the
v15 membership audit, 54/66 diagnostic rows already occur in training, so a
high aggregate result would not establish generalization.

Later training-only curricula, all with empty validation and test splits:

| task | effective source occurrences | role |
|---|---:|---|
| `java_mbjp_humaneval_semanticsupport1082_v15_pair_t5gemma2_20260822` | MBJP 541 + HumanEval 541 | HumanEval-focused rehearsal while retaining MBJP |
| `java_humaneval_v15_single541_semanticsupport_t5gemma2_20260823` | HumanEval 541 | isolate HumanEval fitting/termination behavior |
| `java_transcoder_gfg_v13_single541_semanticsupport_t5gemma2_20260823` | GFG 541 | measure and repair cross-benchmark forgetting |
| `java_humaneval_v15_transcoder_v13_dual1082_t5gemma2_20260823` | HumanEval 541 + GFG 541 | joint low-LR rehearsal to avoid single-source oscillation |

The dual-source task required a backward-compatible extension to
`scripts/build_java_expansion_pair_curriculum.py`: `--base-source` now selects
the first retained source and defaults to `mbjp`, so old commands are
unchanged. Its manifest records that the upstream replay policy uses gold IR
structure/test-source information. Treat it as an exploratory diagnostic
curriculum, not as evidence of untouched-test generalization.

Before any new strict output from the final dual checkpoint is opened, the
checkpoint, datasets, decoder settings, comparisons, and reporting rules are
frozen in:

```text
docs/experiments/JAVA_JOINT23_FROZEN_EVALUATION_PROTOCOL_20260823.md
```

It predeclares HumanEval-v15 test-16 and GFG-v13 test-103 as strict held-out
evaluations and the HumanEval 66-row set as a separate diagnostic with 54
training members and only 12 untrained rows. The latter cannot replace either
strict result.

## 7. Frozen checkpoints

Current paper-facing six-row Java table uses ordinary T5Gemma2 and ProofT5
(ours). CoqView is historical only and is removed from the active reporting
and training queue:

| scope | model | checkpoint |
|---|---|---|
| MBJP + HumanEval | ordinary | `t5_llm/models/t5gemma2-2b_java_clean673_noleak_b5_lr5em5_pass30_20260811_after_clean_coqview/20260811_after_clean_coqview/epoch_20` |
| MBJP | ProofT5 (ours) | `Utils/models/Modelmbjp_humaneval_half_train_t5gemma2_20260731_clean673_noleak_formal30_8gpu_b5_lr1em5_20260810/last_model.ckpt` |
| HumanEval v15 + GFG v13 | ProofT5 (ours), revised joint route | `Utils/models/Modeljoint23_dual_hegfg_from_heonly_lr2e6_p5_20260823/last_model.ckpt` |
| GFG v14 | ordinary | `t5_llm/models/t5gemma2-2b_java_transcoder_gfg_parent_safe_v14_lengthrepair_stage2_selected_20260820` |
| GFG v14 historical route | ProofT5 (ours) | `Utils/models/Modeljava_mbjp_transcoder_gfg_parent_safe2164_v14_coq_selected_20260820/last_model.ckpt` |

Their five documented fingerprints were reverified after cleanup. For an HF
directory, the fingerprint hashes the sorted top-level file manifest; for a
`.ckpt`, it is the file SHA-256. Exact values are in
`docs/JAVA_BENCHMARK_EXPERIMENT_MASTER_20260823.md`.

Original SuFu paper-facing checkpoints were also explicitly checked after
cleanup:

```text
t5_llm/models/paper_comparison_20260731/t5gemma2-2b_sufu
Utils/models/Modelsufu_original_synthetic_half_train_t5gemma2_20260731_complete281_formal100_8gpu_b5_lr5em5_20260731_105207/last_model.ckpt
Utils/models/Modelsufucoqview_complete281_from_sufu100_fullseq_20260801_sufu_fullseq_b1_lr5em6_pass10_20260802_205911/last_model.ckpt
```

Consult `MODEL_TRAINING_INVENTORY.md` before using any other original-paper
checkpoint.

### 7.1 Exploratory 2026-08-23 joint checkpoints

These checkpoints are retained as training evidence. The final dual-rehearsal
checkpoint is the revised HumanEval-v15/GFG-v13 ProofT5 row; rejected
intermediate checkpoints are not additions to the six-row paper table:

| route | checkpoint | status |
|---|---|---|
| ordinary joint, five passes | `t5_llm/models/t5gemma2-2b_java_joint3source_v15v13_from_v14joint_lr1e6_p5_20260823` | training probes incomplete/weak |
| Coq from HumanEval-v14 parent, ten passes | `Utils/models/Modeljoint_v15v13_coq_from_hev14_lr1e6_p10_20260823/last_model.ckpt` | rejected by GFG training gate |
| Coq from GFG-v14 parent, ten passes | `Utils/models/Modeljoint_v15v13_coq_from_gfgv14_lr5e7_p10_20260823/last_model.ckpt` | rejected by HumanEval training gate |
| balanced curriculum candidate E | `Utils/models/Modeljoint23_D_hev15_continue_lr2e6_p2_20260823/last_model.ckpt` | best small-probe balance; full gate not passed |
| seen-replay candidate | `Utils/models/Modeljoint23_E_seenreplay4_lr2e6_p3_20260823/last_model.ckpt` | evaluated diagnostic parent; not selected |
| stronger seen-replay continuation | `Utils/models/Modeljoint23_replay_strong_lr1e5_p10_20260823/last_model.ckpt` | very low loss but only partial functional fit |
| MBJP+HumanEval focus | `Utils/models/Modeljoint23_strong_hefocus_v15_lr5e6_p10_20260823/last_model.ckpt` | improves completed HumanEval beam-10 probe to 5/7, 6/7 |
| HumanEval-only focus | `Utils/models/Modeljoint23_heonly541_from_hefocus_lr5e6_p10_20260823/last_model.ckpt` | 7/7 completed top-1 items; item 7 non-terminating; forgets GFG item 1 |
| GFG single-source restore | `Utils/models/Modeljoint23_gfgrestore_from_heonly_lr2e6_p3_20260823/last_model.ckpt` | restores GFG but loses HumanEval item 5 top-1 |
| HumanEval+GFG dual rehearsal | `Utils/models/Modeljoint23_dual_hegfg_from_heonly_lr2e6_p5_20260823/last_model.ckpt` | best joint training-side candidate; HumanEval 7/7 completed top-1 and GFG 2/2 default; item 7 non-terminating |

Verified SHA-256 values for the two ten-pass Coq checkpoints and seen-replay
candidate are, respectively:

```text
3ffa312313271d4a6b082b9ccc7eaaea3a0b9a62bc3a676f1c4aa46ab7c199d0
4d6c503c106a5ca49a59045d6fafa54acec2a52cb69ad55b3aab193a45f93425
7fe07a11cb9358de1301c06f1d30dfddbe65f3eaf0151c8c8ec7728148380e81
```

The seen-replay candidate completed three passes at 09:15 UTC. Its
machine-readable log is
`tmp/joint23_E_seenreplay4_lr2e6_p3_20260823_metrics.jsonl`; its final
checkpoint is 4,279,182,147 bytes. Do not infer correctness from loss alone.

Later verified checkpoint hashes:

```text
Modeljoint23_replay_strong_lr1e5_p10_20260823            c9ecc8b2b6eb8d2622bbc1fd3c3f90bd75764e695dc83c0c5ce4523619a48f35
Modeljoint23_strong_hefocus_v15_lr5e6_p10_20260823       0c4d73c462768df68d9bedee8137fd61d4ea984e9c5d995cc50c923d079d05f9
Modeljoint23_heonly541_from_hefocus_lr5e6_p10_20260823   545d69e34d6e98baddfb9e361b0816749afb0c05f5bc4546e4886b258b884c4e
Modeljoint23_gfgrestore_from_heonly_lr2e6_p3_20260823    a3f99d4302cf56e4bd934ea0081fdc3c18d641fe5d2cf939942813f5aa8cfa14
Modeljoint23_dual_hegfg_from_heonly_lr2e6_p5_20260823    6740c1f15dfbc6fabcc55ceafa2f6d5624d9e3197336c1bcdc58acb6ae3e2791
```

## 8. Current new-experiment results

All cells are functional problem-level pass@1/pass@10 from ten ordered
candidates unless explicitly marked otherwise.

| benchmark | model | train pass@1 | train pass@10 | test pass@1 | test pass@10 |
|---|---|---:|---:|---:|---:|
| MBJP (608/67) | ordinary T5Gemma2 | 506/608 (83.22%) | 564/608 (92.76%) | 9/67 (13.43%) | 22/67 (32.84%) |
| MBJP (608/67) | **ProofT5 (ours)** | pending | pending | **17/67 (25.37%)** | **29/67 (43.28%)** |
| HumanEval-Java v15 (146/16) | ordinary T5Gemma2 | 145/146 (99.32%) | 145/146 (99.32%) | 2/16 (12.50%) | 4/16 (25.00%) |
| HumanEval-Java v15 (146/16) | **ProofT5 (ours)** | pending | pending | **8/16 (50.00%)** | **9/16 (56.25%)** |
| GFG v13 (414/103) | ordinary T5Gemma2 | 408/414 (98.55%) | 411/414 (99.28%) | 14/103 (13.59%) | 28/103 (27.18%) |
| GFG v13 (414/103) | **ProofT5 (ours)** | pending | pending | pending complete evaluation | pending complete evaluation |

Interpretation:

- MBJP has the desired ordinary T5Gemma2 -> ProofT5 trend.
- HumanEval-v15 also improves, but its 16-row result is ancestor-mixed; the
  lineage-unseen 11-row comparison must accompany it.
- Historical GFG-v14 ProofT5 was below ordinary. The revised GFG-v13
  ProofT5 row remains pending until all 103 problems are scored.
- CoqView is intentionally outside the current six-row scope.

Machine-readable evidence:

```text
tmp/clean_java_reproduction_final_20260811.json
tmp/v14_gfg_parent_safe_plain_lengthrepair_stage2_trainfull414_20260820_score_timeout10.json
tmp/v14_gfg_parent_safe_plain_lengthrepair_stage2_test103_20260820_score_timeout10.json
tmp/v14_gfg_parent_safe_coq_selected_test103_20260820_score_timeout10.json
```

The clean Java result report includes 95% Wilson intervals for all six
MBJP/HumanEval test rows:

```text
docs/experiments/CLEAN_JAVA_REPRODUCTION_RESULTS_20260811.md
```

### 8.1 Latest joint-route diagnostic evidence

The 2026-08-23 joint experiments were attempts to improve HumanEval and GFG
simultaneously. They have not produced a replacement formal result:

| candidate | HumanEval training probe | GFG training probe | decision |
|---|---:|---:|---|
| ordinary joint final | 5/8 pass@1, 5/8 pass@10 | 2/8 pass@1, 3/8 pass@10 | insufficient train fit |
| Coq HumanEval-parent final | 2/2, 2/2 | 0/2, 1/2 | reject |
| Coq GFG-parent final | 1/2, 1/2 | 2/2, 2/2 | reject |
| curriculum candidate E | 1/2, 2/2 | 2/2, 2/2 | best small probe, not a full gate |
| seen-replay final | 3/8, 3/8, final-only | 2/2, 2/2, default | weak HumanEval fit |
| strong replay, joint 10-pass | 4/7, 5/7, final-only; item 7 timeout | 4/7, 5/7, final-only partial | low loss did not ensure autoregressive correctness |
| MBJP+HumanEval focus | 5/7, 6/7, final-only; item 7 timeout | 1/2, 2/2, default | HumanEval improvement with incomplete GFG top-1 |
| HumanEval-only focus | 7/7 top-1 across completed beam-1 items; item 7 timeout | 1/2, 1/2, default | strong HE fit, GFG forgetting |
| GFG single-source restore | 6/7 top-1; item 7 timeout | 2/2, 2/2, default | GFG restored, HE item 5 forgotten |
| HumanEval+GFG dual rehearsal | 7/7 top-1; item 7 timeout | 2/2, 2/2, default | best joint diagnostic candidate; partial gate only |

The denominators above are deliberately explicit. Two-task and eight-task
fixed probes are routing diagnostics, not benchmark scores. Candidate E also
solved a previously seen HumanEval diagnostic item only at pass@10 (0/1 at
pass@1, 1/1 at pass@10), showing a ranking problem rather than evidence of a
stable gain. Changing length penalty to 0.5 did not improve its top-1 result.

Evidence is under `tmp/` with prefixes `java_joint23_` and `joint23_`. Several
evaluation wrappers intentionally exited nonzero after evaluating requested
indices because their aggregate scorer expected the other missing rows. Use
the partial JSON's solved IDs and explicit evaluated-index denominator; never
quote the wrapper's nominal full denominator for these probes.

The completed ordinary HumanEval evidence is:
`tmp/formal_train_he65_plain_retrytok_20260823_score_timeout10.json` records
49/65 pass@1 and 55/65 pass@10 with all 65 outputs present. Its checkpoint
manifest hash exactly matches the frozen ordinary checkpoint. This is a full
training-set score, not a probe.

The completed Coq HumanEval evidence is
`tmp/formal_train_he65_coq_merged_20260823_score_timeout10.json`: it records
55/65 pass@1 and 60/65 pass@10, all 650 candidates, 28 compilation failures,
four timeouts, and no missing outputs. The strict source merge is recorded in
`Utils/output/humaneval_clean65_train_eval_t5gemma2_20260823_test_ans/formal_train_he65_coq_merged_20260823/merge_manifest.json`.
The score-artifact SHA-256 is
`9f4480780656c2ae35675b0090927e9c2392bd85d81539e91246f96097fcb7f0`;
the merge-manifest SHA-256 is
`9f00f79e53aa0413a1a6ad6c44d1e7780bc67a3dbded1c8fee4ec8b57e459a83`.

MBJP evidence is
`tmp/formal_train_mbjp608_plain_retrytok_20260823_score_timeout10.json`: it
records 506/608 pass@1 and 564/608 pass@10, all 6,080 candidates, 1,561
compilation failures, 16 timeouts, no missing outputs, and the same frozen
checkpoint manifest SHA-256. Its score-artifact SHA-256 is
`2bdba990c595762671d71a63fa99d71cef1453c9a71ecddc4b4d07ddbffaae24`.

Decoder labels are part of the result. `final-only` disables prefix proof
checking and is a diagnostic decoder distinct from the formal default Coq
decoder. Beam-1 results report only top-1 and cannot be substituted for
pass@10. HumanEval probe item 7 (`CheckDictCase`, gold proof length about 295
tokens) failed to terminate even with beam 1 and a 400-token generation cap;
this is a termination/exposure-bias failure, not a missing score file.

Key later score artifacts:

```text
tmp/joint23_strong_hefocus_heprobe7of8_finalonly_20260823.json
tmp/joint23_heonly541_heprobe6of8_finalonly_20260823.json
tmp/joint23_heonly541_hehard6_beam1_finalonly_20260823.json
tmp/joint23_gfgrestore_heprobe7of8_beam1_finalonly_20260823.json
tmp/joint23_gfgrestore_gfgprobe01_default_20260823_score_timeout10.json
tmp/joint23_dual_hegfg_heprobe7of8_beam1_finalonly_20260823.json
tmp/joint23_dual_hegfg_gfgprobe01_default_20260823_score_timeout10.json
```

## 9. Historical Major Revision issue board (see Section 0 for current status)

High-level completion snapshot:

| workstream | status |
|---|---|
| clean MBJP/HumanEval data, checkpoint freeze, and full test evaluation | done evidence |
| GFG v14 data audit and ordinary/Coq test evaluation | done evidence, result is negative for Coq |
| clean MBJP/HumanEval Wilson intervals | done evidence |
| full train cells in the requested six-row table | ordinary rows complete; ProofT5 MBJP, HumanEval-v15, and GFG-v13 train evaluations pending |
| 2026-08-23 joint/replay/curriculum attempt | frozen dual HumanEval+GFG ProofT5 checkpoint selected before strict evaluation; HumanEval-v15 is complete but ancestor-mixed, and GFG-v13 strict-103 is active |
| reviewer-ready failure/scalability/cost analyses | partial/open |
| modern decoder-only, SynCode/Copiloting, iterative refinement baselines | open |
| theoretical/limitations revisions | open |
| LaTeX integration and Major Revision response letter | open; current paper tree unchanged |

Status meanings:

- **done evidence**: implementation/result exists and is auditable;
- **partial**: useful evidence exists, but it does not fully answer the review
  or is not yet incorporated into the manuscript;
- **open**: no adequate answer/result exists;
- **paper-open**: technical work may exist, but the paper/response is unchanged.

| issue | reviewer concern | status | present evidence | required completion |
|---|---|---|---|---|
| AE-1 | Missing failure analysis | partial | v13-v15 reports analyze length, prompt/style mismatch, train fit, compilation failures, timeouts, proof pruning, and generalization | Produce a concise taxonomy with representative MBJP/SuFu/new-Java failures and counts; add to evaluation/threats |
| AE-2 / R1 / R2 | Limited benchmarks and small tests | partial | HumanEval-Java and GFG normalized, audited, split, trained and tested | Decide reportable extension. HumanEval remains low; GFG Coq is negative. Reconcile split/count protocol and finish table cells |
| R1 / R2 | Confidence intervals/statistical reliability | partial | Wilson 95% intervals exist for six clean MBJP/HumanEval rows | Add intervals for final paper rows, define statistical unit, consider paired significance or bootstrap; manuscript currently has none |
| R1 | Java subset selection bias | partial | parent-safe and signature-overlap audits, clean train/test separation | Explain original subset construction, reconcile 608-versus-675 count, and document exclusions/coverage in paper |
| R1 / R3 | Marginal Java improvement | partial | clean MBJP Coq/CoqView trend is stronger; HumanEval/GFG expose generalization limits | Present honest mechanism/failure explanation; do not cherry-pick a favorable split |
| AE-3 / R1 / R2 | Scalability to richer/longer programs | partial | sequence-bound audits and long-GFG diagnosis exist | Add measured scaling versus target length/tree depth and discuss subtyping, polymorphism, overloads, mutation, ownership |
| R1 | First-order versus higher-order unification boundary | open | submitted methods mention first-order restriction | State excluded type systems, failure behavior, and possible approximation/extension; revise theory/limitations |
| R1 | Completeness does not bound search/beam recovery | partial | decoder stopping, timeout and missing-output handling are now correct | Measure beam exhaustion/recovery and discuss that logical completeness is not search completeness |
| R1 / R2 | Token pruning rate and beam exhaustion/fallback | open | scorers record missing candidates/timeouts; code can distinguish unfinished beams | Instrument and report pruning fraction by stage/step, exhausted tasks, and exact fallback policy |
| AE-4 / R1 / R2 / R3 | Modern decoder-only and >2B model comparison | open | T5Gemma2-2B is already in submitted paper, but is still encoder-decoder and not >2B | Select modern open/proprietary decoder-only baselines and run zero/few-shot or fine-tuned comparison on exactly the same tasks/tests |
| AE-5 / R3 | SynCode and Copiloting the Copilots | open | SynCode is cited in related work only; paper claims rejection sampling is functionally equivalent, which reviewers reject as insufficient | Implement/run comparable token-level constrained decoding or narrow the claim and provide a rigorous non-equivalence-aware comparison |
| R3 | Iterative refinement with type-error feedback | open | no experiment | Define a fair call/token budget and compare an iterative repair baseline |
| AE-6 / R2 / R3 | Runtime and system cost | open | submitted RQ4 reports average output tokens; code contains performance fixes but no clean wall-clock comparison | Measure end-to-end latency, LM calls/decoder steps, Coq/type-check calls, GPU/CPU time, and candidate cost under matched settings |
| R2 | CHC/arbitrary-constraint claim exceeds evidence | open | current intro/conclusion make broad claims | Either add a richer-constraint case study or narrow claims to type correctness and mark broader CHC use as future work |
| R3 | Dynamically typed languages such as Python | open | no current paper discussion | Add threat/limitation: what static specification would replace the type system and what guarantees would be unavailable |
| all | Integrate revisions and prepare response letter | paper-open | new experiment documents exist outside `tosem/paper` | Revise LaTeX, regenerate PDF, and replace original cover letter with a point-by-point Major Revision response |

No issue should be marked answered merely because a script exists. Every
paper-facing claim needs a complete result artifact and a specific manuscript
edit.

## 10. Historical remaining-work plan (superseded by Section 0)

### Priority 0: fill the six-row ProofT5 table without CoqView

Three result groups remain:

1. MBJP 608: ProofT5 full train evaluation.
2. HumanEval-v15 146: revised ProofT5 full train evaluation.
3. GFG-v13: revised ProofT5 full train-414 and strict test-103 evaluations.

Use ten candidates and report pass@1/pass@10. Do not substitute historical
pass@8 data, probes, partial shards, or the old GFG-v14 result. These jobs use
already-frozen checkpoints. Do not schedule further CoqView work.

Historical HumanEval-65, GFG-v14, and CoqView partial outputs are preserved
for provenance but are no longer prerequisites for the paper-facing table.
Do not restart their old orchestration chain.

The seen-replay and later curriculum checkpoints received their prespecified
training-side probes. The resulting frozen joint checkpoint is
`Modeljoint23_dual_hegfg_from_heonly_lr2e6_p5_20260823`; its complete v15
split evaluation is 8/16 pass@1 and 9/16 pass@10. Because five rows were seen
by its clean-673 ancestor, report that full-16 result as **ancestor-mixed**.
The matched lineage-unseen 11-row comparison is ordinary 1/11 and 3/11 versus
Coq 4/11 and 5/11. Do not use either result to select another checkpoint, and
do not call the full-16 result strictly lineage-held-out.

### Priority 1: turn existing diagnostics into reviewer-facing analyses

1. Compute/report confidence intervals for every final table row.
2. Build a failure taxonomy from score JSONs and representative candidates.
3. Instrument pruning, beam exhaustion, Coq checks, decoder steps, and
   wall-clock/CPU/GPU cost on frozen checkpoints.
4. Resolve the MBJP count/split discrepancy and describe the exact sampling
   unit and overlap policy.
5. Decide whether GFG is presented as a negative/limitation result or omitted
   from the main improvement claim. It cannot currently support a gain claim.

### Priority 2: genuinely missing reviewer baselines

These require a new experimental design and should not be improvised from old
outputs:

1. modern decoder-only and preferably >2B model;
2. SynCode/token-level constrained decoding;
3. Copiloting the Copilots or the closest reproducible equivalent;
4. iterative type-error-feedback refinement.

For fairness, freeze the prompts/tests and predeclare call, token, beam, and
time budgets before inspecting results.

### Priority 3: theory and manuscript revision

1. Narrow or substantiate CHC generality.
2. Explain first-order unification and excluded systems.
3. Separate logical completeness from practical beam-search success.
4. Discuss subtyping, polymorphism, overloads, mutation, ownership, and
   dynamically typed languages.
5. Update evaluation, threats to validity, related work, conclusion, abstract,
   and claims consistently.
6. Create a point-by-point Major Revision cover letter mapping every reviewer
   issue to exact revised pages/sections and evidence.

## 11. Reporting and scientific-integrity rules

Do not:

- use test performance to select a checkpoint;
- describe the 66-row seen/unseen HumanEval diagnostic as held out;
- describe GFG Coq as an improvement over ordinary;
- describe an 8/8 fixed probe as the full GFG training result;
- mix pass@8 and pass@10 in the same table without explicit labels;
- report pass@1/pass@10 without integer numerator and denominator;
- infer paper values from rounded percentages when the integer count is
  impossible or ambiguous;
- claim that token-level constrained decoding has been experimentally answered
  by rejection sampling alone;
- claim all Major Revision items are complete before the paper and cover letter
  contain the changes;
- modify `Utils/score_output/results_final.csv` or submitted paper tables
  without a traceable replacement artifact;
- restore or cite checkpoint paths deleted in the cleanup manifest.

The original paper's Java TyFlow-2B pass@1 value 23.19% is not an exact integer
count over 67 tasks; the clean report already flags this. Reconcile the
original denominator/raw result before resubmission.

## 12. Git and cleanup state

At the 21:39 UTC recheck:

- 15 tracked files are modified, representing required code/tests/docs work;
- 39 untracked Git status entries exist (many are directories containing
  multiple retained files), primarily scripts, tests, selected-data
  manifests, ordinary-model JSONs, and the new documentation;
- `tosem/` has no Git diff;
- tests pass;
- no commit or staging was performed.

Do not run `git reset --hard`, `git checkout --`, or `git clean`. Review and
commit the maintained changes in logical groups only after deciding how large
generated data should be versioned.

Cleanup performed on 2026-08-23:

- 318 obsolete model directories removed;
- approximately 4.651 TB released;
- old SuFu CoqView diagnostics, Java v4-v12 routes, and abandoned SuFu
  expansion checkpoints removed;
- canonical original SuFu and current Java checkpoints preserved;
- duplicate intermediate reports and one-off scripts removed.

Exact destructive record:

```text
docs/CHECKPOINT_CLEANUP_MANIFEST_20260823.md
```

Deleted checkpoints are not recoverable from Git and would require an external
backup or retraining.

## 13. Recommended first actions for the next session

1. Read this document completely.
2. Read `tosem/review_decision_2026-06-16.txt` completely.
3. Read `docs/JAVA_BENCHMARK_EXPERIMENT_MASTER_20260823.md` and
   `MODEL_TRAINING_INVENTORY.md`.
4. Run `git status --short` and `git diff --check`; run the full test command
   before committing (the last complete suite had 69 passing tests).
5. Check `nvidia-smi`, process owners, and the active evaluation tags in
   Section 5.1; do not duplicate or interrupt surviving jobs.
6. Verify the five current Java checkpoint paths before any evaluation.
7. Verify the frozen dual-rehearsal checkpoint hash and preserve its completed
   full-16 and lineage-unseen-11 HumanEval results. Do not use them to choose a
   replacement checkpoint; label every final-only/beam-1 result diagnostic
   and the full-16 result ancestor-mixed.
8. Preserve the completed HumanEval-v15 strict-16 result and finish the active
   ProofT5 GFG-v13 strict-103 evaluation. Then evaluate ProofT5 on the MBJP,
   HumanEval-v15, and GFG-v13 training splits. Do not schedule CoqView work.
9. Produce a reviewer-evidence table for CI, failures, pruning/exhaustion, and
   cost using frozen outputs.
10. Ask the author to approve the exact modern LLM, SynCode/Copiloting, and
   iterative-refinement protocols before expensive new runs.
11. Only after evidence is frozen, revise `tosem/paper` and write the
   point-by-point Major Revision cover letter.

## 14. Compact prompt for a new session

The user may begin a new session with:

> Work in `/data2/x/hzc/prooft5`. Read
> `docs/SESSION_HANDOFF_MAJOR_REVISION_20260823.md` completely, then read every
> source-of-truth file it marks as required for the task you are about to do.
> Preserve the dirty worktree and all frozen checkpoints/results. Do not use
> test results for checkpoint selection, do not create validation for the
> current extension routes, and do not touch other users' GPU processes.
> Continue from the handoff's Major Revision issue board and report evidence,
> missing work, and manuscript changes separately.

## 15. Key links

- Experiment master: `docs/JAVA_BENCHMARK_EXPERIMENT_MASTER_20260823.md`
- Documentation index: `docs/README.md`
- Model lineage: `MODEL_TRAINING_INVENTORY.md`
- Project structure: `PROJECT_STRUCTURE.md`
- Cleanup manifest: `docs/CHECKPOINT_CLEANUP_MANIFEST_20260823.md`
- Clean Java reproduction: `docs/experiments/CLEAN_JAVA_REPRODUCTION_RESULTS_20260811.md`
- GFG/HumanEval retained reports: `docs/experiments/`
- HumanEval-v15 lineage-overlap audit:
  `docs/audits/JAVA_HUMANEVAL_V15_ANCESTOR_OVERLAP_AUDIT_20260823.json`
- Three-source MBJP-style audit:
  `docs/audits/JAVA_THREE_SOURCE_MBJP_STYLE_ALIGNMENT_AUDIT_20260823.json`
- Decision/reviews: `tosem/review_decision_2026-06-16.txt`
- Paper source: `tosem/paper/manuscript.tex`
- Current PDF: `tosem/paper/manuscript.pdf`
