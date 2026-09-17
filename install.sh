#!/usr/bin/env bash
# Script de Instalação do FortiClient VPN Manager para Linux (Ubuntu / Debian)

set -e

GREEN="\033[1;32m"
BLUE="\033[1;34m"
YELLOW="\033[1;33m"
RESET="\033[0m"

echo -e "${BLUE}======================================================${RESET}"
echo -e "${BLUE}    Instalador do FortiClient VPN Manager (Linux)     ${RESET}"
echo -e "${BLUE}======================================================${RESET}"

# 1. Instalar dependências necessárias
echo -e "\n${YELLOW}[1/5] Verificando e instalando dependências do sistema...${RESET}"
sudo apt-get update -qq
sudo apt-get install -y strongswan strongswan-swanctl charon-systemd libstrongswan-extra-plugins libcharon-extra-plugins python3-tk curl

# 2. Copiar scripts para /usr/local/bin
echo -e "\n${YELLOW}[2/5] Instalando utilitários executáveis em /usr/local/bin...${RESET}"
sudo cp bin/vpn /usr/local/bin/vpn
sudo cp bin/vpn-gui /usr/local/bin/vpn-gui
sudo chmod +x /usr/local/bin/vpn /usr/local/bin/vpn-gui

# 3. Configurar diretório de configuração do swanctl
echo -e "\n${YELLOW}[3/5] Verificando configuração em /etc/swanctl/conf.d/...${RESET}"
sudo mkdir -p /etc/swanctl/conf.d/
if [ ! -f /etc/swanctl/conf.d/forti.conf ]; then
    echo -e "Criando arquivo base /etc/swanctl/conf.d/forti.conf a partir do modelo..."
    sudo cp config/forti.conf.example /etc/swanctl/conf.d/forti.conf
    sudo chmod 600 /etc/swanctl/conf.d/forti.conf
else
    echo -e "Arquivo /etc/swanctl/conf.d/forti.conf já existe. Preservado."
fi

# 4. Instalar atalhos de Desktop
echo -e "\n${YELLOW}[4/5] Instalando atalhos gráficos (Desktop e Menu de Aplicativos)...${RESET}"
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

# 5. Iniciar / Habilitar o serviço do strongSwan
echo -e "\n${YELLOW}[5/5] Iniciando serviço do strongSwan swanctl...${RESET}"
sudo systemctl enable --now strongswan-starter.service 2>/dev/null || sudo systemctl enable --now strongswan.service 2>/dev/null || true
sudo swanctl --load-all >/dev/null 2>&1 || true

echo -e "\n${GREEN}======================================================${RESET}"
echo -e "${GREEN}        Instalação concluída com sucesso!             ${RESET}"
echo -e "${GREEN}======================================================${RESET}"
echo -e "Você já pode utilizar:"
echo -e "  • Interface Gráfica : execute ${YELLOW}vpn-gui${RESET} ou clique no atalho na Área de Trabalho"
echo -e "  • Linha de Comando  : execute ${YELLOW}vpn connect${RESET}, ${YELLOW}vpn status${RESET}, ${YELLOW}vpn test${RESET}"
echo ""
