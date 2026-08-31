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

# T5Gemma2 was added after SynCode's pinned Transformers 4.53.2.  Keep a
# separate compatibility environment so the upstream-pinned causal setup is
# still reproducible while the frozen encoder-decoder checkpoints can load.
SYNCODE_T5GEMMA_ENV="${PROOFT5_SYNCODE_T5GEMMA_ENV:-/data2/x/hzc/.uv-envs/prooft5-syncode-t5gemma-py312}"
if [ ! -x "$SYNCODE_T5GEMMA_ENV/bin/python" ]; then
  uv venv --python 3.12 "$SYNCODE_T5GEMMA_ENV"
fi
uv pip install --python "$SYNCODE_T5GEMMA_ENV/bin/python" \
  -e third_party/baselines/syncode
uv pip install --python "$SYNCODE_T5GEMMA_ENV/bin/python" \
  'transformers==5.12.1'
printf 'SynCode + T5Gemma2 compatibility environment: %s\n' "$SYNCODE_T5GEMMA_ENV/bin/python"
