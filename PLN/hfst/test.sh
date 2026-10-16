#!/usr/bin/env bash
set -euo pipefail
pln_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec "$pln_root/.venv/bin/python" -m pytest -c "$pln_root/pytest.ini" "$pln_root/tests" "$@"
