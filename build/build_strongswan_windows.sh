#!/usr/bin/env bash
#
# Cross-compila o strongSwan para Windows (MinGW-w64) — é o motor VPN usado no
# Windows, com suporte a IKEv2 + PSK + EAP-MSCHAPv2 (que o IKEv2 nativo do
# Windows não oferece).
#
# Uso:
#   ./build/build_strongswan_windows.sh
#
# Requisitos (Debian/Ubuntu):
#   sudo apt install build-essential mingw-w64 curl bzip2 perl make
#
# Saída:
#   vendor/windows/charon-svc.exe, vendor/windows/swanctl.exe (+ DLLs)
#
# Referência: https://docs.strongswan.org/docs/latest/os/windows.html

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_DIR="${STRONGSWAN_BUILD_DIR:-$ROOT_DIR/build/cache/strongswan}"
OUT_DIR="${STRONGSWAN_OUT_DIR:-$ROOT_DIR/vendor/windows}"
PREFIX="$BUILD_DIR/prefix"

STRONGSWAN_VERSION="${STRONGSWAN_VERSION:-6.1.0}"
OPENSSL_VERSION="${OPENSSL_VERSION:-3.0.15}"

HOST="x86_64-w64-mingw32"
JOBS="${JOBS:-$(nproc 2>/dev/null || echo 2)}"

log() { printf '\033[1;32m[strongswan-windows]\033[0m %s\n' "$*"; }
die() { printf '\033[1;31m[erro]\033[0m %s\n' "$*" >&2; exit 1; }

# ─────────────────────────────────────────────────────────── pré-requisitos
for tool in "curl" "tar" "make" "${HOST}-gcc" "${HOST}-windres"; do
    command -v "$tool" >/dev/null 2>&1 || die "faltando '$tool'. Rode: sudo apt install build-essential mingw-w64 curl bzip2 perl make"
done

mkdir -p "$BUILD_DIR" "$OUT_DIR"
cd "$BUILD_DIR"

# ─────────────────────────────────────────────────────────────── OpenSSL
# OpenSSL estático evita ter de distribuir libcrypto/libssl separadamente.
# O OpenSSL 3 no MinGW instala em lib64 (e algumas versões em lib).
if [ -f "$PREFIX/lib64/libcrypto.a" ]; then
    OSSL_LIBDIR="$PREFIX/lib64"
elif [ -f "$PREFIX/lib/libcrypto.a" ]; then
    OSSL_LIBDIR="$PREFIX/lib"
else
    OSSL_LIBDIR=""
fi

if [ -z "$OSSL_LIBDIR" ]; then
    log "Baixando OpenSSL $OPENSSL_VERSION"
    if [ ! -d "openssl-$OPENSSL_VERSION" ]; then
        curl -fL -o "openssl-$OPENSSL_VERSION.tar.gz" \
            "https://www.openssl.org/source/openssl-$OPENSSL_VERSION.tar.gz"
        tar xzf "openssl-$OPENSSL_VERSION.tar.gz"
    fi

    log "Compilando OpenSSL para $HOST"
    cd "openssl-$OPENSSL_VERSION"
    ./Configure mingw64 no-shared no-tests --prefix="$PREFIX" \
        --cross-compile-prefix="${HOST}-"
    make -j"$JOBS"
    make install_sw
    cd "$BUILD_DIR"

    if [ -f "$PREFIX/lib64/libcrypto.a" ]; then
        OSSL_LIBDIR="$PREFIX/lib64"
    else
        OSSL_LIBDIR="$PREFIX/lib"
    fi
else
    log "OpenSSL já compilado ($OSSL_LIBDIR)"
fi

# ────────────────────────────────────────────────────────────── strongSwan
if [ ! -d "strongswan-$STRONGSWAN_VERSION" ]; then
    log "Baixando strongSwan $STRONGSWAN_VERSION"
    curl -fL -o "strongswan-$STRONGSWAN_VERSION.tar.bz2" \
        "https://download.strongswan.org/strongswan-$STRONGSWAN_VERSION.tar.bz2"
    tar xjf "strongswan-$STRONGSWAN_VERSION.tar.bz2"
fi

log "Configurando strongSwan (IKEv2 + PSK + EAP-MSCHAPv2 + WFP/iph + swanctl)"
cd "strongswan-$STRONGSWAN_VERSION"

# --enable-attr é obrigatório: é ele que negocia o IP virtual (CPRP) do
# FortiGate. Sem ele o cliente não pede endereço.
# LIBS: bibliotecas de sistema do Windows exigidas pelo OpenSSL estático.
CFLAGS="-O2 -Wall -Wno-pointer-sign -Wno-format-security -Wno-format -mno-ms-bitfields -I$PREFIX/include" \
LDFLAGS="-static -static-libgcc -L$OSSL_LIBDIR" \
LIBS="-lws2_32 -lcrypt32 -lgdi32 -ladvapi32 -luser32" \
PKG_CONFIG_PATH="$OSSL_LIBDIR/pkgconfig" \
./configure \
    --host="$HOST" \
    --prefix="$PREFIX" \
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
make -j"$JOBS"

# ─────────────────────────────────────────────────────────────── coleta
log "Copiando binários para $OUT_DIR"
for exe in charon-svc.exe swanctl.exe; do
    found="$(find src -name "$exe" -type f | head -n1 || true)"
    [ -n "$found" ] || die "não encontrei $exe após a compilação"
    cp "$found" "$OUT_DIR/"
done

# DLLs do MinGW eventualmente necessárias (quando não houver link estático).
for dll in libgcc_s_seh-1.dll libwinpthread-1.dll libssp-0.dll; do
    path="$(command -v "${HOST}-gcc" | xargs dirname)/../$HOST/lib/$dll"
    [ -f "$path" ] && cp "$path" "$OUT_DIR/" || true
done

cp "$ROOT_DIR/build/strongswan-windows.conf" "$OUT_DIR/strongswan.conf" 2>/dev/null || true

log "Verificando os binários gerados"
file "$OUT_DIR/charon-svc.exe" "$OUT_DIR/swanctl.exe"

if command -v wine >/dev/null 2>&1; then
    log "Testando swanctl.exe sob Wine"
    wine "$OUT_DIR/swanctl.exe" --version || log "AVISO: swanctl.exe não executou sob Wine"
else
    log "AVISO: wine ausente; não foi possível testar swanctl.exe"
fi

log "Concluído. Binários em: $OUT_DIR"
log "Próximo passo: ./build/build_windows.sh"
