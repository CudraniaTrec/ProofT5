#!/usr/bin/env bash
# Build the marked-up manuscript for the TOSEM major revision.
#
#   old side: the submitted version, extracted from git (default: ce2dd2c)
#   new side: the CURRENT working tree of tosem/paper/
#
# Outputs, in this directory:
#   manuscript_marked.pdf       latexdiff look: blue underlined additions,
#                               red struck-through deletions; tables in final
#                               form (in-table markup breaks siunitx/booktabs)
#
# Notes:
# - the bibliography is NOT diffed (the new .bbl is excluded); references are
#   rebuilt with bibtex at compile time.
# - re-run this script after any further edit to tosem/paper/ (e.g. after the
#   Appendix D 2B SuFu placeholders are resolved).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"   # repo root
PAPER="$ROOT/tosem/paper"
OUT="$(cd "$(dirname "$0")" && pwd)"
BASE_COMMIT="${1:-ce2dd2c}"                      # submitted-version commit

LATEXDIFF="$(command -v latexdiff || true)"
[ -z "$LATEXDIFF" ] && LATEXDIFF="$OUT/tools/latexdiff"   # vendored v1.4.0 (CTAN)

WORK="$(mktemp -d /tmp/marked_build.XXXXXX)"
trap 'rm -rf "$WORK"' EXIT

# 1. old side: extract the submitted paper from git
mkdir -p "$WORK/orig"
git -C "$ROOT" archive "$BASE_COMMIT" tosem/paper | tar -x -C "$WORK/orig"

# 2. new side: copy current sources (no .bbl -> bibliography excluded from diff)
mkdir -p "$WORK/new"
cp -r "$PAPER"/manuscript.tex "$PAPER"/macros.tex "$PAPER"/chapters \
      "$PAPER"/assets "$PAPER"/*.cls "$PAPER"/*.bst "$PAPER"/*.bbx \
      "$PAPER"/*.cbx "$PAPER"/*.dbx "$PAPER"/bibtex.bib "$PAPER"/acmart.bib \
      "$WORK/new/" 2>/dev/null || true

# 3. flattened diff
perl "$LATEXDIFF" --flatten "$WORK/orig/tosem/paper/manuscript.tex" \
                  "$WORK/new/manuscript.tex" > "$WORK/diff.tex"

build_one () {  # $1 = mode (strike|color), $2 = jobname
  mkdir -p "$WORK/$1"
  cp -r "$WORK"/new/. "$WORK/$1/"
  cp "$WORK/diff.tex" "$WORK/$1/$2.tex"
  python3 "$OUT/tools/clean_diff_markup.py" "$WORK/$1/$2.tex" "$1" "$WORK/new"
  cd "$WORK/$1"
  pdflatex -interaction=nonstopmode "$2.tex" > /dev/null
  bibtex "$2" > /dev/null
  pdflatex -interaction=nonstopmode "$2.tex" > /dev/null
  pdflatex -interaction=nonstopmode "$2.tex"
  cp "$2.tex" "$2.pdf" "$OUT/"
  echo "done: $OUT/$2.pdf ($(pdfinfo "$2.pdf" | awk '/^Pages/{print $2}') pages)"
}

build_one strike manuscript_marked
