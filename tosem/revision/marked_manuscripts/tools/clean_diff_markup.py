#!/usr/bin/env python3
"""Post-process a latexdiff output so it compiles.

Modes:
  strike (default) - keep latexdiff's default look (blue underlined additions,
      red struck-through deletions). In-table markup is stripped because
      siunitx S columns and booktabs rules break under \\DIFadd/\\DIFdel;
      tables render in their final form.
  color - journal "color marks" look: additions printed in blue with no
      underline, deletions omitted entirely (the text reads as the new
      version). This transformation is applied globally, so changed table
      cells are also blue; S columns of changed tables become plain c
      columns (siunitx cannot parse color groups).

Both modes re-join \\emergencystretch assignments that latexdiff split
across \\DIFadd{=2em} groups.
"""
import glob
import os
import re
import sys

path = sys.argv[1]
mode = sys.argv[2] if len(sys.argv) > 2 else "strike"
new_root = sys.argv[3] if len(sys.argv) > 3 else None
with open(path, encoding="utf-8") as f:
    tex = f.read()

TOKENS = [
    r"\\DIFaddbeginFL", r"\\DIFaddendFL", r"\\DIFdelbeginFL", r"\\DIFdelendFL",
    r"\\DIFaddbegin", r"\\DIFaddend", r"\\DIFdelbegin", r"\\DIFdelend",
]


def balanced_split(s: str, cmd: str):
    """Split on every brace-balanced \\cmd{...} occurrence."""
    pat = re.compile(re.escape(cmd) + r"\s*\{")
    out = []
    i = 0
    n = len(s)
    while i < n:
        m = pat.search(s, i)
        if not m:
            break
        j = m.end()
        depth = 1
        while j < n and depth > 0:
            if s[j] == "{":
                depth += 1
            elif s[j] == "}":
                depth -= 1
            j += 1
        out.append((s[i:m.start()], s[m.end():j - 1]))
        i = j
    out.append((s[i:], None))
    return out


def transform(s: str, cmd: str, fn) -> str:
    parts = balanced_split(s, cmd)
    if len(parts) == 1:
        return s
    return "".join(before + (fn(inner) if inner is not None else "")
                   for before, inner in parts)


def strip_tokens(s: str) -> str:
    for tok in TOKENS:
        s = re.sub(tok + r"(?![A-Za-z])", "", s)
    return s


def join_emergencystretch(tex: str) -> str:
    tex = re.sub(
        r"\\DIFaddbegin\s*\\emergencystretch\\DIFadd\{=(\w+)\s*\}\s*\\DIFaddend",
        r"\\emergencystretch=\1", tex)
    tex = re.sub(
        r"\\DIFdelbegin\s*\\emergencystretch\\DIFdel\{=(\w+)\s*\}\s*\\DIFdelend",
        "", tex)
    # bare assignment whose group closes immediately: drop the assignment
    tex = re.sub(r"\\emergencystretch\\DIFadd\{=\w+\s*\}", "", tex)
    tex = re.sub(r"\\emergencystretch\\DIFdel\{=\w+\s*\}", "", tex)
    # assignment whose group also swallows following added text: keep the
    # text inside a fresh group and drop the assignment
    tex = re.sub(r"\\emergencystretch\\DIFadd\{=\w+em([ \t]*\n[ \t]*)",
                 r"\\DIFadd{\1", tex)
    tex = re.sub(r"\\emergencystretch\\DIFdel\{=\w+em([ \t]*\n[ \t]*)",
                 r"\\DIFdel{\1", tex)
    tex = re.sub(r"\\emergencystretch(?=\s*\\DIF)", "", tex)
    return tex


#latexdiff's own preamble definitions must stay intact: process the body only
#(all transforms and token stripping happen after \begin{document}).
_preamble, _sep, _body = tex.partition(r"\begin{document}")
tex = _preamble + _sep


def restore_verbatim_envs(body: str) -> str:
    """Rewrite verbatim-like environments that latexdiff corrupted.

    Inside an entirely NEW section, latexdiff injects \\DIFadd/\\DIFdel markup
    into Verbatim/lstlisting bodies, where it is typeset literally (and the
    diff engine mangles braces and '%' in code).  Such environments are
    restored wholesale from the new-side sources, matched by their first
    intact code line; tables get the same "final form" treatment elsewhere.
    """
    if not new_root:
        return body
    src_envs = []
    files = [os.path.join(new_root, "manuscript.tex"),
             os.path.join(new_root, "macros.tex")]
    files += sorted(glob.glob(os.path.join(new_root, "chapters", "*.tex")))
    for f in files:
        try:
            with open(f, encoding="utf-8") as fh:
                src = fh.read()
        except OSError:
            continue
        for m in re.finditer(
                r"\\begin\{(Verbatim|lstlisting|verbatim)\}(?:\[[^\]]*\])?", src):
            end = re.search(r"\\end\{" + m.group(1) + r"\}", src[m.end():])
            src_envs.append(src[m.end():m.end() + end.start()])

    def fix(m):
        head, env, body_, tail = m.group(1), m.group(2), m.group(3), m.group(4)
        if "\\DIF" not in body_:
            return m.group(0)
        first = None
        for line in body_.splitlines():
            l = line.strip().replace("\\DIFadd{", "").rstrip("}{ ").rstrip()
            if len(l) >= 10 and "\\DIF" not in l and not l.startswith("}"):
                first = l
                break
        if first:
            for src_body in src_envs:
                if first in src_body:
                    return head + src_body + tail
        # no source match: strip markup tokens and hope for the best
        return head + strip_tokens(body_) + tail

    pat = re.compile(
        r"(\\begin\{(Verbatim|lstlisting|verbatim)\}(?:\[[^\]]*\])?"
        r")(.*?)(\\end\{\2\})", re.S)
    return pat.sub(fix, body)


_body = restore_verbatim_envs(_body)
_body = join_emergencystretch(_body)

if mode == "color":
    body = _body
    body = transform(body, r"\DIFdelFL", lambda inner: "")
    body = transform(body, r"\DIFdel", lambda inner: "")
    body = transform(body, r"\DIFaddFL", lambda inner: r"{\color{revblue}" + inner + "}")
    body = transform(body, r"\DIFadd", lambda inner: r"{\color{revblue}" + inner + "}")
    body = strip_tokens(body)
    # \cmidrule/\multicolumn/\multirow cannot take color groups in their
    # numeric arguments; unwrap every shape latexdiff produced
    for _ in range(3):
        body = re.sub(r"\\cmidrule([^{}\n]*)\{\{\\color\{revblue\}([^{}]*)\}\}",
                      r"\\cmidrule\1{\2}", body)
        body = re.sub(r"\\cmidrule\{\\color\{revblue\}([^{}]*)\}\{\\color\{revblue\}([^{}]*)\}\}",
                      r"\\cmidrule\1{\2}", body)
        body = re.sub(r"\\cmidrule\{\\color\{revblue\}([^{}]*)\}\{\\color\{revblue\}([^{}]*)\}",
                      r"\\cmidrule\1{\2}", body)
        body = re.sub(r"\\cmidrule\{\\color\{revblue\}([^{}]*)\}", r"\\cmidrule\1", body)
        body = re.sub(r"\\multicolumn\{\{\\color\{revblue\}([^{}]*)\}\}",
                      r"\\multicolumn{\1}", body)
        body = re.sub(r"\\multirow\{\{\\color\{revblue\}([^{}]*)\}\}",
                      r"\\multirow{\1}", body)
    # tablenote \item labels must stay plain (threeparttable measures them)
    body = re.sub(r"\\item\[\\color\{revblue\}([^][]*)\]", r"\\item[\1]", body)
    body = re.sub(r"\\item\[\{\\color\{revblue\}([^][]*)\}\]", r"\\item[\1]", body)
    # microtype's text-command tracking breaks on "spaces + color group" as
    # the first thing in a font-command argument; flatten the inner group
    body = re.sub(r"(\\(?:text[a-z]*|emph|texttt)\{)\s*\{\\color\{revblue\}([^{}]*)\}\s*\}",
                  r"\1\\color{revblue}\2}", body)
    # changed tabulars: siunitx S columns cannot parse color groups
    parts = re.split(r"(\\begin\{tabular\}.*?\\end\{tabular\})", body, flags=re.S)
    for idx in range(1, len(parts), 2):
        if r"\color{revblue}" in parts[idx]:
            parts[idx] = re.sub(r"S\[table-format=[^\]]*\]", "c", parts[idx])
    body = "".join(parts)
    # override latexdiff's own definitions for any residual DIF tokens, and
    # define the color (xcolor is loaded by the manuscript preamble)
    tex += "\n\\definecolor{revblue}{RGB}{0,0,190}\n" \
           "\\renewcommand{\\DIFadd}[1]{{\\color{revblue}#1}}\n" \
           "\\renewcommand{\\DIFdel}[1]{}\n" \
           "\\renewcommand{\\DIFaddFL}[1]{{\\color{revblue}#1}}\n" \
           "\\renewcommand{\\DIFdelFL}[1]{}\n" + body
else:
    def clean_table(body: str) -> str:
        body = transform(body, r"\DIFdelFL", lambda inner: "")
        body = transform(body, r"\DIFdel", lambda inner: "")
        body = transform(body, r"\DIFaddFL", lambda inner: inner)
        body = transform(body, r"\DIFadd", lambda inner: inner)
        return strip_tokens(body)

    parts = re.split(r"(\\begin\{tabular\}.*?\\end\{tabular\})", _body, flags=re.S)
    for idx in range(1, len(parts), 2):
        parts[idx] = clean_table(parts[idx])
    tex += "".join(parts)

with open(path, "w", encoding="utf-8") as f:
    f.write(tex)
print(f"cleaned {path} [{mode}]: "
      f"{tex.count(chr(92) + 'DIFadd') + tex.count(chr(92) + 'DIFdel')} DIF tokens remain")
