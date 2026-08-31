# Synthetic Java three-shot specification

This is the corrected few-shot condition used by the `syn3c` runs.  It is
prompt conditioning only: no parameters are updated and no row from MBJP,
HumanEval-Java, GFG, or SuFu is used as a demonstration.

Each example follows the benchmark's Java prompt layout: the four standard
imports, two blank lines, a class declaration, a JavaDoc task statement, and a
`public static` method signature ending at the opening brace.  The answer is a
complete source file with the same prefix and a small method body.  No JavaDoc
input/output examples, hidden tests, target class names, or target solutions
are included.

The three fixed examples are:

1. `ExampleIdentity.identity(int x)`: return the input integer unchanged.
2. `ExampleIncrement.increment(int x)`: return the input integer plus one.
3. `ExampleIsEmpty.isEmpty(String s)`: check whether the string has length zero.

The runner stores the exact prompt-prefix/body representation in
`baselines/java_baselines/run_decoder_only_zero_few_shot.py` and records this
SHA-256 in every final manifest:

```text
f937cdd87eeab6182f707d5688581471ef41917d879002e8caa7b7134150df93
```

For prefix-completion models, each complete synthetic source is followed by
the untouched benchmark prefix.  For full-source chat models, each task prefix
and complete source are shown as separate labelled parts.  The target prompt
is unchanged in both cases.  The earlier empty skeleton (`minimal_format`) and
dataset-derived examples are retained only as diagnostics and are not part of
the corrected F3 results.
