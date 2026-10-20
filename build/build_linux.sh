#!/usr/bin/env bash
# Gera o executável único de Linux (PyInstaller onefile) para a release.
#
# O artefato é um arquivo só: Python, GUI e assets ficam embutidos. O motor
# VPN continua sendo o strongSwan do sistema, instalado pelo install-linux.sh.
#
# Uso: ./build/build_linux.sh
# Saída: dist/FortiClient-VPN

set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$DIR"

OUT_DIR="$DIR/dist"
WORK_DIR="$DIR/build/output/linux-work"

command -v pyinstaller >/dev/null 2>&1 || {
    echo "erro: pyinstaller não encontrado (pip install pyinstaller pillow)." >&2
    exit 1
}

if [ ! -f "build_info.py" ]; then
    python3 "$DIR/build/gen_build_info.py"
fi

mkdir -p "$OUT_DIR"
rm -rf "$WORK_DIR" "$OUT_DIR/FortiClient-VPN"

pyinstaller --noconfirm \
    --distpath "$OUT_DIR" \
    --workpath "$WORK_DIR" \
    "$DIR/build/FortiClient-VPN.spec"

[ -f "$OUT_DIR/FortiClient-VPN" ] || {
    echo "erro: o PyInstaller não gerou $OUT_DIR/FortiClient-VPN" >&2
    exit 1
}

# Smoke test: o binário precisa abrir o parser de CLI sem depender do ambiente.
"$OUT_DIR/FortiClient-VPN" --help > /dev/null || {
    echo "erro: o binário gerado não executa (--help falhou)." >&2
    exit 1
}

echo "Executável: $OUT_DIR/FortiClient-VPN ($(du -h "$OUT_DIR/FortiClient-VPN" | cut -f1))"
