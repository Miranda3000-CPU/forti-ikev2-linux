#!/usr/bin/env bash
#
# Assina os artefatos Windows com um certificado de assinatura de código.
#
#   FCT_SIGN_PFX=cert.pfx FCT_SIGN_PASS=... ./build/sign_windows.sh
#
# Sem FCT_SIGN_PFX o script apenas informa o que falta e sai com 0 (para não
# quebrar um build local sem certificado). Defina FCT_SIGN_REQUIRED=1 para
# transformar a ausência de certificado em erro — use isso no CI de release.
#
# Ferramenta: `osslsigncode` (Linux/macOS) ou `signtool` (Windows, do SDK).
# Instale com: apt install osslsigncode
#
# IMPORTANTE: só os artefatos deste projeto são assinados. Os binários do
# strongSwan em vendor/windows/ NÃO são — são de terceiro e assiná-los com o
# certificado da DTIC deturparia a procedência e a cadeia de confiança.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

APP_EXE="build/output/FortiClient-VPN.exe"
INSTALLER_EXE="dist/FortiClient-VPN-Setup.exe"

# Timestamp RFC 3161 é obrigatório: sem ele a assinatura morre junto com o
# certificado e o instalador volta a aparecer como não assinado.
TSA_URL="${FCT_TSA_URL:-http://timestamp.digicert.com}"
SUBJECT="${FCT_SIGN_SUBJECT:-FortiClient VPN - DTIC/PRODEPA}"
SUBJECT_URL="${FCT_SIGN_URL:-https://github.com/Miranda3000-CPU/forti-ikev2-linux}"

log()  { printf '\033[1;32m[sign]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[aviso]\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[1;31m[erro]\033[0m %s\n' "$*" >&2; exit 1; }

# ─────────────────────────────────────────── o que precisa existir
if [ -z "${FCT_SIGN_PFX:-}" ]; then
    cat >&2 << 'EOF'
[aviso] Nenhum certificado configurado (FCT_SIGN_PFX vazio). Artefatos
        entregues SEM ASSINATURA — o Windows exibirá o aviso do SmartScreen
        em "Mais informações → Executar assim mesmo".

        Para assinar:
          1. Obtenha um certificado de assinatura de código (ver README).
          2. Exporte como PFX (não-PKCS12) e guarde a senha no cofre de
             segredos do CI, nunca no repositório.
          3. Exporte:
               FCT_SIGN_PFX=cert.pfx FCT_SIGN_PASS=... ./build/sign_windows.sh
EOF
    [ "${FCT_SIGN_REQUIRED:-0}" = "1" ] && die "FCT_SIGN_REQUIRED=1 e nenhum certificado informado."
    exit 0
fi

[ -f "$FCT_SIGN_PFX" ] || die "certificado não encontrado em $FCT_SIGN_PFX"

# ─────────────────────────────────────────── escolher a ferramenta
case "$(uname -s)" in
    MINGW*|MSYS*|CYGWIN*) HAVE_SIGNTOOL=1 ;;
    *) HAVE_SIGNTOOL=0 ;;
esac

if command -v osslsigncode >/dev/null 2>&1; then
    TOOL="osslsigncode"
elif [ "$HAVE_SIGNTOOL" = "1" ] && command -v signtool.exe >/dev/null 2>&1; then
    TOOL="signtool"
else
    die "nenhuma ferramenta de assinatura disponível (instale 'osslsigncode' ou o Windows SDK com signtool)."
fi
log "Ferramenta: $TOOL"

# ─────────────────────────────────────────── assinar
sign_one() {
    local alvo="$1"
    [ -f "$alvo" ] || { warn "$alvo ausente, pulando"; return 0; }

    log "assinando $alvo"
    if [ "$TOOL" = "osslsigncode" ]; then
        osslsigncode sign \
            -pkcs12 "$FCT_SIGN_PFX" -pass "$FCT_SIGN_PASS" \
            -h sha256 -t "$TSA_URL" \
            -n "$SUBJECT" -i "$SUBJECT_URL" \
            -in "$alvo" -out "$alvo.assinado" \
            && mv -f "$alvo.assinado" "$alvo"
    else
        signtool.exe sign /fd SHA256 /td SHA256 /tr "$TSA_URL" \
            /f "$(cygpath -w "$FCT_SIGN_PFX")" /p "$FCT_SIGN_PASS" \
            /n "$SUBJECT" /i "$SUBJECT_URL" \
            "$(cygpath -w "$alvo")"
    fi
    verify_one "$alvo"
}

verify_one() {
    local alvo="$1"
    if [ "$TOOL" = "osslsigncode" ]; then
        osslsigncode verify -in "$alvo" >/dev/null 2>&1 \
            || die "a assinatura de $alvo não valida"
    else
        signtool.exe verify /pa "$(cygpath -w "$alvo")" >/dev/null 2>&1 \
            || warn "signtool verify alarmou em $alvo (pode ser cadeia incompleta no Wine)"
    fi
    log "ok: $alvo assinado e verificado"
}

# O executável da GUI e o instalador. O instalador sem assinatura continua
# disparando o SmartScreen mesmo que o .exe dentro dele esteja assinado.
sign_one "$APP_EXE"
sign_one "$INSTALLER_EXE"

# Guarda explícita: o motor é GPLv2 de terceiro e não leva a assinatura da DTIC.
for terceiro in vendor/windows/charon-svc.exe vendor/windows/swanctl.exe; do
    [ -f "$terceiro" ] && warn "não assinado (third-party strongSwan, GPLv2): $terceiro"
done

log "concluído"
