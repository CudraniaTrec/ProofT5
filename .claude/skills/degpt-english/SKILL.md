---
name: degpt-english
description: Remove LLM writing traces from English academic prose — response letters, rebuttals, and manuscript text — while protecting facts, numbers, verbatim quotes, and defined terminology. Fixes four failure modes: synonym churn (one referent, many names), buried points (the news hidden in a trailing clause or behind a content-free wrap-up), coined or undefined terms, and broken or fake transitions. 用于英文论文与审稿回复的「去 GPT 味」：一义多名、重点后置、造词无定义、衔接跳跃/假衔接。Simplified Chinese prose → use qu-ai-wei instead. Full paper drafting pipelines → academic-paper. Triggers: de-GPT, remove GPT traces, GPT flavor, AI-sounding, humanize English, tighten the response letter, 去除 GPT 痕迹, 英文去 AI 味, 这段太 GPT 了.
---

# De-GPT English Academic Prose

LLM-generated academic English is mechanically fluent but structurally careless.
The damage is rarely in vocabulary lists ("delve", "crucial" — other checklists
cover those). It is in four structural habits, all of which survive a grammar
pass. This skill detects and repairs those four, in this repository's own
terms.

## Scope

- In scope: English prose the user owns and is revising — response letters,
  rebuttals, cover letters, manuscript paragraphs, README prose.
- Out of scope: Simplified Chinese (route to `qu-ai-wei`); drafting a paper
  from scratch (route to `academic-paper`); reviewing a paper (`academic-paper-reviewer`).

## Protected content — edit arbitration order

When a fix conflicts with something below, the higher item wins:

1. **Facts**: numbers, p-values, intervals, task counts, table/figure/section
   references, claim strength. Never strengthen, weaken, or round a claim to
   make a sentence read better. If the honest fact is inconvenient, state it
   plainly — hiding an unfavorable comparison inside a vague sentence is one
   of the failure modes, not a fix for one. A number's *value* is protected;
   its *form* (word vs numeral) is not — that is governed by Number style
   below.
2. **Verbatim quotes** from another document (e.g. `revquote` blocks quoting
   the manuscript). These are evidence; leave them untouched. If the quoted
   sentence is itself the problem, fix the source document and quote the new
   text — as a separate, flagged work item, not silently.
3. **Defined terminology**: terms the project defines or uses canonically
   (table below). Do not "vary" them; do not rename them for elegance.
4. **Approved structure**: the author's unit structure (comment → response →
   changes made → quotes) and any wording the author has signed off on.
5. Everything else — sentence order, sentence internals, connectives, openers
   — is editable.

## The four diagnostics

Apply each as a test, not a vibe. A passage passes when all four tests pass.

### 1. Synonym churn (one referent, many names)

**Test**: list every name each recurring referent carries in the unit
(a response item, a subsection). If a referent has more than one name and the
variants are not deliberately distinguished concepts, it fails.

**Why it fails**: in technical prose, repetition of a term is a feature — it
tells the reader the same thing is meant. Variation forces the reader to
re-verify reference, and reviewers read it as either evasion or sloppiness.

**Fix**: pick the canonical term (table below), use it everywhere, and let it
repeat. Distinguish only when the concepts genuinely differ — then say so once.

**Real example (this repo's response letter)**: TyFlow's own first-stage
constraint was called "grammar pruning" in one paragraph and "syntactic
pruning" everywhere else (including the same response's Changes-made items).
Fix: "syntactic pruning" everywhere; "grammar masking" is SynCode's mechanism,
"completion-guided token pruning" is Repilot's — different systems, different
names, deliberately.

### 2. Buried point (the news in an inconspicuous position)

**Test**: for each sentence, mark where the new information lands. It fails if
the sentence's news sits in a trailing subordinate or participial clause, after
a colon, or inside a parenthetical, while the front of the sentence is setup,
hedge, or restatement. It also fails — harder — if a sentence carries no news
at all ("These results provide context for performance on Java under the
respective generation settings"): that is a burial by omission, usually of a
comparison the author does not enjoy stating.

**Why it fails**: readers take the main clause of the first sentence as the
point. LLMs optimize local fluency, so they park the point wherever it connects
most smoothly — typically last, after the scaffolding.

**Fix**: move the news into the main clause of the sentence: "The larger models
solve 34–42 of 67 MBJP tasks; TyFlow-2B solves 17." Delete content-free
wrap-up sentences; if a synthesis is genuinely there, state it concretely.
Delete rather than hedge (project prose rule). When the buried fact is
unfavorable, unburying it is mandatory — reviewers compute the numbers anyway,
and a letter that concedes cleanly reads as stronger, not weaker.

**Real example**: "These results suggest that when the model assigns too little
probability to correct programs, decoding-time constraints alone offer limited
gains, suggesting that training with a suitable representation can be more
effective..." — the paper's central thesis arrives in a trailing participial
clause, hedged twice ("suggest...suggesting"). Fix: two sentences, thesis
first, evidence second, no participial tail.

### 3. Coined or undefined terms

**Test**: every noun that names a mechanism, category, or configuration must
(a) already be defined at first use in this document or its source, (b) be a
canonical project term, or (c) be replaced by plain wording. A label invented
for one sentence ("the dominant residual mode", "the compile-safe
configuration", "the output set", "an active slot") fails.

**Why it fails**: undefined coinage imitates the texture of technical writing
without its contract. Reviewers who know the literature check whether the term
is standard; when it is not, the prose reads as manufactured.

**Fix**: prefer the project's existing term or plain description ("the largest
remaining failure category", "the configuration in which SynCode masks
grammar-violating tokens"). If a shorthand is genuinely needed, define it once,
at first use, then keep it fixed (see diagnostic 1).

### 4. Broken or fake transitions

**Test**: read consecutive sentences. Each sentence after the first must pick
up an explicit anchor — a repeated canonical term, a true contrast, or a stated
inference ("Because X", "Under the same budget"). A jump with no anchor fails.
A transition sentence that could prefix any paragraph in any letter ("These
results show that...") is a fake anchor: it fails even though it looks like
cohesion.

**Why it fails**: LLMs produce sentence-level connective tissue (moreover,
however, these results) without building referential continuity. The surface
flows; the argument teleports.

**Fix**: name the actual link. Usually the fix is making the shared referent
the subject of the next sentence. Cut formulaic wrap-ups ("Together, these
results show consistent improvements...") unless the sentence after them uses
the synthesis. Restructure paragraph order only when anchors cannot be built
without it — and note any such reordering in the report.

## Formulaic scaffolding to audit (beyond the four)

These recur in LLM rebuttal prose. Audit, don't auto-delete:

- **Thesaurus openers**: "Thanks for this comment / suggestion / question /
  criticism" — the noun varies for variety's sake. Unify ("Thanks for this
  comment."), or drop the formula and open with the answer.
- **"These results show/suggest/indicate..."** wrap-ups — at most one per
  response unit, and only when the stated inference is new information.
- **"precisely", "notably", "importantly"** as sentence adverbs — usually
  diagnostic-2 markers: the emphasized word often carries the buried point.
- **Triple parallelism** ("we define its terms, express its rules, and
  implement its constraints") — fine once; padding if every list has three.

## Response-letter self-containment

Each reviewer reads their own section and should never need to open another
reviewer's. A response that delegates its substance — "we addressed this in
our response to Comment 1.4" — fails, however polite the pointer.

- Every comment's response carries the full substance for its own question —
  settings, numbers, and reasoning — even when the same material already
  appears in another reviewer's section. Length is not the constraint;
  independence is.
- When the same content must exist in several responses, duplicate the source
  passage (verbatim where possible, reframed for the local question) and
  treat the copies as one fact with several bodies: a later change to a
  number, term, or claim is applied to every copy at once, and identical
  facts keep identical wording.
- Cross-references are acceptable only as navigation after the substance is
  fully present locally — e.g., an editor's overview bullet that already
  summarizes the evidence and points to where it is detailed. Never route a
  reviewer to another reviewer's section.
- Same-reviewer pointers (Comment 1.4 citing Comment 1.3) follow the same
  rule: the substance stands alone; a pointer, if kept at all, comes after.

Calibration (this repo's response letter, fixed 2026-09-26): the letter
carried 28 cross-references. The 17 delegation instances (R1 1.1(3) and 1.4;
R2 2.1, 2.2, 2.3; R3 3.3, 3.4, 3.5) were replaced by inlined substance; the
11 editor-overview pointers, whose bullets already summarize the evidence,
were kept as navigation for the editor, who reads the whole letter.

## Canonical terms (this repository)

| Referent | Canonical name | Not |
|---|---|---|
| TyFlow's first-stage constraint | syntactic pruning | grammar pruning (that is SynCode's masking) |
| TyFlow's second-stage constraint | type pruning | type filtering |
| The evolving input to the encoder | dynamic typing context | changing context, context cache (except when discussing KV reuse) |
| What the model emits | decision sequence | derivation text, proof script |
| Failure categories (App. C) | All-invalid / Well-typed but wrong / Ranking failure / Solved@1 | ad-hoc re-descriptions ("compilable programs with incorrect behavior") after first definition |
| The fine-tuned unconstrained model | the baseline (CodeT5-220M / T5Gemma2-2B) | the pretrained model, the plain model |
| Sec. 6.2.3 temperature-sampling control | the ordinary control | (reserve "control" for this row) |
| No-checks ablation row | the base model | |
| Tasks solved | solved tasks / solved set (define once) | successes, hits |
| The three prompted LLMs | the larger (prompted) models | modern LLMs, external models |

Do not "correct" a term inside a verbatim quote; if source and letter
disagree, list it under manuscript propagation.

## Number style

Quantities are written as Arabic numerals, uniformly — including small
counts, where LLM prose habitually spells them out ("ten candidates" reads
more "naturally fluent", which is exactly the trace being removed):

- Protocol quantities: "10 candidates per task", "at most 2 rounds",
  "3 solved examples", "beam 10", "top-20".
- Counts: "4 categories", "3 benchmarks", "6 solved tasks", "34–42 of 67
  tasks".
- All measurements: "7.97 hypotheses", "59.1%", "2.74×", "31.1 ms".

Calibration (this repo's response letter, pre-fix): the same protocol
quantity appeared as "ten candidates per task" in the letter's own prose and
as "10 candidates each" in the quoted manuscript text — one fact, two forms.

Keep as words:

- Ordinals: "the first candidate", "the second term".
- Idiomatic, non-quantifying uses: "one of the compared methods", "no task".
- Numbers that are part of a proper term, title, or cited name.

Sentence-initial numerals: reword rather than spell out ("Ten candidates are
generated..." → "Each task generates 10 candidates" or "We generate 10
candidates per task").

Cross-document rule: the letter's number forms must match the manuscript's
for the same fact. A quote keeps the manuscript's form (protected); if the
manuscript itself is mixed, that entry goes on the propagation list.

## Procedure

1. **Inventory** (read-only): for each unit, list referents and their names;
   mark each sentence's news position; flag coinages; flag anchor-less jumps;
   list every quantity in word form and every word/numeral inconsistency
   (within the unit, and letter-vs-manuscript for the same fact); list every
   cross-reference and classify it as editor-navigation (substance already
   present) or reviewer-delegation (substance missing — must be inlined).
2. **Fix in order**: terms (churn + coinage) → number forms → sentence
   structure (unbury) → transitions → openers/wrap-ups. Term and number
   fixes first, so restructured sentences are built on stable vocabulary.
3. **Verify**: diff numbers, p-values, section/table references, and claim
   strength against the pre-edit text — all values unchanged; number forms
   unified per Number style; verbatim quotes untouched; "Changes made" items
   still match what the text says; duplicated fact-groups are consistent
   across all copies (grep each fact; identical wording and values
   everywhere).
4. **Report**: a table of edits tagged CHURN / BURIED / COINED / JUMP /
   SCAFFOLD, each with a one-line reason. Split into (a) letter-only edits,
   (b) edits whose sentence also exists in the manuscript (propagation list —
   touching the manuscript shifts page numbers, which re-opens the letter's
   page-anchor verification; never do (b) silently).

## Output

Before/after for every substantive edit, in the report. Where a fix changes
emphasis or concedes something the current text soft-pedals, mark it
`needs-author-confirmation` — unburying an unfavorable comparison is usually
correct, but the author decides.
