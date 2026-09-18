#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════
#  FortiClient VPN — Desinstalador para Linux
#  Duplo-clique neste arquivo para desinstalar.
# ═══════════════════════════════════════════════════════════════════
set -euo pipefail

APP_NAME="FortiClient VPN"

# ── Detectar ferramenta de diálogo gráfico ──
GUI=""
if command -v zenity &>/dev/null; then
    GUI="zenity"
elif command -v kdialog &>/dev/null; then
    GUI="kdialog"
fi

mostrar_info() {
    if [ "$GUI" = "zenity" ]; then
        zenity --info --title="$APP_NAME" --text="$1" --width=400 --no-wrap 2>/dev/null
    elif [ "$GUI" = "kdialog" ]; then
        kdialog --title "$APP_NAME" --msgbox "$1" 2>/dev/null
    else
        echo -e "\n$1\n"
    fi
}

mostrar_erro() {
    if [ "$GUI" = "zenity" ]; then
        zenity --error --title="$APP_NAME — Erro" --text="$1" --width=400 --no-wrap 2>/dev/null
    elif [ "$GUI" = "kdialog" ]; then
        kdialog --title "$APP_NAME — Erro" --error "$1" 2>/dev/null
    else
        echo -e "\n❌ ERRO: $1\n" >&2
    fi
}

confirmar() {
    if [ "$GUI" = "zenity" ]; then
        zenity --question --title="$APP_NAME" --text="$1" --width=400 --no-wrap 2>/dev/null
        return $?
    elif [ "$GUI" = "kdialog" ]; then
        kdialog --title "$APP_NAME" --yesno "$1" 2>/dev/null
        return $?
    else
        read -rp "$1 (s/N): " resp
        [[ "$resp" =~ ^[sS]$ ]]
        return $?
    fi
}

# Verificar se está instalado
if ! dpkg -l forticlient-vpn 2>/dev/null | grep -q "^ii"; then
    mostrar_info "$APP_NAME não está instalado neste computador."
    exit 0
fi

if ! confirmar "Deseja remover o $APP_NAME?\n\nO programa será desinstalado do sistema."; then
    exit 0
fi

if command -v pkexec &>/dev/null; then
    pkexec apt-get remove -y forticlient-vpn 2>&1
else
    sudo apt-get remove -y forticlient-vpn 2>&1
fi

# Remover atalho da área de trabalho
rm -f "$HOME/Área de trabalho/FortiClient-VPN.desktop" 2>/dev/null || true
rm -f "$HOME/Desktop/FortiClient-VPN.desktop" 2>/dev/null || true

mostrar_info "✅ $APP_NAME foi desinstalado com sucesso."
