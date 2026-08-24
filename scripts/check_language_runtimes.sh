#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/runtime_env.sh"

for command in "${PROOFT5_JAVA}" "${PROOFT5_JAVAC}" cmake coqc ocamlrun timeout; do
  command -v "${command}" >/dev/null
done
test -x "${PROOFT5_SUFU_FULL_EXECUTOR}"
test -f "${PROOFT5_SUFU_PARSER}"

work_dir="$(mktemp -d /tmp/prooft5-runtime-check-XXXXXX)"
trap 'rm -rf "${work_dir}"' EXIT

cat >"${work_dir}/Main.java" <<'JAVA'
public class Main {
    public static void main(String[] args) {
        System.out.println("JAVA_RUNTIME_OK");
    }
}
JAVA
"${PROOFT5_JAVAC}" -d "${work_dir}" "${work_dir}/Main.java"
test "$("${PROOFT5_JAVA}" -cp "${work_dir}" Main)" = "JAVA_RUNTIME_OK"

cat >"${work_dir}/RuntimeCheck.v" <<'COQ'
Theorem runtime_ok : True.
Proof. exact I. Qed.
COQ
coqc -q -o "${work_dir}/RuntimeCheck.vo" "${work_dir}/RuntimeCheck.v"

ocamlrun \
  "${PROOFT5_SUFU_PARSER}" \
  "${PROOFT5_ROOT}/SuFu/SuFu/test.f" \
  "${work_dir}/surface.json" \
  >"${work_dir}/surface.log" 2>&1
test -s "${work_dir}/surface.json"

if ! timeout 180 \
  "${PROOFT5_SUFU_FULL_EXECUTOR}" \
  --benchmark="${PROOFT5_ROOT}/SuFu/SuFu_origin/benchmark/autolifter/single-pass/sum.f" \
  --output="${work_dir}/sufu-result.f" \
  --use_gurobi=false \
  >"${work_dir}/sufu.log" 2>&1; then
  tail -n 40 "${work_dir}/sufu.log"
  exit 1
fi
grep -qx "Success" "${work_dir}/sufu.log"
test -s "${work_dir}/sufu-result.f"

"${PROOFT5_JAVA}" -version 2>&1 | head -n 1
"${PROOFT5_JAVAC}" -version
coqc --version | head -n 2
cmake --version | head -n 1
printf 'Java compile/run: OK\n'
printf 'Coq compile: OK\n'
printf 'SuFu surface parse: OK\n'
printf 'SuFu full synthesis: OK\n'
