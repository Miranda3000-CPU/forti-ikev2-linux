#!/usr/bin/env bash
# Script de Instalação do FortiClient VPN GUI para Linux (Ubuntu / Debian / Fedora / Arch)

set -e

GREEN="\033[1;32m"
BLUE="\033[1;34m"
YELLOW="\033[1;33m"
RESET="\033[0m"

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

echo -e "${BLUE}======================================================${RESET}"
echo -e "${BLUE}   Instalador do FortiClient VPN GUI para Linux       ${RESET}"
echo -e "${BLUE}======================================================${RESET}"

# 1. Instalar dependências necessárias
echo -e "\n${YELLOW}[1/4] Verificando e instalando dependências...${RESET}"
if command -v apt-get &> /dev/null; then
    sudo apt-get update -qq
    sudo apt-get install -y strongswan strongswan-swanctl charon-systemd libstrongswan-extra-plugins libcharon-extra-plugins python3-tk python3-pil python3-pil.imagetk curl
elif command -v dnf &> /dev/null; then
    sudo dnf install -y strongswan python3-tkinter python3-pillow curl
elif command -v pacman &> /dev/null; then
    sudo pacman -Sy --noconfirm strongswan tk python-pillow curl
fi

# 2. Copiar aplicativo, inicializador e assets
echo -e "\n${YELLOW}[2/5] Instalando executáveis e recursos do sistema...${RESET}"
sudo mkdir -p /usr/share/forticlient-vpn/assets
sudo cp -r "$DIR/assets/"* /usr/share/forticlient-vpn/assets/
sudo cp "$DIR/vpn-gui.py" /usr/share/forticlient-vpn/vpn-gui.py
sudo cp "$DIR/iniciar_linux.sh" /usr/share/forticlient-vpn/iniciar_linux.sh
sudo chmod +x /usr/share/forticlient-vpn/vpn-gui.py /usr/share/forticlient-vpn/iniciar_linux.sh

sudo ln -sf /usr/share/forticlient-vpn/iniciar_linux.sh /usr/local/bin/forticlient-vpn
sudo ln -sf /usr/share/forticlient-vpn/iniciar_linux.sh /usr/local/bin/vpn-gui

# Instalar ícone oficial DTIC
sudo cp "$DIR/assets/icon.png" /usr/share/pixmaps/forticlient-vpn.png 2>/dev/null || true
sudo mkdir -p /usr/share/icons/hicolor/256x256/apps/
sudo cp "$DIR/assets/icon.png" /usr/share/icons/hicolor/256x256/apps/forticlient-vpn.png 2>/dev/null || true

# 3. Configurar permissões sudoers anti-interferência
echo -e "\n${YELLOW}[3/5] Configurando regras sudoers anti-interferência (/etc/sudoers.d/forticlient-vpn)...${RESET}"
sudo mkdir -p /etc/sudoers.d
TMP_SUDOERS=$(mktemp)
cat << 'EOF_SUDO' > "$TMP_SUDOERS"
# FortiClient VPN - Regras especificas de rede para conexao corporativa
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

if command -v visudo >/dev/null 2>&1; then
    visudo -cf "$TMP_SUDOERS" >/dev/null 2>&1 && sudo cp "$TMP_SUDOERS" /etc/sudoers.d/forticlient-vpn
else
    sudo cp "$TMP_SUDOERS" /etc/sudoers.d/forticlient-vpn
fi
rm -f "$TMP_SUDOERS"
sudo chown root:root /etc/sudoers.d/forticlient-vpn
sudo chmod 0440 /etc/sudoers.d/forticlient-vpn

# 4. Configurar diretório swanctl
echo -e "\n${YELLOW}[4/5] Verificando configuração em /etc/swanctl/conf.d/...${RESET}"
sudo mkdir -p /etc/swanctl/conf.d/
if [ ! -f /etc/swanctl/conf.d/forti.conf ]; then
    echo -e "Criando /etc/swanctl/conf.d/forti.conf a partir do modelo..."
    sudo cp config/forti.conf.example /etc/swanctl/conf.d/forti.conf
    sudo chmod 600 /etc/swanctl/conf.d/forti.conf
else
    echo -e "Arquivo /etc/swanctl/conf.d/forti.conf já existe. Mantido."
fi

# 5. Instalar atalhos gráficos
echo -e "\n${YELLOW}[5/5] Instalando atalhos gráficos (Desktop e Menu de Aplicativos)...${RESET}"
mkdir -p "$HOME/.local/share/applications"
cp assets/forticlient-vpn.desktop "$HOME/.local/share/applications/"
chmod +x "$HOME/.local/share/applications/forticlient-vpn.desktop"

DESKTOP_DIR="$HOME/Área de trabalho"
if [ ! -d "$DESKTOP_DIR" ]; then
    DESKTOP_DIR="$HOME/Desktop"
fi
if [ -d "$DESKTOP_DIR" ]; then
    cp assets/forticlient-vpn.desktop "$DESKTOP_DIR/FortiClient-VPN.desktop"
    chmod +x "$DESKTOP_DIR/FortiClient-VPN.desktop"
    gio set "$DESKTOP_DIR/FortiClient-VPN.desktop" metadata::trusted true 2>/dev/null || true
fi

# Habilitar serviço strongSwan
sudo systemctl enable --now strongswan-starter.service 2>/dev/null || sudo systemctl enable --now strongswan.service 2>/dev/null || true
sudo swanctl --load-all >/dev/null 2>&1 || true

echo -e "\n${GREEN}======================================================${RESET}"
echo -e "${GREEN}        Instalação concluída com sucesso!             ${RESET}"
echo -e "${GREEN}======================================================${RESET}"
echo -e "Você já pode abrir o aplicativo:"
echo -e "  • Pelo atalho na Área de Trabalho: ${YELLOW}FortiClient VPN${RESET}"
echo -e "  • Pelo terminal: ${YELLOW}vpn-gui${RESET} ou ${YELLOW}python3 vpn-gui.py${RESET}"
echo ""
