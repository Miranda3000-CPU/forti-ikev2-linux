#!/usr/bin/env bash
#
# Gera o pacote Windows a partir do Linux:
#   1. build_info.py (versão/commit)
#   2. motor strongSwan para Windows (MinGW) — opcional se já vendorizado
#   3. FortiClient-VPN.exe (PyInstaller rodando dentro do Wine)
#   4. instalador Inno Setup (ISCC rodando dentro do Wine)
#
# Uso:
#   ./build/build_windows.sh                 # tudo (usa vendor/windows já pronto)
#   ./build/build_windows.sh --with-strongswan
#   ./build/build_windows.sh --skip-installer
#
# Requisitos: wine com um Python do Windows instalado no prefixo, Inno Setup
# (ISCC.exe) para o passo 4.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="$ROOT_DIR/build/output"
DIST_DIR="$ROOT_DIR/dist"
VENDOR_DIR="$ROOT_DIR/vendor/windows"

WITH_STRONGSWAN=0
SKIP_INSTALLER=0

for arg in "$@"; do
    case "$arg" in
        --with-strongswan) WITH_STRONGSWAN=1 ;;
        --skip-installer) SKIP_INSTALLER=1 ;;
        -h|--help) sed -n '2,16p' "$0"; exit 0 ;;
        *) echo "opção desconhecida: $arg" >&2; exit 2 ;;
    esac
done

log() { printf '\033[1;32m[build-windows]\033[0m %s\n' "$*"; }
die() { printf '\033[1;31m[erro]\033[0m %s\n' "$*" >&2; exit 1; }

command -v wine >/dev/null 2>&1 || die "wine não encontrado."

WINE_BIN="${WINE_BIN:-wine}"
WINE_PYTHON="${WINE_PYTHON:-python.exe}"

# ───────────────────────────────────────────── 1. versão/commit no pacote
log "Gerando build_info.py"
python3 "$ROOT_DIR/build/gen_build_info.py"

# ───────────────────────────────────────────── 2. motor strongSwan
if [ "$WITH_STRONGSWAN" = "1" ]; then
    log "Cross-compilando o motor strongSwan"
    "$ROOT_DIR/build/build_strongswan_windows.sh"
fi

if [ ! -f "$VENDOR_DIR/swanctl.exe" ] || [ ! -f "$VENDOR_DIR/charon-svc.exe" ]; then
    die "motor ausente em vendor/windows (rode com --with-strongswan ou vendorize os binários)."
fi

# ───────────────────────────────────────────── 3. executável da GUI
log "Limpando artefatos anteriores"
# NÃO apagar $OUT_DIR inteiro: o script de preparação guarda cache e o runtime
# do Wine lá dentro.
mkdir -p "$OUT_DIR"
rm -rf "$OUT_DIR/work" "$OUT_DIR/FortiClient-VPN.exe"

log "Verificando o Python do Windows no prefixo Wine"
"$WINE_BIN" "$WINE_PYTHON" --version >/dev/null 2>&1 || die "o prefixo Wine não tem Python do Windows. Rode ./build/preparar_instalador_windows.sh (instala tudo) ou defina WINE_PYTHON=C:/Python312/python.exe."

log "Rodando PyInstaller sob Wine"
"$WINE_BIN" "$WINE_PYTHON" -m pip install --disable-pip-version-check -q pyinstaller pillow
"$WINE_BIN" "$WINE_PYTHON" -m PyInstaller --noconfirm \
    --distpath "$OUT_DIR" --workpath "$OUT_DIR/work" \
    "$ROOT_DIR/build/FortiClient-VPN.spec"

EXE="$OUT_DIR/FortiClient-VPN.exe"
[ -f "$EXE" ] || die "PyInstaller não gerou $EXE"
log "Executável: $EXE"

# ───────────────────────────────────────────── 4. instalador
mkdir -p "$DIST_DIR"
if [ "$SKIP_INSTALLER" = "1" ]; then
    log "Instalador ignorado (--skip-installer). Copiando o .exe para dist/"
    cp "$EXE" "$DIST_DIR/FortiClient-VPN.exe"
    exit 0
fi

ISCC="${ISCC:-${WINEPREFIX:-$HOME/.wine}/drive_c/Program Files (x86)/Inno Setup 6/ISCC.exe}"
[ -f "$ISCC" ] || die "ISCC.exe não encontrado. Rode ./build/preparar_instalador_windows.sh (instala tudo) ou defina ISCC=/caminho/ISCC.exe."

# O ISCC é um programa Windows: precisa de caminho Windows (Z:\...) para o .iss.
iss_unix="$ROOT_DIR/build/FortiClient-VPN-Setup.iss"
iss_win="$(WINEDEBUG=-all "$WINE_BIN" winepath -w "$iss_unix" 2>/dev/null | tr -d '\r' | head -n1)"
if [ -z "$iss_win" ]; then
    iss_win="Z:$(printf '%s' "$iss_unix" | tr '/' '\\')"
fi

log "Compilando o instalador com Inno Setup"
"$WINE_BIN" "$ISCC" "$iss_win" || die "ISCC falhou ao gerar o instalador."

# ───────────────────────────────────────────── 5. assinatura (opcional)
# Sem FCT_SIGN_PFX o script só avisa. A assinatura tem que vir DEPOIS do
# instalador: assinar o .exe antes do ISCC não produziria um instalador
# assinado, porque o Inno Setup reconstrói o arquivo final.
FCT_TSA_URL="${FCT_TSA_URL:-}" FCT_SIGN_REQUIRED="${FCT_SIGN_REQUIRED:-0}" \
    "$ROOT_DIR/build/sign_windows.sh"

log "Concluído. Artefatos em $DIST_DIR:"
ls -lh "$DIST_DIR"
