#!/usr/bin/env bash
# Instala o FortiClient VPN a partir do código, sem empacotar.
#
# Uso: sudo ./install.sh
#
# O caminho recomendado para usuários finais é o .deb (build/build_deb.sh);
# este script existe para instalar direto da árvore de trabalho.
set -euo pipefail

GREEN="\033[1;32m"
YELLOW="\033[1;33m"
RESET="\033[0m"

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

PKG_NAME="forticlient-vpn"
SHARE_DIR="/usr/share/${PKG_NAME}"

echo -e "${YELLOW}Instalando dependências...${RESET}"
if command -v apt-get &> /dev/null; then
    sudo apt-get update -qq
    sudo apt-get install -y strongswan strongswan-swanctl python3-tk python3-pil python3-pil.imagetk
else
    echo "aviso: sem apt-get; assumindo que strongswan, swanctl e python3-tk já estão instalados." >&2
fi

# ─────────────────────────────────────────── versão
# build_info.py é gerado e não versionado (ver .gitignore). Sem ele o aplicativo
# reporta a versão como "dev" e não dá para saber o que está instalado.
if [ ! -f "$DIR/build_info.py" ]; then
    echo -e "${YELLOW}Gerando build_info.py...${RESET}"
    python3 "$DIR/build/gen_build_info.py"
fi

# ─────────────────────────────────────────── arquivos
echo -e "${YELLOW}Copiando arquivos...${RESET}"
sudo mkdir -p "$SHARE_DIR/assets" "$SHARE_DIR/config"
sudo cp -r "$DIR/assets/." "$SHARE_DIR/assets/"
sudo cp "$DIR/vpn-gui.py" "$DIR/vpn_engine.py" "$DIR/vpn_config.py" "$DIR/build_info.py" "$SHARE_DIR/"
sudo cp "$DIR/iniciar_linux.sh" "$SHARE_DIR/iniciar_linux.sh"
sudo cp "$DIR/config/forti.conf.example" "$SHARE_DIR/config/" 2>/dev/null || true
sudo chmod +x "$SHARE_DIR/vpn-gui.py" "$SHARE_DIR/iniciar_linux.sh"
sudo chmod 644 "$SHARE_DIR/vpn_engine.py" "$SHARE_DIR/vpn_config.py" "$SHARE_DIR/build_info.py"

# Licenças: quem instala precisa saber que pode redistribuir/modificar, e que o
# strongSwan embarcado no Windows é GPLv2.
sudo mkdir -p "/usr/share/doc/${PKG_NAME}"
for doc in LICENSE NOTICE SOURCE-OFFER.txt; do
    if [ -f "$DIR/$doc" ]; then
        sudo cp "$DIR/$doc" "/usr/share/doc/${PKG_NAME}/"
    fi
done
sudo chmod -R a+rX "/usr/share/doc/${PKG_NAME}"

sudo ln -sf "$SHARE_DIR/iniciar_linux.sh" /usr/local/bin/forticlient-vpn

# ─────────────────────────────────────────── atalho e ícone
# O .desktop declara `Icon=forticlient-vpn`; sem o ícone nos temas do sistema o
# atalho aparece genérico. Instalar em hicolor (tema padrão) e em pixmaps
# (compatibilidade) resolve. Sem o 256x256, o hicolor não acha o ícone.
echo -e "${YELLOW}Criando atalho...${RESET}"
sudo install -m 0644 "$DIR/assets/icon.png" /usr/share/icons/hicolor/256x256/apps/${PKG_NAME}.png
sudo install -m 0644 "$DIR/assets/icon.png" /usr/share/pixmaps/${PKG_NAME}.png
sudo install -m 0644 "$DIR/assets/forticlient-vpn.desktop" /usr/share/applications/${PKG_NAME}.desktop
sudo gtk-update-icon-cache -f /usr/share/icons/hicolor 2>/dev/null || true
update-desktop-database /usr/share/applications 2>/dev/null || true

# ─────────────────────────────────────────── sudoers
echo -e "${YELLOW}Configurando sudoers...${RESET}"
sudo mkdir -p /etc/sudoers.d
TMP_SUDOERS=$(mktemp)
cat << 'EOF' > "$TMP_SUDOERS"
ALL ALL=(root) NOPASSWD: /usr/sbin/swanctl --load-all
ALL ALL=(root) NOPASSWD: /usr/sbin/swanctl --list-sas
ALL ALL=(root) NOPASSWD: /usr/sbin/swanctl --list-conns
ALL ALL=(root) NOPASSWD: /usr/sbin/swanctl --initiate --child forticlient
ALL ALL=(root) NOPASSWD: /usr/sbin/swanctl --terminate --ike forticlient
ALL ALL=(root) NOPASSWD: /usr/bin/tee /etc/swanctl/conf.d/forti.conf
ALL ALL=(root) NOPASSWD: /usr/bin/chmod 600 /etc/swanctl/conf.d/forti.conf
ALL ALL=(root) NOPASSWD: /usr/bin/mkdir -p /etc/swanctl/conf.d
ALL ALL=(root) NOPASSWD: /bin/systemctl start strongswan-starter.service
ALL ALL=(root) NOPASSWD: /usr/bin/systemctl start strongswan-starter.service
ALL ALL=(root) NOPASSWD: /bin/systemctl start strongswan.service
ALL ALL=(root) NOPASSWD: /usr/bin/systemctl start strongswan.service
ALL ALL=(root) NOPASSWD: /sbin/ip rule add lookup 220 pref 220
ALL ALL=(root) NOPASSWD: /usr/sbin/ip rule add lookup 220 pref 220
EOF
sudo cp "$TMP_SUDOERS" /etc/sudoers.d/forticlient-vpn
rm -f "$TMP_SUDOERS"
sudo chown root:root /etc/sudoers.d/forticlient-vpn
sudo chmod 0440 /etc/sudoers.d/forticlient-vpn

echo -e "${GREEN}Instalação concluída!${RESET}"
echo "Abra 'FortiClient VPN' no menu de aplicativos ou rode: forticlient-vpn"
