#!/usr/bin/env bash
#
# UM COMANDO para gerar o instalador do Windows a partir do Linux.
#
#   ./build/preparar_instalador_windows.sh
#
# O script instala o que falta (MinGW, Wine), compila o motor strongSwan,
# instala o Python e o Inno Setup dentro do prefixo Wine e no final gera:
#
#   dist/FortiClient-VPN-Setup.exe
#
# Não é preciso preparar nada manualmente. Se preferir não buildar nada,
# use o GitHub Actions (aba Actions -> "Instalador Windows").

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK_DIR="${FCT_WORK_DIR:-$ROOT_DIR/build/cache}"
VENV_DIR="$WORK_DIR/wine-tools"
WINE_PY_VERSION="${WINE_PY_VERSION:-3.12.8}"
WINE_PY_DIR="${WINE_PY_DIR:-C:\\Python312}"
ISCC_PATH="${WINEPREFIX:-$HOME/.wine}/drive_c/Program Files (x86)/Inno Setup 6/ISCC.exe"

export WINEDEBUG="${WINEDEBUG:--all}"
export WINEDLLOVERRIDES="${WINEDLLOVERRIDES:-mscoree,mshtml=}"

# Alguns ambientes exportam TMPDIR apontando para um diretório que não existe,
# o que quebra `make`, `configure` e o próprio Wine.
if [ -z "${TMPDIR:-}" ] || [ ! -d "${TMPDIR}" ]; then
    export TMPDIR=/tmp
fi
mkdir -p "$TMPDIR" 2>/dev/null || export TMPDIR=/tmp

# O Wine cria um soquete em $XDG_RUNTIME_DIR; se esse diretório não for
# gravável (ex.: /run/user/<uid> somente leitura), aproveitamos a pasta de build.
if [ -z "${XDG_RUNTIME_DIR:-}" ] || [ ! -w "${XDG_RUNTIME_DIR}" ]; then
    export XDG_RUNTIME_DIR="$WORK_DIR/wine-runtime"
fi
mkdir -p "$XDG_RUNTIME_DIR" 2>/dev/null || true

log() { printf '\033[1;32m[preparar]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[aviso]\033[0m %s\n' "$*" >&2; }
die() { printf '\033[1;31m[erro]\033[0m %s\n' "$*" >&2; exit 1; }

need_root() {
    if [ "$(id -u)" -eq 0 ]; then
        "$@"
    elif command -v sudo >/dev/null 2>&1; then
        sudo "$@"
    else
        die "preciso de root/sudo para instalar pacotes do sistema."
    fi
}

# ─────────────────────────────────────────── 1. dependências do sistema
log "Verificando dependências do sistema"

missing=()
for tool in wine x86_64-w64-mingw32-gcc make curl tar bzip2 perl; do
    command -v "$tool" >/dev/null 2>&1 || missing+=("$tool")
done

if [ "${#missing[@]}" -gt 0 ]; then
    log "Instalando pacotes ausentes: ${missing[*]}"
    if command -v apt-get >/dev/null 2>&1; then
        need_root apt-get update -qq
        need_root apt-get install -y build-essential mingw-w64 wine wine64 curl bzip2 perl make
    else
        die "instale manualmente: ${missing[*]} (o script automatiza apenas apt-get)."
    fi
fi
log "Dependências OK"

mkdir -p "$WORK_DIR" "$VENV_DIR"

# ─────────────────────────────────────────── 2. motor strongSwan
if [ -f "$ROOT_DIR/vendor/windows/charon-svc.exe" ] && [ -f "$ROOT_DIR/vendor/windows/swanctl.exe" ]; then
    log "Motor strongSwan já está em vendor/windows (pulando compilação)"
else
    log "Compilando o motor strongSwan para Windows"
    "$ROOT_DIR/build/build_strongswan_windows.sh"
fi

# ─────────────────────────────────────────── 3. Python do Windows no Wine
WINE_BIN="${WINE_BIN:-wine}"

python_ok() {
    "$WINE_BIN" "$1" --version >/dev/null 2>&1
}

# Procura um Python do Windows já presente no prefixo, inclusive instalações
# por usuário ("Just for me"), que é o padrão do instalador da python.org.
find_existing_wine_python() {
    local candidate
    for candidate in "$WINE_PY_DIR\\python.exe" 'C:\Python312\python.exe' 'C:\Python311\python.exe' 'C:\Python313\python.exe'; do
        if python_ok "$candidate"; then
            printf '%s' "$candidate"
            return 0
        fi
    done

    local prefix="${WINEPREFIX:-$HOME/.wine}"
    local found
    found="$(find "$prefix/drive_c/users" -maxdepth 6 -ipath "*Programs/Python/Python3*/python.exe" 2>/dev/null | head -n1)"
    if [ -n "$found" ] && [ -f "$found" ]; then
        # /home/.../drive_c/users/x/... -> C:\users\x\...
        printf 'C:\\%s' "$(printf '%s' "${found#*/drive_c/}" | tr '/' '\\')"
        return 0
    fi
    return 1
}

log "Inicializando o prefixo Wine"
"$WINE_BIN" wineboot --init >/dev/null 2>&1 || true

if WINE_PYTHON="$(find_existing_wine_python)"; then
    log "Python do Windows já disponível em $WINE_PYTHON"
else
    WINE_PYTHON="$WINE_PY_DIR\\python.exe"
    log "Instalando Python $WINE_PY_VERSION dentro do Wine"
    installer="$WORK_DIR/python-$WINE_PY_VERSION-amd64.exe"
    if [ ! -f "$installer" ]; then
        curl -fL -o "$installer" \
            "https://www.python.org/ftp/python/$WINE_PY_VERSION/python-$WINE_PY_VERSION-amd64.exe" \
            || die "não consegui baixar o Python $WINE_PY_VERSION"
    fi
    "$WINE_BIN" "$installer" /quiet InstallAllUsers=1 PrependPath=1 Include_test=0 \
        Include_launcher=0 "TargetDir=$WINE_PY_DIR" || true
    "$WINE_BIN" wineboot -u >/dev/null 2>&1 || true
    if ! python_ok "$WINE_PYTHON"; then
        WINE_PYTHON="$(find_existing_wine_python)" \
            || die "Python do Windows não respondeu no prefixo Wine."
    fi
    log "Python do Windows instalado em $WINE_PYTHON"
fi

# ─────────────────────────────────────────── 4. Inno Setup
if [ ! -f "$ISCC_PATH" ]; then
    # Procurar em outros locais antes de baixar.
    for candidate in "${WINEPREFIX:-$HOME/.wine}/drive_c/Program Files/Inno Setup 6/ISCC.exe" \
                     "${WINEPREFIX:-$HOME/.wine}/drive_c/Program Files (x86)/Inno Setup 7/ISCC.exe"; do
        if [ -f "$candidate" ]; then
            ISCC_PATH="$candidate"
            break
        fi
    done
fi

if [ -f "$ISCC_PATH" ]; then
    log "Inno Setup já instalado"
else
    log "Instalando o Inno Setup dentro do Wine"
    is_installer="$WORK_DIR/innosetup.exe"
    if [ ! -f "$is_installer" ] || ! head -c2 "$is_installer" | grep -q "MZ"; then
        # A página jrsoftware.org/download.php devolve HTML; o binário real está
        # nas releases do GitHub.
        curl -fL --retry 3 -o "$is_installer" \
            "https://github.com/jrsoftware/issrc/releases/download/is-6_7_3/innosetup-6.7.3.exe" \
            || die "não consegui baixar o Inno Setup"
    fi
    head -c2 "$is_installer" | grep -q "MZ" || die "o download do Inno Setup não é um executável."
    "$WINE_BIN" "$is_installer" /VERYSILENT /SUPPRESSMSGBOXES /NORESTART /SP- || true
    if [ ! -f "$ISCC_PATH" ]; then
        found="$(find "${WINEPREFIX:-$HOME/.wine}/drive_c" -iname "ISCC.exe" 2>/dev/null | head -n1)"
        [ -n "$found" ] || die "instalação do Inno Setup não gerou ISCC.exe"
        ISCC_PATH="$found"
    fi
    log "Inno Setup instalado em $ISCC_PATH"
fi

# ─────────────────────────────────────────── 5. pacote final
log "Gerando o executável e o instalador"
WINE_BIN="$WINE_BIN" WINE_PYTHON="$WINE_PYTHON" ISCC="$ISCC_PATH" \
    "$ROOT_DIR/build/build_windows.sh"

echo
log "Pronto. Instalador:"
ls -lh "$ROOT_DIR/dist/FortiClient-VPN-Setup.exe"
log "Copie esse arquivo para o Windows e execute (aceite o UAC)."
