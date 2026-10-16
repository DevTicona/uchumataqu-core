#!/usr/bin/env bash
set -euo pipefail
pln_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
export PYTHONPATH="$pln_root/src${PYTHONPATH:+:$PYTHONPATH}"
exec "$pln_root/.venv/bin/python" -m uchumataqu_hfst "$@"
