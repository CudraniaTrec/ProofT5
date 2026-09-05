# ProofT5 Project Structure

Last updated: 2026-09-05

This note records the current local structure of `/data2/x/hzc/prooft5`.
It is meant as a memory aid for future work, especially because several
important runtime assets are intentionally ignored by git.

## Top-Level Map

```text
/data2/x/hzc/prooft5
├── run.py                    # Main ProofT5 training/evaluation entrypoint
├── Model.py                  # CodeT5-based model definitions
├── ModelT5Gemma2.py          # T5Gemma2 ProofT5 model adaptations
├── Dataset.py                # Dataset loading and collation
├── beamsearch*.py            # Decoding implementations for Java, Coq, DSL, SuFu
├── get_tokenizer.py          # Tokenizer helper
├── trans_dsl_program.py      # DSL-to-executable-program helper
├── run.sh / run_overall.sh   # Shell wrappers for experiments
├── acc_config.yaml           # Accelerate config
├── requirements.txt          # Historical Python requirements
├── requirements-t5gemma2.txt # T5Gemma2 environment overlay
├── artifacts/                # Frozen paper-facing result packages and hashes
├── baselines/                # Reproducible Java baseline adapters and lock file
├── docs/                     # Canonical experiment ledger, audits, retained reports
├── Utils/                    # Data, checkpoints, outputs, scoring, parsers
├── coq_model/                # Java/Coq modeling, proof generation, mxeval
├── SuFu/                     # SuFu benchmarks, parser, model helpers, ignored source trees
├── t5_llm/                   # CodeT5 / T5Gemma2 baseline scripts and outputs
├── tests/                    # Script-style regression tests
├── third_party/              # Gitignored upstream checkouts restored from lock file
├── tosem/                    # TOSEM paper and submission material
└── tmp/                      # Ignored runtime scratch data, logs, and backups
```

Paper-facing Java experiment status is frozen in
`docs/MAJOR_REVISION_FINAL_PACKAGE_20260824.md`. The machine-readable package
under `artifacts/major_revision_20260824/` records exact dataset, checkpoint,
score, and complete candidate-output paths and their hashes. The compact table
also remains in `docs/JAVA_BENCHMARK_EXPERIMENT_MASTER_20260823.md`.

For current experiment numbers, start from the frozen 2026-08-24 package. For
broader paper, reviewer, code, and historical context, continue with
`docs/SESSION_HANDOFF_MAJOR_REVISION_20260823.md`; its older experiment status
must not override the frozen package.

External SynCode, Repilot, LLMLOOP, and modified Eclipse JDT repositories are
not vendored. Their URLs and exact commits are recorded in
`baselines/java_baselines/UPSTREAM_LOCK.json`; run
`python3 baselines/java_baselines/fetch_upstreams.py` to reconstruct the
gitignored `third_party/baselines/` tree.

There is no `paper/ase2026` directory in this checkout at the time of writing.
The visible manuscript directory here is `tosem/paper`.

Current revision supplement:

artifacts/major_revision_evaluation_20260905/
  rq2_runtime_2b/                 # 2B SuFu runtime records
  java_statistics_combined.json   # merged Java statistical results

The submission-facing response draft and author modification table are
revision_response_letter.md and major_revision_modification_table.md.

## Main ProofT5 Code

The core ProofT5 path is rooted at the repository top level.

Key files:

```text
run.py
Model.py
ModelT5Gemma2.py
Dataset.py
beamsearch.py
beamsearch_coq.py
beamsearch_dsl.py
beamsearch_sufu.py
beamsearch_sufu_cd.py
beamsearch_cache.py
```

`run.py` supports both the historical CodeT5 path and the T5Gemma2 path. It reads task-specific config from `Utils/data/<task>/config.json`, loads
rules from `Utils/data/<task>/rules.pkl`, and writes generated outputs under
`Utils/output/<task>_test_ans/...`.

Important constrained-decoding task families:

```text
mbjpcoq
mbjpcoqview
sufucoq
sufucoqview
```

Known vocabulary alignment:

```text
mbjpcoq      runtime rules: 32216
mbjpcoqview  runtime rules: 32216
sufucoq      runtime rules: 32302
sufucoqview  runtime rules: 32302
```

`sufucoqview/rules.pkl` contains four extra CodeT5-style tags:

```text
<code>
</code>
<proof>
</proof>
```

Those extra tags are not used by the old ProofT5 constrained-decoding checkpoint.
The runtime rule loader trims by task `config.json` when `rulenum` is explicitly
set.

T5Gemma2 data preparation utilities:

```text
prepare_t5gemma2_retokenized_prooft5_data.py
prepare_t5gemma2_java_coqview_promptprefix.py
prepare_t5gemma2_sufu_coqview_ctxfix.py
```

The generic early conversion script is superseded and ignored; use the three
task-specific scripts above so training tokens stay aligned with the fixed merged
vocabulary.

## Utils

`Utils/` is the main storage and utility directory.

```text
Utils/
├── data/             # Processed train/valid/test data and task configs
├── models/           # HuggingFace models and ProofT5 checkpoints, gitignored
├── output/           # Generated candidate programs, gitignored
├── processdata/      # Java tree-sitter processing and rule serialization
├── tree_sitter_dsl/  # DSL tree-sitter grammar/parser helpers
├── evaluator/        # CodeBLEU and evaluation helpers
└── score_output/     # Java/SuFu scoring scripts and result CSVs
```

Important `Utils/data` task directories include:

```text
mbjp, mbjp_blind, mbjp_dsl
mbjpcoq, mbjpcoqview, mbjpcoqview2
sufucoq, sufucoqview
codet5-base_mbjp, codet5-base_sufu
codet5-base_mbjp_codeproof, codet5-base_mbjp_proofcode
codet5-base_sufu_codeproof, codet5-base_sufu_proofcode
codet5p-220m_mbjp, codet5p-220m_sufu
codet5p-770m_mbjp, codet5p-770m_sufu
Qwen2.5-0.5B_sufu
```

Important `Utils/models` entries include:

```text
Modelpretrain/
Modelmbjpcoq/
Modelmbjpcoqview/
Modelsufucoq/
Modelsufucoqview/
codet5-small/
codet5p-770m/
codet5p-2b/
t5gemma-2-1b-1b/
```

Known checkpoint directories:

```text
Utils/models/Modelmbjpcoq/2025-06-11_11-41-16
Utils/models/Modelmbjpcoqview/2025-06-20_16-57-57
Utils/models/Modelsufucoq/2025-06-07_21-03-51
Utils/models/Modelsufucoqview/2025-06-19_20-01-51
```

Important scoring files:

```text
Utils/score_output/test-java-output.py
Utils/score_output/test-sufu-output.py
Utils/score_output/result.csv
Utils/score_output/results_final.csv
Utils/score_output/compile_error_list.json  # generated and gitignored
```

Do not casually modify:

```text
Utils/score_output/results_final.csv
tosem/paper tables and result text
```

## coq_model

`coq_model/` contains the Java-to-Coq/proof side of the project.

```text
coq_model/
├── program_model.py          # Python-side modeling and serialization of proofs/programs
├── java2impp.py              # Java-to-DSL conversion and checks
├── prepare_data.py           # Coq proof sequence data generation
├── prepare_pretrain_data.py  # Pretraining data preparation
├── coq_code/                 # Coq source files
├── datas/                    # MBJP/HumanEval data and CoqView variants
├── mxeval/                   # Java execution/evaluation package
└── myjavalang/               # Java parser support
```

The local editable `mxeval` package is installed into the uv environment from:

```text
/data2/x/hzc/prooft5/coq_model/mxeval
```

Coq-related PATH currently relies on:

```bash
export PATH=/home/zchuang/.opam/with-coq-8.20.1/bin:/home/zchuang/.opam/default/bin:$PATH
```

## SuFu

`SuFu/` has three different roles:

```text
SuFu/
├── benchmark/            # Tracked SuFu benchmark corpus used by this project
├── label/                # SuFu labels
├── sufu_model.py         # Python model/parser/type-check helpers
├── tree-sitter-sufu/     # Python/tree-sitter package for SuFu syntax
├── SuFu/                 # Ignored local SuFu C++/OCaml source tree
└── SuFu_origin/          # Ignored upstream-style SuFu source tree and thirdparty deps
```

The ProofT5 scoring path primarily uses the OCaml surface parser:

```text
SuFu/SuFu/surface/f
```

Build the surface parser:

```bash
cd /data2/x/hzc/prooft5/SuFu/SuFu/surface
export PATH=/home/zchuang/.opam/with-coq-8.20.1/bin:/home/zchuang/.opam/default/bin:$PATH
make
```

Run the surface parser:

```bash
cd /data2/x/hzc/prooft5
./SuFu/SuFu/surface/f SuFu/SuFu/test.f tmp/test.json
```

The full SuFu C++ synthesizer has also been built locally.

User-local dependencies:

```text
/data2/x/hzc/.local/sufu-deps
```

Build directories outside the repo:

```text
/data2/x/hzc/.local/sufu-builds/prooft5-current
/data2/x/hzc/.local/sufu-builds/prooft5-origin
/data2/x/hzc/.local/sufu-builds/prooft5-origin-verified
```

The verified full SuFu executable is:

```text
/data2/x/hzc/.local/sufu-builds/prooft5-origin-verified/executor/run
```

It has an embedded runtime search path. The equivalent explicit library path is:

```bash
export LD_LIBRARY_PATH=/data2/x/hzc/.local/sufu-deps/lib:/data2/x/hzc/prooft5/SuFu/SuFu_origin/thirdparty/z3-z3-4.13.0/build:/data2/x/hzc/prooft5/SuFu/SuFu_origin/thirdparty/gurobi912/linux64/lib:$LD_LIBRARY_PATH
```

Verified minimal full-SuFu run:

```bash
/data2/x/hzc/.local/sufu-builds/prooft5-origin-verified/executor/run \
  --benchmark=SuFu/SuFu_origin/benchmark/autolifter/single-pass/sum.f \
  --output=/data2/x/hzc/.local/sufu-builds/run-test/res.f \
  --use_gurobi=false
```

Expected tail:

```text
Success
```

Build this target with an empty `CMAKE_BUILD_TYPE`, as done by
`scripts/build_language_runtimes.sh`. The source already forces `-Ofast`;
adding the `Release` flags and `-DNDEBUG` produced a stage-2 segmentation fault
on the `sum.f` smoke test.

Important: `SuFu/SuFu` and `SuFu/SuFu_origin` are ignored by git. Local fixes to
their CMake/config files are active on this machine but will not be committed
unless explicitly force-added or the ignore rules are changed.

## t5_llm

`t5_llm/` contains CodeT5, T5Gemma2, and other LLM baseline scripts.

```text
t5_llm/
├── finetune_codet5.py    # CodeT5 finetuning entrypoint
├── finetune_t5gemma2.py  # T5Gemma2 baseline finetuning entrypoint
├── codet5_output.py      # CodeT5 generation/output script
├── finetune_qwen.py      # Qwen finetuning script
├── gen_ans.py            # Answer generation helper
├── data/                 # LLM baseline data
├── models/               # Baseline model checkpoints, gitignored
├── outputs/              # Baseline generated outputs, gitignored
└── results/              # Baseline result artifacts
```

CodeT5 baseline outputs also appear under `Utils/output/codet5*`.

## Paper And Submission Material

Current visible manuscript path:

```text
tosem/paper/
├── manuscript.tex
├── manuscript.pdf
├── macros.tex
├── acmart.bib
├── bibtex.bib
├── chapters/
├── assets/
└── material/
```

Other TOSEM material:

```text
tosem/cover_letter.pdf
tosem/review_decision_2026-06-16.txt
```

Again, this checkout currently does not contain `paper/ase2026`.

## Runtime Environment

Python uv environments:

```text
/data2/x/hzc/.uv-envs/prooft5-py313
/data2/x/hzc/.uv-envs/prooft5-t5gemma-py313
```

Activate:

```bash
source /data2/x/hzc/.uv-envs/prooft5-t5gemma-py313/bin/activate
```

Useful PATH:

```bash
export PATH=/data2/x/hzc/.local/jdks/temurin17/bin:/home/zchuang/.opam/with-coq-8.20.1/bin:/home/zchuang/.opam/default/bin:$PATH
```

JDK:

```text
/data2/x/hzc/.local/jdks/temurin17
```

User-level `java` and `javac` links in `/home/zchuang/.local/bin` point to this
JDK, so both the legacy PATH-based scorers and the configurable scorers use
Java 17.

Portable scoring overrides:

```bash
export PROOFT5_JAVA_HOME=/path/to/jdk
export PROOFT5_JAVA=/path/to/java
export PROOFT5_JAVAC=/path/to/javac
export PROOFT5_SUFU_PARSER=/path/to/SuFu/surface/f
```

SuFu C++ dependencies:

```text
/data2/x/hzc/.local/sufu-deps
/data2/x/hzc/.local/src/sufu-deps
```

The language environments can be loaded and checked without writing into the
repository:

```bash
source scripts/runtime_env.sh
scripts/check_language_runtimes.sh
```

To rebuild Coq, the SuFu surface parser, and the full SuFu synthesizer:

```bash
scripts/build_language_runtimes.sh
```

## Common Commands

The versioned external Java and synthetic SuFu dataset expansion is documented
in `DATASET_EXPANSION_20260730.md`. It currently includes HumanEval, McEval,
NaturalCodeBench, and a mechanically translated 1,581-row MXEval MathQA Java
set, plus two SuFu suites. Its generated task directories under `Utils/data/`
are ignored, while the reproducible builders are:

```text
scripts/build_java_external_datasets.py
scripts/build_sufu_synthetic_dataset.py
scripts/audit_expanded_dataset_roundtrip.py
```

ProofT5 checkpoint/eval example:

```bash
source /data2/x/hzc/.uv-envs/prooft5-py313/bin/activate
export PATH=/data2/x/hzc/.local/jdks/temurin17/bin:/home/zchuang/.opam/with-coq-8.20.1/bin:/home/zchuang/.opam/default/bin:$PATH

accelerate launch --config_file ./acc_config.yaml --num_processes=1 run.py \
  --task sufucoqview \
  --eval \
  --train_time 2025-06-19_20-01-51 \
  --checkpoint_epoch 100
```

Java scoring example:

```bash
python Utils/score_output/test-java-output.py \
  --task codet5-base_mbjp \
  --train_time 2025-07-02_15-48-24 \
  --checkpoint_epoch 50
```

SuFu scoring example:

```bash
export PATH=/home/zchuang/.opam/with-coq-8.20.1/bin:/home/zchuang/.opam/default/bin:$PATH
python Utils/score_output/test-sufu-output.py \
  --task codet5-base_sufu \
  --train_time 2025-06-29_23-21-14 \
  --checkpoint_epoch 160
```

## Git Ignore And Preservation Notes

The following are ignored or mostly runtime/generated:

```text
Utils/models/*
Utils/output/*
Utils/data/*/
Utils/score_output/forjava/*
SuFu/SuFu
SuFu/SuFu_origin
t5_llm/models/
t5_llm/outputs/
/tmp/
/Utils/tensorboard/
/coq_model/mxeval/mxeval/java_exec_eval/
**/target/
*.aux, *.glob, *.vo, *.vok, *.vos, *.class
**/__pycache__/
```

Therefore, many important local assets are not protected by normal git commits:

```text
trained checkpoints
downloaded HuggingFace models
generated candidate outputs
SuFu C++ source/build changes under ignored directories
runtime split datasets, logs, and backups in tmp/
```

Before cleaning or moving files, check these paths carefully. In particular,
do not delete or overwrite existing experiment outputs unless explicitly intended.
