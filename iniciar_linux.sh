#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

if ! command -v python3 >/dev/null 2>&1; then
    echo "python3 não encontrado"
    exit 1
fi

if ! python3 -c "import tkinter" >/dev/null 2>&1; then
    echo "python3-tk não encontrado"
    exit 1
fi

if ! command -v swanctl >/dev/null 2>&1; then
    echo "strongswan não encontrado"
    exit 1
fi

exec python3 "$DIR/vpn-gui.py" "$@"
