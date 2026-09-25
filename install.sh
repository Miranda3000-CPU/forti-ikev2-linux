#!/usr/bin/env bash
set -e

GREEN="\033[1;32m"
YELLOW="\033[1;33m"
RESET="\033[0m"

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

echo -e "${YELLOW}Instalando dependências...${RESET}"
if command -v apt-get &> /dev/null; then
    sudo apt-get update -qq
    sudo apt-get install -y strongswan strongswan-swanctl python3-tk python3-pil python3-pil.imagetk
fi

echo -e "${YELLOW}Copiando arquivos...${RESET}"
sudo mkdir -p /usr/share/forticlient-vpn/assets
sudo cp -r "$DIR/assets/"* /usr/share/forticlient-vpn/assets/ 2>/dev/null || true
sudo cp "$DIR/vpn-gui.py" "$DIR/vpn_engine.py" "$DIR/vpn_config.py" /usr/share/forticlient-vpn/
sudo cp "$DIR/iniciar_linux.sh" /usr/share/forticlient-vpn/iniciar_linux.sh
sudo chmod +x /usr/share/forticlient-vpn/vpn-gui.py /usr/share/forticlient-vpn/iniciar_linux.sh
sudo chmod 644 /usr/share/forticlient-vpn/vpn_engine.py /usr/share/forticlient-vpn/vpn_config.py

sudo ln -sf /usr/share/forticlient-vpn/iniciar_linux.sh /usr/local/bin/forticlient-vpn

echo -e "${YELLOW}Configurando sudoers...${RESET}"
sudo mkdir -p /etc/sudoers.d
TMP_SUDOERS=$(mktemp)
cat << 'EOF' > "$TMP_SUDOERS"
ALL ALL=(root) NOPASSWD: /usr/sbin/swanctl --load-all
ALL ALL=(root) NOPASSWD: /usr/sbin/swanctl --list-sas
ALL ALL=(root) NOPASSWD: /usr/sbin/swanctl --initiate --child forticlient
ALL ALL=(root) NOPASSWD: /usr/sbin/swanctl --terminate --ike forticlient
ALL ALL=(root) NOPASSWD: /usr/bin/tee /etc/swanctl/conf.d/forti.conf
ALL ALL=(root) NOPASSWD: /usr/bin/chmod 600 /etc/swanctl/conf.d/forti.conf
ALL ALL=(root) NOPASSWD: /usr/bin/mkdir -p /etc/swanctl/conf.d
ALL ALL=(root) NOPASSWD: /bin/systemctl start strongswan-starter.service
ALL ALL=(root) NOPASSWD: /usr/bin/systemctl start strongswan-starter.service
ALL ALL=(root) NOPASSWD: /bin/systemctl start strongswan.service
ALL ALL=(root) NOPASSWD: /usr/bin/systemctl start strongswan.service
ALL ALL=(root) NOPASSWD: /usr/sbin/ip rule add lookup 220 pref 220
ALL ALL=(root) NOPASSWD: /sbin/ip rule add lookup 220 pref 220
EOF
sudo cp "$TMP_SUDOERS" /etc/sudoers.d/forticlient-vpn
rm -f "$TMP_SUDOERS"
sudo chown root:root /etc/sudoers.d/forticlient-vpn
sudo chmod 0440 /etc/sudoers.d/forticlient-vpn

echo -e "${YELLOW}Criando atalho...${RESET}"
mkdir -p "$HOME/.local/share/applications"
cp assets/forticlient-vpn.desktop "$HOME/.local/share/applications/" 2>/dev/null || true
if [ -f "$HOME/.local/share/applications/forticlient-vpn.desktop" ]; then
    chmod +x "$HOME/.local/share/applications/forticlient-vpn.desktop"
fi

echo -e "${GREEN}Instalação concluída!${RESET}"
