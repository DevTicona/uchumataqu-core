#!/usr/bin/env bash
set -euo pipefail
model_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec "$model_root/.venv/bin/python" -m pytest -c "$model_root/pytest.ini" "$model_root/tests" "$@"
