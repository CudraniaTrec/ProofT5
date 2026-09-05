# Revision Response Letter

Manuscript: *TyFlow: A Type-Aware Approach to Neural Code Models*
Manuscript ID: TOSEM-2026-0076

Dear Editor and Reviewers,

Thank you for the detailed and constructive comments. We have prepared a
revised evaluation package and a focused set of manuscript changes. The
Evaluation section now includes two additional Java benchmarks, a task-level
failure analysis, runtime measurements on SuFu, pruning and beam-exhaustion
statistics, comparisons with larger decoder-only models, and comparisons with
SynCode, Repilot, rejection sampling, and iterative compiler repair. The
Appendix reports the combined Java statistical analysis and the SuFu
confidence intervals.

The remaining wording changes outside Evaluation and Appendix are listed
separately in major_revision_modification_table.md for author confirmation
before submission. Section and page references should be updated after those
manual edits are finalized.

## Response to the Editor's meta-review

### Missing failure analysis

We added a task-level failure taxonomy and representative examples in
Appendix C. The taxonomy separates top-1 success, ranking failure, all-invalid
generation, and well-typed but functionally incorrect programs. It shows that
the remaining TyFlow failures are primarily semantic rather than type errors.

### Limited evaluation benchmarks

We added HumanEval-Java and TransCoder-GFG, both normalized to the existing
Java task format. The benchmark-specific results remain in the main RQ1 table,
and the Appendix reports the combined Java analysis over 186 paired tasks.

### Missing discussion on scalability

RQ2 now reports pruning statistics and 2B SuFu inference time for the
no-check, syntactic-pruning, type-pruning, and dynamic-context configurations.
The text also states the observed beam-exhaustion result and the fail-closed
behavior when the fixed generation budget produces fewer than ten completed
candidates. We additionally explain qualitatively how synthesis-tree depth,
decision-sequence length, and branching increase the decoding and checking work
as programs become more complex.

### Missing comparison with larger and more recent LLMs

We added pass@1 results for MiMo-7B, Qwen3-14B, and Qwen3-30B-A3B on MBJP,
HumanEval-Java, TransCoder-GFG, and SuFu. Zero-shot and few-shot conditions
are reported separately, with the prompt protocol stated in the table note.

### Missing comparison with state-of-the-art techniques

RQ3 now includes SynCode, Repilot, rejection sampling, and iterative compiler
repair under the aligned Java comparison protocol. The table reports
functional correctness and compilation-error rate, and the accompanying text
states the protocol differences between these methods.

### Missing analysis of system cost

The RQ2 text reports the measured 2B SuFu runtime for each component
configuration. This keeps the system-cost analysis with the component
ablation to which it belongs.

## Response to Reviewer 1

### Statistical reliability of the small test sets

We added Appendix D. MBJP, HumanEval-Java, and TransCoder-GFG are analyzed as
186 paired Java tasks. For pass@1 and pass@10, the Appendix reports 95%
Wilson intervals and exact two-sided paired McNemar tests. It also reports the
corresponding intervals and paired tests for FSP and CER. For SuFu, the
Appendix reports 95% Wilson intervals for the reported task-level pass rates
and candidate-level compilation-error rates over all 58 tasks. HumanEval-
Java's 16-task result remains visible in the benchmark-specific table; the
merged analysis prevents that small set from being the sole basis for the
statistical conclusion.

### Java pass@1 improvement

The revised Evaluation reports the benchmark-specific Java results and the
failure taxonomy. It now briefly explains that the type constraints primarily
remove uncompilable candidates, while semantic errors can still affect the
top-ranked candidate; the Java-subset scope is stated separately.

### Modern decoder-only models

The new decoder-only table reports three larger open-weight models on all four
benchmarks. Each cell identifies the zero-shot and few-shot task counts
separately, so the results are not combined across prompt conditions.

### First-order unification and richer type systems

We agree that the current formal and empirical evidence is limited to the
implemented first-order setting. A targeted scope and limitation paragraph
covering higher-order unification, polymorphism, subtyping, overloading, and
mutable-state-related features is listed for insertion in the relevant
non-Evaluation sections.

### Branching factor and pruning

RQ2 now reports the observed syntactic and type-pruning rates on the SuFu
test set, together with the number of tasks that dead-end under constrained
beam search. The Appendix and the surrounding text distinguish logical
existence of a derivation from completion under a finite beam budget.

### Remaining failures

Appendix C provides both aggregate failure counts and representative
compilation-invalid and well-typed-but-wrong examples. The analysis makes
clear which failures are addressed by type constraints and which remain
semantic.

## Response to Reviewer 2

### W1: Benchmarks and statistical analysis

We added two Java benchmarks and Appendix D's combined 186-task analysis with
95% intervals and paired tests for the four reported metrics. We also add
95% intervals for the submitted SuFu task and candidate proportions. The
original benchmark-specific results are retained in RQ1.

### W2: Runtime overhead, richer types, beam exhaustion, and fallback

RQ2 reports the measured 2B SuFu runtime for each component configuration. The
same section reports zero strict beam dead-ends in the instrumented 58-task
run. The decoder does not switch to unconstrained generation; incomplete
candidate slots at the fixed budget are scored fail-closed. The discussion of
richer type features is listed as a focused manual limitation edit.

### W3: Decoder-only comparison and adaptation

We added the four-benchmark decoder-only comparison for MiMo-7B, Qwen3-14B,
and Qwen3-30B-A3B. The architectural adaptation discussion remains a
limitation in the Evaluation section: TyFlow currently obtains its dynamic
type context by re-encoding the evolving synthesis goal in an encoder-decoder
architecture. A pure decoder-only adaptation would require a different
representation and would not preserve that mechanism in its current form.

### W4: Scope of the CHC generality claim

The empirical claim is supported by the two evaluated languages and the
additional Java benchmarks. The requested narrowing of the CHC/generalization
wording and the explicit boundary around richer constraints are listed for
manual insertion in the introduction, related-work, and conclusion text.

## Response to Reviewer 3

### SynCode, Copiloting the Copilots, and iterative refinement

RQ3 reports SynCode, Repilot (the Copiloting the Copilots comparison), and
iterative compiler repair alongside rejection sampling and TyFlow. The
iterative row reports both functional correctness and compilation-error rate;
the text records that compiler repair improves compilability without adding a
solved MBJP task in the controlled run.

### Larger models

The new decoder-only table provides comparisons with models larger than 2B on
the same four benchmark families. Their prompt-based protocol is kept
separate from the trained encoder-decoder TyFlow results.

### Java performance and failure behavior

The revised Java results are retained for all three Java benchmarks. Appendix
C identifies the dominant residual failure mode as well-typed but
functionally incorrect code and gives representative examples.

### Computational cost

Measured TyFlow component runtime is reported in RQ2 on the 58 SuFu tasks.
External-method cost details remain in the method-specific RQ3 discussion; we
do not merge heterogeneous cost accounting into a second cross-method cost
table.

### Dynamic languages and Python

The Evaluation section now states as a concise limitation that the current
implementation and experiments focus on languages with explicit typing rules
and do not establish applicability to dynamically typed languages such as
Python.

Sincerely,
The Authors
