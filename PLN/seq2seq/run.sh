#!/usr/bin/env bash
set -euo pipefail
model_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
export PYTHONPATH="$model_root/src${PYTHONPATH:+:$PYTHONPATH}"
exec "$model_root/.venv/bin/python" -m uchumataqu_seq2seq "$@"
