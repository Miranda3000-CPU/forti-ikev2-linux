#!/bin/bash
# Script para gerar pacote .deb do FortiClient VPN
# Uso: ./build/build_deb.sh
#
# Requer: dpkg-deb, fakeroot
#
# Gera: dist/forticlient-vpn_1.0.0_amd64.deb

set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$DIR"

VERSION="1.0.0"
PKG_NAME="forticlient-vpn"
ARCH="amd64"
DEB_DIR="/tmp/${PKG_NAME}-deb"

echo "Preparando estrutura em $DEB_DIR..."
rm -rf "$DEB_DIR"
mkdir -p "$DEB_DIR/DEBIAN"
mkdir -p "$DEB_DIR/usr/share/${PKG_NAME}/assets"
mkdir -p "$DEB_DIR/usr/share/${PKG_NAME}/config"
mkdir -p "$DEB_DIR/usr/share/applications"
mkdir -p "$DEB_DIR/usr/bin"

cp debian/control "$DEB_DIR/DEBIAN/control"
cp debian/postinst "$DEB_DIR/DEBIAN/postinst"
cp debian/prerm "$DEB_DIR/DEBIAN/prerm"
chmod 0755 "$DEB_DIR/DEBIAN/postinst"
chmod 0755 "$DEB_DIR/DEBIAN/prerm"

cp vpn-gui.py vpn_engine.py vpn_config.py "$DEB_DIR/usr/share/${PKG_NAME}/"
cp requirements.txt "$DEB_DIR/usr/share/${PKG_NAME}/" 2>/dev/null || true
cp -r assets/* "$DEB_DIR/usr/share/${PKG_NAME}/assets/"
cp config/forti.conf.example "$DEB_DIR/usr/share/${PKG_NAME}/config/" 2>/dev/null || true
cp assets/forticlient-vpn.desktop "$DEB_DIR/usr/share/applications/" 2>/dev/null || true

cat << 'EOF' > "$DEB_DIR/usr/bin/${PKG_NAME}"
#!/bin/bash
exec python3 /usr/share/forticlient-vpn/vpn-gui.py "$@"
EOF
chmod 0755 "$DEB_DIR/usr/bin/${PKG_NAME}"
# Módulos precisam ser legíveis pelo usuário que executa o app.
chmod 0755 "$DEB_DIR/usr/share/${PKG_NAME}/vpn-gui.py"
chmod 0644 "$DEB_DIR/usr/share/${PKG_NAME}/vpn_engine.py" "$DEB_DIR/usr/share/${PKG_NAME}/vpn_config.py"

echo "Construindo pacote..."
mkdir -p dist
dpkg-deb --root-owner-group --build "$DEB_DIR" "dist/${PKG_NAME}_${VERSION}_${ARCH}.deb"

echo "Pacote gerado: dist/${PKG_NAME}_${VERSION}_${ARCH}.deb"
