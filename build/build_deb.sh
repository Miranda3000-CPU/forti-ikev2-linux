#!/usr/bin/env bash
# Gera o pacote Debian/Ubuntu (.deb) do FortiClient VPN.
# Uso: ./build/build_deb.sh

set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$DIR"

PKG_NAME="forticlient-vpn"
ARCH="all"
BUILD_DIR="build/deb"
DOC_DIR="${BUILD_DIR}/DEBIAN"
SHARE_DIR="/usr/share/${PKG_NAME}"

command -v dpkg-deb >/dev/null 2>&1 || {
    echo "erro: dpkg-deb não encontrado (instale o pacote 'dpkg')." >&2
    exit 1
}

# Versão do software
if [ ! -f "VERSION" ]; then
    echo "2.1.4" > VERSION
fi
VERSION="$(cat VERSION | tr -d '[:space:]')"
echo "Construindo pacote para versão: ${VERSION}"

# Limpeza e preparação da estrutura de diretórios
rm -rf "$BUILD_DIR"
mkdir -p "$DOC_DIR" \
         "$BUILD_DIR/usr/bin" \
         "$BUILD_DIR${SHARE_DIR}/assets" \
         "$BUILD_DIR/usr/share/applications" \
         "$BUILD_DIR/usr/share/icons/hicolor/256x256/apps" \
         "$BUILD_DIR/usr/share/pixmaps" \
         "$BUILD_DIR/usr/share/doc/${PKG_NAME}"

# Metadados de controle do pacote
cp debian/control "$DOC_DIR/control"
cp debian/postinst "$DOC_DIR/postinst"
cp debian/prerm "$DOC_DIR/prerm"
cp debian/postrm "$DOC_DIR/postrm"
cp debian/changelog "$DOC_DIR/changelog"
cp debian/copyright "$DOC_DIR/copyright"

chmod 0755 "$DOC_DIR" "$DOC_DIR/postinst" "$DOC_DIR/prerm" "$DOC_DIR/postrm"
chmod 0644 "$DOC_DIR/changelog" "$DOC_DIR/copyright"

# Código da aplicação
cp vpn-gui.py vpn_engine.py vpn_config.py "$BUILD_DIR${SHARE_DIR}/"
if [ -f "build_info.py" ]; then
    cp build_info.py "$BUILD_DIR${SHARE_DIR}/"
else
    echo "VERSION = '${VERSION}'" > "$BUILD_DIR${SHARE_DIR}/build_info.py"
fi
[ -f requirements.txt ] && cp requirements.txt "$BUILD_DIR${SHARE_DIR}/"

# Assets e ícones
cp assets/icon.png "$BUILD_DIR/usr/share/icons/hicolor/256x256/apps/${PKG_NAME}.png"
cp assets/icon.png "$BUILD_DIR/usr/share/pixmaps/${PKG_NAME}.png"
cp assets/forticlient-vpn.desktop "$BUILD_DIR/usr/share/applications/${PKG_NAME}.desktop"
cp assets/* "$BUILD_DIR${SHARE_DIR}/assets/" 2>/dev/null || true

# Documentação
for doc in LICENSE NOTICE README.md CHANGELOG.md; do
    [ -f "$doc" ] && cp "$doc" "$BUILD_DIR/usr/share/doc/${PKG_NAME}/"
done

# Launcher executável em /usr/bin/forticlient-vpn
cat << 'EOF' > "$BUILD_DIR/usr/bin/forticlient-vpn"
#!/bin/sh
exec /usr/bin/python3 /usr/share/forticlient-vpn/vpn-gui.py "$@"
EOF
chmod 0755 "$BUILD_DIR/usr/bin/forticlient-vpn"

# Permissões
find "$BUILD_DIR/usr" -type f -exec chmod 0644 {} +
chmod 0755 "$BUILD_DIR/usr/bin/forticlient-vpn" "$BUILD_DIR${SHARE_DIR}/vpn-gui.py"

# Geração de MD5
( cd "$BUILD_DIR" && find usr -type f -printf '%p\0' | xargs -0 md5sum ) > "$DOC_DIR/md5sums"

# Build final
mkdir -p dist
OUT="dist/${PKG_NAME}_${VERSION}_${ARCH}.deb"
echo "Gerando pacote Debian: $OUT ..."
dpkg-deb --root-owner-group --build "$BUILD_DIR" "$OUT"

echo "✓ Pacote gerado com sucesso: $OUT"
