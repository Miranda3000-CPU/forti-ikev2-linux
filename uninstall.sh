#!/usr/bin/env bash
# Script de Desinstalação do FortiClient VPN GUI para Linux

set -e

RED="\033[1;31m"
GREEN="\033[1;32m"
YELLOW="\033[1;33m"
RESET="\033[0m"

echo -e "${RED}======================================================${RESET}"
echo -e "${RED}   Desinstalador do FortiClient VPN GUI (Linux)       ${RESET}"
echo -e "${RED}======================================================${RESET}"

# Encerrar VPN se estiver ativa
if sudo swanctl --list-sas 2>/dev/null | grep -q "ESTABLISHED"; then
    echo -e "${YELLOW}[*] Encerrando túnel VPN ativo...${RESET}"
    sudo swanctl --terminate --ike forticlient 2>/dev/null || true
fi

# Remover binário e diretórios
echo -e "${YELLOW}[*] Removendo executáveis e recursos do sistema...${RESET}"
sudo rm -f /usr/local/bin/vpn-gui /usr/local/bin/forticlient-vpn
sudo rm -rf /usr/share/forticlient-vpn
sudo rm -f /usr/share/pixmaps/forticlient-vpn.png /usr/share/icons/hicolor/256x256/apps/forticlient-vpn.png

# Remover atalhos
echo -e "${YELLOW}[*] Removendo atalhos do desktop...${RESET}"
rm -f "$HOME/.local/share/applications/forticlient-vpn.desktop"
rm -f "$HOME/Área de trabalho/FortiClient-VPN.desktop"
rm -f "$HOME/Desktop/FortiClient-VPN.desktop"

read -p "Deseja remover também as configurações (/etc/swanctl/conf.d/forti.conf)? (s/N): " resp
if [[ "$resp" =~ ^[sS]$ ]]; then
    sudo rm -f /etc/swanctl/conf.d/forti.conf
    echo -e "${YELLOW}[*] Configurações removidas.${RESET}"
else
    echo -e "${GREEN}[*] Configurações mantidas em /etc/swanctl/conf.d/forti.conf.${RESET}"
fi

echo -e "\n${GREEN}[✓] Desinstalação concluída com sucesso.${RESET}\n"
