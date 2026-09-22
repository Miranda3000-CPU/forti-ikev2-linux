#!/usr/bin/env bash
# =============================================================================
# FortiClient VPN Manager — Inicializador Seguro e Simplificado (Linux)
# Execução a partir do código-fonte com checagem automática de dependências,
# configuração anti-interferência de permissões e atalhos na Área de Trabalho.
# =============================================================================
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

GREEN='\033[1;32m'
YELLOW='\033[1;33m'
BLUE='\033[1;34m'
RED='\033[1;31m'
RESET='\033[0m'

echo -e "${BLUE}========================================================${RESET}"
echo -e "${BLUE}  FortiClient VPN Manager — Inicializador Linux         ${RESET}"
echo -e "${BLUE}========================================================${RESET}"
echo ""

# 1. Verificar se ambiente gráfico está ativo
if [ -z "${DISPLAY:-}" ] && [ -z "${WAYLAND_DISPLAY:-}" ]; then
    echo -e "${RED}[ERRO] Nenhum servidor gráfico detectado (DISPLAY ou WAYLAND).${RESET}"
    echo "Este aplicativo possui interface gráfica (Tkinter) e necessita de ambiente de desktop."
    exit 1
fi

# 2. Diagnóstico de dependências
MISSING_DEPS=()

if ! command -v python3 >/dev/null 2>&1; then
    MISSING_DEPS+=("python3")
fi

if ! python3 -c "import tkinter" >/dev/null 2>&1; then
    MISSING_DEPS+=("python3-tk")
fi

if ! python3 -c "from PIL import Image, ImageDraw" >/dev/null 2>&1; then
    MISSING_DEPS+=("python3-pil")
fi

if ! command -v swanctl >/dev/null 2>&1; then
    MISSING_DEPS+=("strongswan" "strongswan-swanctl")
fi

NEED_SUDOERS=0
SUDOERS_FILE="/etc/sudoers.d/forticlient-vpn"
if [ ! -f "$SUDOERS_FILE" ] || ! sudo -n swanctl --list-sas >/dev/null 2>&1; then
    NEED_SUDOERS=1
fi

# 3. Satisfazer dependências caso necessário
if [ ${#MISSING_DEPS[@]} -gt 0 ] || [ "$NEED_SUDOERS" -eq 1 ]; then
    echo -e "${YELLOW}[*] Configuração inicial de ambiente necessária:${RESET}"
    [ ${#MISSING_DEPS[@]} -gt 0 ] && echo -e "    Pacotes a instalar: ${MISSING_DEPS[*]}"
    [ "$NEED_SUDOERS" -eq 1 ] && echo -e "    Permissões de rede: Configurar regras seguras em $SUDOERS_FILE"
    echo ""
    echo -e "Solicitando elevação administrativa (sudo/pkexec) para aplicar as configurações..."

    SUDO_CMD="sudo"
    if [ -z "${TERM:-}" ] || [ ! -t 0 ]; then
        if command -v pkexec >/dev/null 2>&1; then
            SUDO_CMD="pkexec"
        fi
    fi

    # Instalação de pacotes faltantes
    if [ ${#MISSING_DEPS[@]} -gt 0 ]; then
        if command -v apt-get >/dev/null 2>&1; then
            $SUDO_CMD apt-get update -qq
            $SUDO_CMD apt-get install -y --no-install-recommends "${MISSING_DEPS[@]}" libcharon-extra-plugins curl
        elif command -v dnf >/dev/null 2>&1; then
            $SUDO_CMD dnf install -y "${MISSING_DEPS[@]}" curl
        elif command -v pacman >/dev/null 2>&1; then
            $SUDO_CMD pacman -Sy --noconfirm "${MISSING_DEPS[@]}" curl
        fi
    fi

    # Configuração de sudoers estrito (anti-interferência e anti-travamento de GUI)
    if [ "$NEED_SUDOERS" -eq 1 ]; then
        echo -e "${YELLOW}[*] Gravando regras seguras de execução em $SUDOERS_FILE...${RESET}"
        TMP_SUDOERS=$(mktemp)
        cat << 'EOF_SUDO' > "$TMP_SUDOERS"
# FortiClient VPN - Regras especificas de rede para conexao corporativa
# Permite ao swanctl e regras de roteamento IP operarem sem travar a interface grafica
ALL ALL=(root) NOPASSWD: /usr/sbin/swanctl --load-all
ALL ALL=(root) NOPASSWD: /usr/sbin/swanctl --list-sas
ALL ALL=(root) NOPASSWD: /usr/sbin/swanctl --initiate --child forticlient
ALL ALL=(root) NOPASSWD: /usr/sbin/swanctl --terminate --ike forticlient
ALL ALL=(root) NOPASSWD: /usr/bin/swanctl --load-all
ALL ALL=(root) NOPASSWD: /usr/bin/swanctl --list-sas
ALL ALL=(root) NOPASSWD: /usr/bin/swanctl --initiate --child forticlient
ALL ALL=(root) NOPASSWD: /usr/bin/swanctl --terminate --ike forticlient
ALL ALL=(root) NOPASSWD: /usr/bin/tee /etc/swanctl/conf.d/forti.conf
ALL ALL=(root) NOPASSWD: /usr/bin/chmod 600 /etc/swanctl/conf.d/forti.conf
ALL ALL=(root) NOPASSWD: /usr/bin/mkdir -p /etc/swanctl/conf.d
ALL ALL=(root) NOPASSWD: /usr/sbin/ip rule add lookup 220 pref 220
ALL ALL=(root) NOPASSWD: /sbin/ip rule add lookup 220 pref 220
EOF_SUDO

        # Validar sintaxe com visudo antes de instalar
        if command -v visudo >/dev/null 2>&1; then
            if visudo -cf "$TMP_SUDOERS" >/dev/null 2>&1; then
                $SUDO_CMD cp "$TMP_SUDOERS" "$SUDOERS_FILE"
                $SUDO_CMD chown root:root "$SUDOERS_FILE"
                $SUDO_CMD chmod 0440 "$SUDOERS_FILE"
            else
                echo -e "${RED}[ERRO] Sintaxe do sudoers inválida. Abortando gravação.${RESET}"
            fi
        else
            $SUDO_CMD cp "$TMP_SUDOERS" "$SUDOERS_FILE"
            $SUDO_CMD chown root:root "$SUDOERS_FILE"
            $SUDO_CMD chmod 0440 "$SUDOERS_FILE"
        fi
        rm -f "$TMP_SUDOERS"

        $SUDO_CMD mkdir -p /etc/swanctl/conf.d
        $SUDO_CMD systemctl enable strongswan-starter.service 2>/dev/null || $SUDO_CMD systemctl enable strongswan.service 2>/dev/null || true
        $SUDO_CMD systemctl start strongswan-starter.service 2>/dev/null || $SUDO_CMD systemctl start strongswan.service 2>/dev/null || true
    fi

    echo -e "${GREEN}✓ Dependências e configurações aplicadas com sucesso.${RESET}\n"
fi

# 4. Assegurar atalho na Área de Trabalho e no Menu do Usuário
DESKTOP_ENTRY="$HOME/.local/share/applications/forticlient-vpn.desktop"
mkdir -p "$HOME/.local/share/applications"

# Gerar o arquivo .desktop apontando para este projeto
cat << EOF_DESKTOP > "$DESKTOP_ENTRY"
[Desktop Entry]
Version=1.0
Type=Application
Name=FortiClient VPN
GenericName=VPN Client
Comment=Gerenciador FortiClient VPN IKEv2 (DTIC/PRODEPA)
Exec=$DIR/iniciar_linux.sh
Icon=$DIR/assets/icon.png
Terminal=false
Categories=Network;Security;
Keywords=vpn;fortinet;forticlient;ikev2;ipsec;dtic;prodepa;
StartupWMClass=Tk
StartupNotify=true
EOF_DESKTOP
chmod +x "$DESKTOP_ENTRY"

# Área de Trabalho
DESKTOP_DIR="$HOME/Área de trabalho"
[ ! -d "$DESKTOP_DIR" ] && DESKTOP_DIR="$HOME/Desktop"
if [ -d "$DESKTOP_DIR" ]; then
    cp "$DESKTOP_ENTRY" "$DESKTOP_DIR/FortiClient-VPN.desktop"
    chmod +x "$DESKTOP_DIR/FortiClient-VPN.desktop"
    gio set "$DESKTOP_DIR/FortiClient-VPN.desktop" metadata::trusted true 2>/dev/null || true
fi

# 5. Executar aplicação Python (ou encerrar se solicitado apenas setup/verificação)
if [ "${1:-}" = "--setup-only" ] || [ "${1:-}" = "--check" ]; then
    echo -e "${GREEN}✓ Ambiente e dependências configurados com sucesso.${RESET}"
    exit 0
fi

echo -e "${GREEN}Iniciando FortiClient VPN Manager...${RESET}"
exec python3 "$DIR/vpn-gui.py" "$@"
