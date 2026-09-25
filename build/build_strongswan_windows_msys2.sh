#!/usr/bin/env bash
#
# Compila o strongSwan para Windows dentro do MSYS2 (usado pelo GitHub Actions).
#
# Diferenças em relação ao build MinGW do Linux:
#   * o OpenSSL vem pronto do MSYS2 (mingw-w64-x86_64-openssl);
#   * as DLLs são copiadas automaticamente com `ldd`.
#
# Uso (dentro de um shell MINGW64 do MSYS2):
#   bash build/build_strongswan_windows_msys2.sh

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_DIR="${STRONGSWAN_BUILD_DIR:-$ROOT_DIR/build/cache/strongswan-msys2}"
OUT_DIR="${STRONGSWAN_OUT_DIR:-$ROOT_DIR/vendor/windows}"
STRONGSWAN_VERSION="${STRONGSWAN_VERSION:-6.1.0}"
MINGW_PREFIX="${MINGW_PREFIX:-/mingw64}"

log() { printf '\033[1;32m[strongswan-msys2]\033[0m %s\n' "$*"; }
die() { printf '\033[1;31m[erro]\033[0m %s\n' "$*" >&2; exit 1; }

command -v gcc >/dev/null 2>&1 || die "gcc do MinGW não encontrado (abra o shell MINGW64)."
command -v make >/dev/null 2>&1 || die "make não encontrado."

mkdir -p "$BUILD_DIR" "$OUT_DIR"
cd "$BUILD_DIR"

if [ ! -d "strongswan-$STRONGSWAN_VERSION" ]; then
    log "Baixando strongSwan $STRONGSWAN_VERSION"
    curl -fL -o "strongswan-$STRONGSWAN_VERSION.tar.bz2" \
        "https://download.strongswan.org/strongswan-$STRONGSWAN_VERSION.tar.bz2"
    tar xjf "strongswan-$STRONGSWAN_VERSION.tar.bz2"
fi

log "Configurando strongSwan (IKEv2 + PSK + EAP-MSCHAPv2 + WFP/iph + swanctl)"
cd "strongswan-$STRONGSWAN_VERSION"

# --enable-attr é obrigatório: negocia o IP virtual (CPRP) do FortiGate.
PKG_CONFIG_PATH="$MINGW_PREFIX/lib/pkgconfig" \
CFLAGS="-O2 -Wall -Wno-pointer-sign -Wno-format-security -Wno-format -mno-ms-bitfields -I$MINGW_PREFIX/include" \
LDFLAGS="-L$MINGW_PREFIX/lib" \
./configure \
    --host=x86_64-w64-mingw32 \
    --prefix="$MINGW_PREFIX" \
    --disable-defaults \
    --enable-monolithic \
    --enable-static \
    --enable-svc \
    --enable-ikev2 \
    --enable-nonce \
    --enable-pem \
    --enable-pkcs1 \
    --enable-pubkey \
    --enable-x509 \
    --enable-openssl \
    --enable-md4 \
    --enable-sha1 \
    --enable-sha2 \
    --enable-hmac \
    --enable-eap-identity \
    --enable-eap-mschapv2 \
    --enable-attr \
    --enable-socket-win \
    --enable-kernel-wfp \
    --enable-kernel-iph \
    --enable-swanctl \
    --with-swanctldir=swanctl \
    --with-strongswan-conf=strongswan.conf

log "Compilando strongSwan"
make -j"$(nproc 2>/dev/null || echo 2)"

log "Copiando binários para $OUT_DIR"
for exe in charon-svc.exe swanctl.exe; do
    found="$(find src -name "$exe" -type f | head -n1 || true)"
    [ -n "$found" ] || die "não encontrei $exe após a compilação"
    cp "$found" "$OUT_DIR/"
done

# Copia as DLLs realmente exigidas (OpenSSL, zlib, runtime do MinGW).
if command -v ldd >/dev/null 2>&1; then
    log "Copiando DLLs dependentes"
    for exe in charon-svc.exe swanctl.exe; do
        ldd "$OUT_DIR/$exe" | awk '{print $3}' | grep -E '^/mingw64/bin/.*\.dll$' | while read -r dll; do
            cp -n "$dll" "$OUT_DIR/" || true
        done
    done
fi

cp "$ROOT_DIR/build/strongswan-windows.conf" "$OUT_DIR/strongswan.conf"

log "Conteúdo final de vendor/windows:"
ls -lh "$OUT_DIR"
