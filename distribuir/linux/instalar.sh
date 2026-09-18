#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════
#  FortiClient VPN — Instalador para Linux (Ubuntu / Debian)
#  Duplo-clique neste arquivo para instalar.
# ═══════════════════════════════════════════════════════════════════
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEB_FILE="$DIR/forticlient-vpn_1.0.0_all.deb"
APP_NAME="FortiClient VPN"

# ── Detectar ferramenta de diálogo gráfico ──
GUI=""
if command -v zenity &>/dev/null; then
    GUI="zenity"
elif command -v kdialog &>/dev/null; then
    GUI="kdialog"
fi

# ── Funções de UI ──
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

pedir_senha() {
    if [ "$GUI" = "zenity" ]; then
        zenity --password --title="$APP_NAME — Senha de Administrador" 2>/dev/null
    elif [ "$GUI" = "kdialog" ]; then
        kdialog --title "$APP_NAME" --password "Senha de Administrador:" 2>/dev/null
    else
        read -rsp "Senha de administrador: " pw
        echo "$pw"
    fi
}

# ── Verificações iniciais ──

# Verificar se o .deb existe
if [ ! -f "$DEB_FILE" ]; then
    mostrar_erro "Pacote de instalação não encontrado!\n\nArquivo esperado:\n$DEB_FILE\n\nVerifique se o arquivo .deb está na mesma pasta deste instalador."
    exit 1
fi

# Verificar se é Debian/Ubuntu
if ! command -v dpkg &>/dev/null; then
    mostrar_erro "Este instalador é para sistemas Ubuntu / Debian.\n\nSeu sistema não possui o gerenciador de pacotes dpkg."
    exit 1
fi

# ── Diálogo de confirmação ──
if ! confirmar "Deseja instalar o $APP_NAME?\n\nO programa será instalado no sistema e ficará disponível\nno menu de aplicativos e na área de trabalho.\n\nSerá solicitada sua senha de administrador."; then
    exit 0
fi

# ── Instalação ──
INSTALL_OK=0

# Tentar com pkexec (diálogo gráfico de senha do sistema)
if command -v pkexec &>/dev/null; then
    if pkexec bash -c "apt-get install -y -f '$DEB_FILE' 2>&1"; then
        INSTALL_OK=1
    fi
fi

# Fallback: pedir senha manualmente
if [ "$INSTALL_OK" -eq 0 ]; then
    SENHA=$(pedir_senha)
    if [ -z "$SENHA" ]; then
        mostrar_erro "Instalação cancelada pelo usuário."
        exit 1
    fi

    RESULTADO=$(echo "$SENHA" | sudo -S apt-get install -y -f "$DEB_FILE" 2>&1)
    if [ $? -eq 0 ]; then
        INSTALL_OK=1
    else
        mostrar_erro "Falha na instalação.\n\nDetalhes:\n${RESULTADO:0:300}"
        exit 1
    fi
fi

if [ "$INSTALL_OK" -eq 1 ]; then
    # Criar atalho na Área de Trabalho
    DESKTOP_DIR="$HOME/Área de trabalho"
    [ ! -d "$DESKTOP_DIR" ] && DESKTOP_DIR="$HOME/Desktop"

    if [ -d "$DESKTOP_DIR" ] && [ -f /usr/share/applications/forticlient-vpn.desktop ]; then
        cp /usr/share/applications/forticlient-vpn.desktop "$DESKTOP_DIR/FortiClient-VPN.desktop" 2>/dev/null || true
        chmod +x "$DESKTOP_DIR/FortiClient-VPN.desktop" 2>/dev/null || true
        gio set "$DESKTOP_DIR/FortiClient-VPN.desktop" metadata::trusted true 2>/dev/null || true
    fi

    mostrar_info "✅ $APP_NAME instalado com sucesso!\n\nVocê pode abrir o programa:\n\n  • Pelo atalho na Área de Trabalho\n  • Pelo menu de aplicativos (busque \"FortiClient\")\n  • Pelo terminal: forticlient-vpn"
else
    mostrar_erro "Não foi possível concluir a instalação.\nTente executar manualmente no terminal:\n\nsudo apt install ./$DEB_FILE"
fi
