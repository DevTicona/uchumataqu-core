#!/usr/bin/env bash
# Ubuntu 24.04 x86_64 / WSL2. Todas las escrituras se limitan a PLN.
set -euo pipefail
pln_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
export UV_CACHE_DIR="$pln_root/tools/uv-cache"
mkdir -p "$pln_root/tools/packages" "$pln_root/tools/root"
cd "$pln_root/tools/packages"
if ! sha256sum --check ../hfst-debs.sha256; then
    apt-get download 'hfst=3.16.0-5build4' 'libhfst55=3.16.0-5build4' \
        'libfst22=1.7.9-5build1' 'libfoma0t64=1:0.10.0+s311-1.2build2'
    sha256sum --check ../hfst-debs.sha256
fi
while read -r digest package; do
    dpkg-deb --extract "$package" "$pln_root/tools/root"
done < ../hfst-debs.sha256
if [[ ! -x "$pln_root/.venv/bin/python" ]]; then
    uv venv --python python3.12 "$pln_root/.venv"
fi
uv pip install --python "$pln_root/.venv/bin/python" --no-deps -r "$pln_root/requirements.lock"
uv pip check --python "$pln_root/.venv/bin/python"
