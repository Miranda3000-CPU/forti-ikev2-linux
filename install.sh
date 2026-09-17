#!/usr/bin/env bash
# Script de Instalação do FortiClient VPN Container para Linux (Ubuntu / Debian / Fedora / Arch)

set -e

GREEN="\033[1;32m"
BLUE="\033[1;34m"
YELLOW="\033[1;33m"
RED="\033[1;31m"
RESET="\033[0m"

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

echo -e "${BLUE}======================================================${RESET}"
echo -e "${BLUE}   Instalador FortiClient VPN Container (GUI & Web)   ${RESET}"
echo -e "${BLUE}======================================================${RESET}"

# 1. Verificar Docker
echo -e "\n${YELLOW}[1/4] Verificando Docker no sistema...${RESET}"
if ! command -v docker &> /dev/null; then
    echo -e "${RED}[✗] Docker não encontrado. Por favor, instale o Docker primeiro.${RESET}"
    exit 1
fi
echo -e "${GREEN}[✓] Docker encontrado: $(docker --version)${RESET}"

# 2. Configurar arquivo de credenciais
echo -e "\n${YELLOW}[2/4] Preparando configuração local (config/forti.conf)...${RESET}"
mkdir -p config
if [ ! -f config/forti.conf ]; then
    if [ -f /etc/swanctl/conf.d/forti.conf ]; then
        echo -e "Importando configuração existente do host..."
        sudo cp /etc/swanctl/conf.d/forti.conf config/forti.conf
        sudo chown $(id -u):$(id -g) config/forti.conf
    else
        echo -e "Criando config/forti.conf a partir do modelo..."
        cp config/forti.conf.example config/forti.conf
    fi
    chmod 600 config/forti.conf
fi

# 3. Construir imagem Docker
echo -e "\n${YELLOW}[3/4] Construindo imagem Docker (forticlient-vpn-gui)...${RESET}"
docker compose build

# 4. Criar atalhos e utilitário global
echo -e "\n${YELLOW}[4/4] Instalando atalho na Área de Trabalho e comando global...${RESET}"
sudo ln -sf "$DIR/run.sh" /usr/local/bin/vpn-gui
sudo chmod +x /usr/local/bin/vpn-gui

mkdir -p "$HOME/.local/share/applications"
sed "s|/home/jeiel/forticlient-vpn-linux|$DIR|g" assets/forticlient-vpn.desktop > "$HOME/.local/share/applications/forticlient-vpn.desktop"
chmod +x "$HOME/.local/share/applications/forticlient-vpn.desktop"

DESKTOP_DIR="$HOME/Área de trabalho"
if [ ! -d "$DESKTOP_DIR" ]; then
    DESKTOP_DIR="$HOME/Desktop"
fi
if [ -d "$DESKTOP_DIR" ]; then
    cp "$HOME/.local/share/applications/forticlient-vpn.desktop" "$DESKTOP_DIR/FortiClient-VPN.desktop"
    chmod +x "$DESKTOP_DIR/FortiClient-VPN.desktop"
    gio set "$DESKTOP_DIR/FortiClient-VPN.desktop" metadata::trusted true 2>/dev/null || true
fi

echo -e "\n${GREEN}======================================================${RESET}"
echo -e "${GREEN}        Instalação concluída com sucesso!             ${RESET}"
echo -e "${GREEN}======================================================${RESET}"
echo -e "Você já pode executar o programa:"
echo -e "  • Pelo atalho na Área de Trabalho: ${YELLOW}FortiClient VPN${RESET}"
echo -e "  • Pelo terminal: ${YELLOW}vpn-gui${RESET} ou ${YELLOW}./run.sh${RESET}"
echo -e "  • Pelo Navegador: ${YELLOW}http://localhost:8080${RESET}"
echo ""
