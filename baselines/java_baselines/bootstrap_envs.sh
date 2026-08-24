#!/usr/bin/env bash
set -euo pipefail

cd /data2/x/hzc/prooft5

python3 baselines/java_baselines/fetch_upstreams.py

SYNCODE_ENV="${PROOFT5_SYNCODE_ENV:-/data2/x/hzc/.uv-envs/prooft5-syncode-py312}"
if [ ! -x "$SYNCODE_ENV/bin/python" ]; then
  uv venv --python 3.12 "$SYNCODE_ENV"
fi
uv pip install --python "$SYNCODE_ENV/bin/python" \
  -e third_party/baselines/syncode

printf 'SynCode environment: %s\n' "$SYNCODE_ENV/bin/python"
printf 'Iterative refinement and Repilot adapters can use the existing project environment.\n'
