#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/runtime_env.sh"

make -C "${PROOFT5_ROOT}/coq_model" -j"$(nproc)"
make -C "${PROOFT5_ROOT}/SuFu/SuFu/surface" -j"$(nproc)"

# SuFu already adds -Ofast. Release mode adds -DNDEBUG and crashes on sum.f.
cmake \
  -S "${PROOFT5_ROOT}/SuFu/SuFu_origin/src" \
  -B "${PROOFT5_SUFU_BUILD_DIR}" \
  -DSUFU_DEPS_PREFIX="${PROOFT5_SUFU_DEPS}" \
  -DCMAKE_BUILD_TYPE=
cmake \
  --build "${PROOFT5_SUFU_BUILD_DIR}" \
  --target run \
  --parallel "$(nproc)"

printf 'Built Coq, SuFu parser, and full SuFu runtime.\n'
