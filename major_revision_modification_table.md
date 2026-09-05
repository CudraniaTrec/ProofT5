# Major Revision Modification Table

Scope of this table: only Evaluation and Appendix are changed directly in the
current working tree. Rows marked “Author manual” are recommendations for the
authors to decide and insert; they have not been applied to other paper
chapters.

| Reviewer item | Required paper action | Location | Evidence | Status |
|---|---|---|---|---|
| R1: small test sets and missing statistical reliability | Report the merged Java task count, 95% intervals, and paired tests for pass@1, pass@10, FSP, and CER; add 95% intervals for the submitted SuFu pass rates and CER. | Appendix D | java_statistics_combined.json; sufu_statistics.json; 186 Java tasks and 58 SuFu tasks | Implemented |
| R2 W1: limited benchmarks | Retain MBJP and add HumanEval-Java and TransCoder-GFG with exact denominators. | Evaluation RQ1; Appendix B | Frozen score package | Implemented |
| R1/R2 W1: HumanEval-Java has few tasks | Explain briefly that the primary statistical calculation combines the three aligned Java test sets while preserving the individual rows. | Appendix D | 67 + 16 + 103 = 186 | Implemented |
| R1: missing failure analysis | Provide task-level failure categories and representative invalid and well-typed-but-wrong programs. | Appendix C | Frozen candidate status files | Implemented |
| R1: Java pass@1 gain is modest | Add one short explanation of the smaller gain and avoid extending the claim beyond the implemented Java subset. | Evaluation RQ1 | Java rows and Appendix C | Implemented |
| R1: branching factor and pruning | Report observed syntactic and type-pruning rates and strict beam dead-ends. | Evaluation RQ2 | 59.1%, 8.2%, and 0/58 | Implemented |
| R2 W2: runtime overhead | Report the 2B SuFu mean runtime for no-check, syntactic pruning, type pruning, and dynamic context. | Evaluation RQ2 | Four 58-task JSONL runs | Implemented |
| R2 W2: synthesis-tree scalability | Add a concise qualitative discussion of how deeper trees, longer decision sequences, and more rule choices increase decoding and checking work as programs become more complex. | Evaluation RQ2 | RQ2 runtime and pruning discussion | Implemented |
| R2 W2: beam exhaustion and fallback | State the observed exhaustion result and that fixed-budget incomplete slots are scored fail-closed without unconstrained fallback. | Evaluation RQ2 | Instrumented decoding metadata | Implemented |
| R1/R2 W2: richer type features | Add a concise boundary statement for polymorphism, variance, subtyping, type inference, overloading, and ownership-related features. | Limitations or Theory discussion | Current Java subset and first-order implementation | Author manual |
| R1: first-order unification | State what the restriction excludes and that higher-order unification is outside the current evidence. | methods_meta.tex or Limitations | Current formalization | Author manual |
| R2 W3: modern decoder-only models | Add zero-shot/few-shot pass@1 results for larger decoder-only models on the same benchmark families, with conditions separated. | Evaluation after RQ1 | MiMo-7B, Qwen3-14B, Qwen3-30B-A3B | Implemented |
| R2 W3: decoder-only adaptation | Add the limitation that the current dynamic type-context path requires an encoder-decoder module; a decoder-only redesign would require a different program representation and would not retain the current context mechanism unchanged. | Evaluation Limitations | Current dual-encoding architecture | Implemented |
| R2 W4: CHC generality is broader than evidence | Narrow claims about arbitrary constraints/Turing-complete expressiveness to the formal framework, and state that experiments cover type correctness in the evaluated languages. | Introduction, Related Work, Conclusion | Existing claims and current experiments | Author manual |
| R2 W4: richer constraint case study or limitation | Choose the limitation route unless a new case study is intentionally added; mention that richer constraint families are not evaluated. | Limitations | No new case study in this package | Author manual |
| R3: SynCode comparison | Keep the aligned SynCode comparison and label the compile-safe adaptation precisely. | Evaluation RQ3 | Existing Java comparison artifacts | Implemented |
| R3: Copiloting the Copilots | Identify Repilot as the comparison method and retain its Java results. | Evaluation RQ3 | Existing Repilot score package | Implemented |
| R3: iterative refinement | Add the controlled iterative compiler-repair row and report its observed functional and compilation results. | Evaluation RQ3 | 8/67, 17/67, and 83/670 | Implemented |
| Editor/R3: system cost | Keep TyFlow runtime with RQ2 component analysis; do not create a separate mixed cost table unless the authors later choose to do so. | Evaluation RQ2 | 2B SuFu runtime package | Implemented |
| R3: dynamically typed languages/Python | Add a short limitation stating that the current implementation depends on an explicit type system and does not establish results for dynamically typed Python programs. | Evaluation Limitations | Current language scope | Implemented |
| ACM submission requirement | Include a cover-letter paragraph stating how the revision addresses the editor and reviewer concerns. | Response letter | revision_response_letter.md | Draft prepared |

## Files changed directly

- tosem/paper/chapters/evaluation.tex
- tosem/paper/chapters/appendix.tex

## Files prepared for author review

- revision_response_letter.md
- major_revision_modification_table.md

All other paper chapters remain unchanged relative to the Git baseline used
for the pre-evaluation PDF comparison.
