#!/usr/bin/env bash
# Script para gerar pacote Debian (.deb) do FortiClient VPN Manager
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

VERSION="1.0.0"
PKG_NAME="forticlient-vpn"
ARCH="all"
DEB_NAME="${PKG_NAME}_${VERSION}_${ARCH}.deb"
BUILD_ROOT="build/deb"

echo "========================================================"
echo "  Gerador de Pacote .deb - FortiClient VPN Manager      "
echo "========================================================"
echo ""

# 1. Garantir que os ícones circulares estão gerados
echo "[*] Verificando ícones circulares DTIC..."
python3 - << 'EOF'
from PIL import Image, ImageDraw, ImageOps
import os

src = "assets/dtic-logo-whasapp.jpeg"
if os.path.exists(src):
    img = Image.open(src).convert("RGBA")
    w, h = img.size
    m = min(w, h)
    c = img.crop(((w-m)//2, (h-m)//2, (w-m)//2+m, (h-m)//2+m))
    scale = 4
    mask = Image.new("L", (m*scale, m*scale), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, m*scale, m*scale), fill=255)
    mask = mask.resize((m, m), Image.Resampling.LANCZOS)
    c.putalpha(mask)
    c.save("assets/icon.png", "PNG")
    c.save("assets/icon.ico", format="ICO", sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])
    print("  -> Ícones redondos atualizados.")
EOF

# 2. Limpar diretórios anteriores
rm -rf "$BUILD_ROOT"
mkdir -p "$BUILD_ROOT/DEBIAN"
mkdir -p "$BUILD_ROOT/usr/bin"
mkdir -p "$BUILD_ROOT/usr/share/$PKG_NAME/assets"
mkdir -p "$BUILD_ROOT/usr/share/applications"
mkdir -p "$BUILD_ROOT/usr/share/pixmaps"
mkdir -p "$BUILD_ROOT/usr/share/icons/hicolor/256x256/apps"
mkdir -p "$BUILD_ROOT/etc/sudoers.d"
mkdir -p "dist"

# 3. Arquivo DEBIAN/control
cat << 'EOF' > "$BUILD_ROOT/DEBIAN/control"
Package: forticlient-vpn
Version: 1.0.0
Section: net
Priority: optional
Architecture: all
Maintainer: DTIC Bombeiros <dtic@bombeiros.pa.gov.br>
Depends: strongswan, strongswan-swanctl, libcharon-extra-plugins, python3, python3-tk, python3-pil, python3-pil.imagetk
Description: FortiClient IKEv2 VPN Manager GUI
 Interface Grafica nativa em Python/Tkinter para gerenciamento e conexao
 a VPNs corporativas FortiGate utilizando protocolo IKEv2 / IPsec com EAP-MSCHAPv2.
 Inclui icone oficial DTIC e suporte a rotas e painel Web interno.
EOF

# 4. Script DEBIAN/postinst
cat << 'EOF' > "$BUILD_ROOT/DEBIAN/postinst"
#!/bin/sh
set -e

chmod 755 /usr/bin/forticlient-vpn
chmod 755 /usr/share/forticlient-vpn/vpn-gui.py
chmod 440 /etc/sudoers.d/forticlient-vpn 2>/dev/null || true

# Atualizar caches de ícone e desktop
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database /usr/share/applications || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -f -t /usr/share/icons/hicolor || true
fi

# Habilitar o serviço do strongSwan
systemctl enable --now strongswan-starter.service 2>/dev/null || systemctl enable --now strongswan.service 2>/dev/null || true

echo "FortiClient VPN instalado com sucesso!"
echo "Execute 'forticlient-vpn' ou localize no menu de aplicativos."
exit 0
EOF
chmod 755 "$BUILD_ROOT/DEBIAN/postinst"

# 5. Script DEBIAN/prerm
cat << 'EOF' > "$BUILD_ROOT/DEBIAN/prerm"
#!/bin/sh
set -e

# Desconectar conexões ativas se existirem
swanctl --terminate --ike forticlient >/dev/null 2>&1 || true
exit 0
EOF
chmod 755 "$BUILD_ROOT/DEBIAN/prerm"

# 6. Executável wrapper /usr/bin/forticlient-vpn
cat << 'EOF' > "$BUILD_ROOT/usr/bin/forticlient-vpn"
#!/usr/bin/env bash
exec /usr/bin/python3 /usr/share/forticlient-vpn/vpn-gui.py "$@"
EOF
chmod 755 "$BUILD_ROOT/usr/bin/forticlient-vpn"

# 7. Copiar aplicação e assets
cp vpn-gui.py "$BUILD_ROOT/usr/share/$PKG_NAME/"
chmod 755 "$BUILD_ROOT/usr/share/$PKG_NAME/vpn-gui.py"

cp -r assets/* "$BUILD_ROOT/usr/share/$PKG_NAME/assets/"
cp assets/icon.png "$BUILD_ROOT/usr/share/pixmaps/forticlient-vpn.png"
cp assets/icon.png "$BUILD_ROOT/usr/share/icons/hicolor/256x256/apps/forticlient-vpn.png"

# 8. Copiar desktop entry com o novo ícone oficial
cat << 'EOF' > "$BUILD_ROOT/usr/share/applications/forticlient-vpn.desktop"
[Desktop Entry]
Version=1.0
Type=Application
Name=FortiClient VPN
Comment=Gerenciador FortiClient VPN IKEv2 (DTIC)
Exec=forticlient-vpn
Icon=forticlient-vpn
Terminal=false
Categories=Network;Security;
Keywords=vpn;fortinet;forticlient;ikev2;ipsec;dtic;
StartupWMClass=FortiClient VPN
EOF
chmod 644 "$BUILD_ROOT/usr/share/applications/forticlient-vpn.desktop"

# 9. Configuração de sudoers sem senha para swanctl e ip rule
cat << 'EOF' > "$BUILD_ROOT/etc/sudoers.d/forticlient-vpn"
ALL ALL=(ALL) NOPASSWD: /usr/sbin/swanctl, /usr/bin/swanctl, /sbin/ip rule *, /bin/ip rule *, /usr/bin/tee /etc/swanctl/conf.d/forti.conf, /usr/bin/chmod 600 /etc/swanctl/conf.d/forti.conf
EOF
chmod 440 "$BUILD_ROOT/etc/sudoers.d/forticlient-vpn"

# 10. Empacotar via dpkg-deb
echo "[*] Empacotando com dpkg-deb..."
dpkg-deb --build --root-owner-group "$BUILD_ROOT" "dist/$DEB_NAME"

echo ""
echo "========================================================"
echo "  [SUCESSO] Pacote Debian criado com sucesso!"
echo "========================================================"
echo "Arquivo gerado: dist/$DEB_NAME"
echo ""
echo "Para instalar no Ubuntu/Debian:"
echo "  sudo apt install ./dist/$DEB_NAME"
echo ""
