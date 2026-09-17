#!/usr/bin/env bash
# Script de Desinstalação do FortiClient VPN Container

set -e

RED="\033[1;31m"
GREEN="\033[1;32m"
YELLOW="\033[1;33m"
RESET="\033[0m"

echo -e "${RED}======================================================${RESET}"
echo -e "${RED} Desinstalador do FortiClient VPN Container (Linux)   ${RESET}"
echo -e "${RED}======================================================${RESET}"

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

# Parar container se estiver rodando
echo -e "${YELLOW}[*] Parando container caso esteja ativo...${RESET}"
docker compose down 2>/dev/null || true

# Remover link global
echo -e "${YELLOW}[*] Removendo comando /usr/local/bin/vpn-gui...${RESET}"
sudo rm -f /usr/local/bin/vpn-gui

# Remover atalhos
echo -e "${YELLOW}[*] Removendo atalhos do desktop...${RESET}"
rm -f "$HOME/.local/share/applications/forticlient-vpn.desktop"
rm -f "$HOME/Área de trabalho/FortiClient-VPN.desktop"
rm -f "$HOME/Desktop/FortiClient-VPN.desktop"

read -p "Deseja remover também a imagem Docker construída? (s/N): " resp
if [[ "$resp" =~ ^[sS]$ ]]; then
    docker rmi -f forticlient-vpn-gui:latest 2>/dev/null || true
    echo -e "${YELLOW}[*] Imagem Docker removida.${RESET}"
fi

echo -e "\n${GREEN}[✓] Desinstalação concluída.${RESET}\n"
