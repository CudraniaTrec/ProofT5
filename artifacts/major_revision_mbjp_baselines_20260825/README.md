# MBJP strong-baseline evidence (2026-08-25)

This package freezes the exact 67-problem, 10-candidate MBJP scores and runtime
summaries for the archived paper-recovery T5Gemma checkpoint, the matched
ordinary sampling control, corrected SynCode Java adaptations, the
upstream-faithful Repilot/JDT adapter, and frozen ProofT5 result. The archived
checkpoint gives 10/67 pass@1 and 23/67 pass@10, close to the submitted
approximately 12/67 and 24/67 row.

`analysis.json` contains the headline counts, paired exact tests, soundness
gates, and measured checker costs. `scores/` and `costs/` are verbatim copies
of the scorer and trajectory summaries. `SHA256SUMS` authenticates all package
files except itself. Older epoch-20 and diagnostic rows are retained rather
than overwritten.

The paper-facing SynCode adaptation must be labelled **SynCode + standalone-
`javac` compile-safe portfolio**. It retains each ordinary candidate unless
standalone `javac` proves it uncompilable and accepts the corresponding
SynCode candidate. It never runs benchmark tests during selection, retains ten
final candidates, and costs two generation arms. It obtains 10/67 and 24/67
with 73/670 scorer compile errors. The proposal-preserving grammar-only
diagnostic obtains 10/67 and 23/67, exactly preserving the ordinary solved set.
The upstream-style pre-mask sampling diagnostic is not a main-table result:
renormalization changes fixed-seed trajectories even after false-prune bugs are
removed.

The final corrected Repilot run obtains 10/67 and 23/67 with 112/670 compile
errors, versus the ordinary control's 122/670. It makes 18,653 JDT completion
queries and spends 150.44 seconds in JDT, or 2.66 ms per output token. A
training-only replay shows that querying `newCompletion` on literally every
token falsely rejects 56/608 known-correct Java programs; the upstream
keyword/punctuation bypass has zero false-pruned training programs and is the
formal policy. The optional ACTIVE completion propagation is also excluded
after falsely pruning 293/608 programs. A separately labelled Repilot +
standalone-`javac` portfolio remains 10/67 and 23/67 with 110/670 compile
errors.

Controlled iterative compiler feedback obtains 8/67 and 17/67, exactly equal
to its exported round-0 functional scores. It nevertheless repairs 68
initially non-compiling candidates and reduces scorer compile errors from
133/670 to 83/670 after 275 repair calls. This is evidence of improved
compilability, not improved functional correctness.
