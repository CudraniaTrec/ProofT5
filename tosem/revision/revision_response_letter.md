# Revision Response Letter

Manuscript: *TyFlow: A Type-Aware Approach to Neural Code Models*
Manuscript ID: TOSEM-2026-0076

Dear Editor and Reviewers,

Thank you for the detailed and constructive comments. We have prepared a
revised evaluation package and a focused set of manuscript changes. The
Evaluation section now includes two additional Java benchmarks, a task-level
failure analysis, runtime measurements on SuFu, pruning and beam-exhaustion
statistics, comparisons with larger decoder-only models, and comparisons with
SynCode, Repilot, rejection sampling, and iterative compiler repair. We also
re-audited the Java baseline training recipe and replaced the HumanEval-Java
and TransCoder-GFG baselines with strengthened checkpoints (same benchmarks,
same beam decoding, no prompt-engineering changes), so that the reported
improvements are measured against stronger baselines; the audit and its
holdout-based selection protocol are documented in Appendix B, and all frozen
scores are included in the artifact package. The Appendix reports the combined
Java statistical analysis---on the pooled 186 tasks all four paired
differences remain significant with the strengthened baselines---and the SuFu
confidence intervals.

The remaining wording changes outside Evaluation and Appendix have been
applied directly to the manuscript, and all section references and page counts
in this letter refer to the current compiled version.

## Response to the Editor's meta-review

### Missing failure analysis

We added a task-level failure taxonomy and representative examples in
Appendix C. The taxonomy separates top-1 success, ranking failure, all-invalid
generation, and well-typed but functionally incorrect programs. It shows that
the remaining TyFlow failures are primarily semantic rather than type errors.

### Limited evaluation benchmarks

We added HumanEval-Java and TransCoder-GFG, both normalized to the existing
Java task format. The benchmark-specific results remain in the main RQ1 table,
and the Appendix reports the combined Java analysis over 186 paired tasks. To
avoid under-trained baselines on the two added benchmarks, we re-audited the
baseline recipe and retrained those two baselines (learning-rate correction
and holdout-selected checkpoints; Appendix B); the combined analysis uses
these stronger baselines and still finds significant differences on all four
metrics.

### Missing discussion on scalability

RQ2 now reports pruning statistics and 220M SuFu inference time for the
no-check, syntactic-pruning, type-pruning, and dynamic-context configurations.
The text also states the observed beam-exhaustion result (no task dead-ends
under beam 10). How the approach scales to more expressive type systems is
discussed in the Limitations subsection of the Evaluation section.

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

The RQ2 text reports the measured SuFu runtime of the same 220M model for
each component configuration. This keeps the system-cost analysis with the component
ablation to which it belongs.

## Response to Reviewer 1

### Statistical reliability of the small test sets

We added Appendix D. MBJP, HumanEval-Java, and TransCoder-GFG are analyzed as
186 paired Java tasks. For pass@1 and pass@10, the Appendix reports 95%
Wilson intervals and exact two-sided paired McNemar tests; FSP reports a
t-interval over per-task ranks with an exact two-sided sign test, and CER a
Wilson interval over candidates with an exact sign test on per-task error
fractions. The merged analysis
is computed with the strengthened baselines (Appendix B), so the significance
of the pooled comparison is not an artifact of under-trained baselines; at
the 220M scale, where only MBJP is reported, the exact tests on 67 tasks are
underpowered (the Appendix states both reasons: modest improvements and few
discordant pairs), which is why the pooled 2B analysis carries the
statistical conclusion. For SuFu, the
Appendix reports the same intervals and paired tests at the 220M scale (all
four differences significant), and at the 2B scale Wilson intervals plus the
compilation-error bound derived from aggregate counts alone. HumanEval-
Java's 16-task result remains visible in Table 1; the
merged analysis prevents that small set from being the sole basis for the
statistical conclusion.

### Java pass@1 improvement

The revised Evaluation reports the benchmark-specific Java results and the
failure taxonomy. It now briefly explains that the type constraints primarily
remove uncompilable candidates, while semantic errors can still affect the
top-ranked candidate; the Java-subset scope is stated separately. In addition,
the Java baselines were re-audited and strengthened (Appendix B), which raises
the HumanEval-Java baseline from 12.50% to 31.25% pass@1 and the
TransCoder-GFG baseline from 13.59% to 19.42%; the reported Java
improvements are therefore measured against stronger baselines, and on the
pooled 186 tasks all four paired differences remain significant (Appendix D).

### Modern decoder-only models

The revision reports three larger open-weight models on all four benchmarks in
the RQ1 discussion. The zero-shot and few-shot task counts are reported
separately, so the results are not combined across prompt conditions.

### First-order unification and richer type systems

We agree that the current formal and empirical evidence is limited to the
implemented first-order setting. A targeted scope and limitation paragraph
covering higher-order unification, polymorphism, subtyping, overloading, and
mutable-state-related features has been added to the Limitations subsection of
the Evaluation section. The paragraph also notes that typing rules are
formulated as constrained Horn clauses, which can in principle describe richer
type systems, and that migrating to such systems (including linear types) is
future work.

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
95% intervals and paired tests for the four reported metrics. The HumanEval-Java
and TransCoder-GFG baselines were first re-audited and strengthened (Appendix B),
so the analysis is not driven by weak baselines: on the pooled tasks the
strengthened baselines solve 34/186 at pass@1 and 62/186 at pass@10, and the
differences remain significant (pass@1 p = 0.0021, pass@10 p = 0.00054,
FSP p = 0.00076, CER p = 1.3e-19). We also add 95% intervals for the submitted SuFu
task and candidate proportions. The original benchmark-specific results are
retained in RQ1.

### W2: Runtime overhead, richer types, beam exhaustion, and fallback

RQ2 reports the measured SuFu runtime of the same 220M model for each component
configuration. The
same section reports zero strict beam dead-ends in the instrumented 58-task
run. The discussion of richer type features is a focused paragraph in the
Limitations subsection of the Evaluation section.

### W3: Decoder-only comparison and adaptation

We added the four-benchmark decoder-only comparison for MiMo-7B, Qwen3-14B,
and Qwen3-30B-A3B. The architectural adaptation discussion remains a
limitation in the Evaluation section: TyFlow currently obtains its dynamic
type context by re-encoding the evolving synthesis goal in an encoder-decoder
architecture. The representation itself carries over to a decoder-only model
unchanged; what changes is the architecture; supplying the context there would
mean prefilling the current typing context after the derivation prefix at
every step and removing it again before the next step, so its key-value
entries would be recomputed at every step and never reused. We leave this
adaptation to future work.

### W4: Scope of the CHC generality claim

The empirical claim is supported by the two evaluated languages and the
additional Java benchmarks. The requested narrowing of the CHC/generalization
wording and the explicit boundary around richer constraints have been applied
to the introduction, related-work, and conclusion text.

## Response to Reviewer 3

### SynCode, Copiloting the Copilots, and iterative refinement

RQ3 reports SynCode, Repilot (the Copiloting the Copilots comparison), and
iterative compiler repair alongside rejection sampling and TyFlow. All
external methods are rerun on one leak-clean frozen T5Gemma2-2B checkpoint
under a shared temperature-sampling protocol (the control's scores therefore
differ slightly from the beam-10 Table 1 row; the TyFlow row is identical in
both tables). The table reports functional correctness and
compilation-error rate; the text records that compiler repair improves
compilability without adding a solved MBJP task in the controlled run, and
that rejection sampling is the only external method that adds solved tasks
(three at pass@10, one at pass@1), with the differences not statistically
significant.

### Larger models

The revision provides comparisons with models larger than 2B on the same four
benchmark families (reported in the RQ1 text). Their prompt-based protocol is
kept separate from the trained encoder-decoder TyFlow results.

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

The Evaluation section now states this as a focused limitation paragraph: our
method needs a type system in which the type derivation of a program can be
computed automatically from the program text, so that existing code can be
converted into the decision-sequence format. Dynamically typed languages such
as Python still have typing rules to a degree, but the derivation cannot be
read off the program text alone, so training sequences cannot be extracted
from existing programs; this breaks the Data Usability property and with it
the training-data pipeline. Adapting such languages is left to future work.

### Artifact availability

All Java table rows and the 220M SuFu pair in the revision are backed by a
frozen artifact package: the per-candidate outputs and score JSONs, the
pre-registered evaluation and baseline-strengthening protocols (including the
validation holdouts and the epoch-selection rules), the frozen checkpoints
(including the 220M SuFu pair's checkpoint), and SHA-256 sums for datasets,
checkpoints, and scores, so each of these numbers can be traced to the exact
checkpoint, dataset revision, and scoring configuration that produced it. The
2B SuFu pair predates this record-keeping; its per-task arrays were not
preserved, so the Appendix reports for it only what the retained aggregate
counts support (Wilson intervals and the compilation-error bound).

Sincerely,
The Authors
