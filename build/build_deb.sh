#!/bin/bash
# Gera o pacote .deb do FortiClient VPN.
# Uso: ./build/build_deb.sh
#
# Requer apenas: dpkg-deb (já faz parte do dpkg). Nada de fakeroot — o
# --root-owner-group atribui root:root sem precisar de privilégio.
#
# Gera: dist/forticlient-vpn_<versão>_all.deb
#
# A versão vem de ./VERSION (fonte única), propagada por gen_build_info.py
# para o .deb, para o instalador Windows e para o executável.

set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$DIR"

PKG_NAME="forticlient-vpn"
ARCH="all"            # o pacote é um script Python, não tem código compilado
BUILD_DIR="build/deb"        # raiz do pacote: DEBIAN/ e usr/ são irmãos
DOC_DIR="${BUILD_DIR}/DEBIAN"
SHARE_DIR="/usr/share/${PKG_NAME}"

command -v dpkg-deb >/dev/null 2>&1 || {
    echo "erro: dpkg-deb não encontrado (instale o pacote 'dpkg')." >&2
    exit 1
}

# ─────────────────────────────────────────── versão e metadados
echo "Gerando build_info.py (versão única a partir de ./VERSION)..."
python3 build/gen_build_info.py
VERSION="$(python3 -c 'import build_info; print(build_info.VERSION)')"
echo "Versão: $VERSION"

# A URL do repositório vem do remote git, para o pacote nunca apontar para um
# repositório inexistente. Só entering no pacote se vier de um host público
# (github.com): um remote interno (Gitea etc.) jamais pode vazar para um .deb.
# Cai para o campo Homepage já gravado em control.
PUBLIC_HOST_RE="^(https://github\.com/|git@github\.com:)"
REPO_URL="$(git remote get-url origin 2>/dev/null || true)"
REPO_URL="${REPO_URL%.git}"
if [[ "$REPO_URL" =~ $PUBLIC_HOST_RE ]]; then
    echo "Repositório: $REPO_URL"
else
    echo "aviso: remote não é um GitHub público; metadados ficam com o placeholder." >&2
    REPO_URL=""
fi

# ─────────────────────────────────────────── limpeza
rm -rf "$BUILD_DIR"
mkdir -p "$DOC_DIR" \
         "$BUILD_DIR/usr/bin" \
         "$BUILD_DIR/usr/share/${PKG_NAME}/assets" \
         "$BUILD_DIR/usr/share/${PKG_NAME}/config" \
         "$BUILD_DIR/usr/share/applications" \
         "$BUILD_DIR/usr/share/icons/hicolor/256x256/apps" \
         "$BUILD_DIR/usr/share/pixmaps" \
         "$BUILD_DIR/usr/share/doc/${PKG_NAME}"

# ─────────────────────────────────────────── metadados do pacote
cp debian/control "$DOC_DIR/control"
cp debian/postinst "$DOC_DIR/postinst"
cp debian/prerm "$DOC_DIR/prerm"
cp debian/postrm "$DOC_DIR/postrm"
cp debian/changelog "$DOC_DIR/changelog"
cp debian/copyright "$DOC_DIR/copyright"
chmod 0755 "$DOC_DIR/postinst" "$DOC_DIR/prerm" "$DOC_DIR/postrm"
chmod 0644 "$DOC_DIR/changelog" "$DOC_DIR/copyright"

# Sincroniza a URL do repositório nos metadados, se o remote existir.
if [ -n "$REPO_URL" ]; then
    for meta in "$DOC_DIR/control" "$DOC_DIR/copyright"; do
        sed -i "s|https://github.com/Miranda3000-CPU/forti-ikev2-linux|$REPO_URL|g" "$meta"
    done
fi

# ─────────────────────────────────────────── código e recursos
cp vpn-gui.py vpn_engine.py vpn_config.py build_info.py "$BUILD_DIR${SHARE_DIR}/"
cp requirements.txt "$BUILD_DIR${SHARE_DIR}/" 2>/dev/null || true
# O .desktop vai para /usr/share/applications (abaixo); não repetir em assets/.
cp -r assets/* "$BUILD_DIR${SHARE_DIR}/assets/"
rm -f "$BUILD_DIR${SHARE_DIR}/assets/forticlient-vpn.desktop"
cp config/forti.conf.example "$BUILD_DIR${SHARE_DIR}/config/" 2>/dev/null || true

# Licenças e avisos: obrigatórios para quem instala o pacote saber o que pode
# fazer com ele (o instalador Windows embarca strongSwan, que é GPLv2).
for doc in LICENSE NOTICE SOURCE-OFFER.txt CHANGELOG.md README.md; do
    [ -f "$doc" ] && cp "$doc" "$BUILD_DIR/usr/share/doc/${PKG_NAME}/"
done

# ─────────────────────────────────────────── atalho e ícone
# O .desktop declara `Icon=forticlient-vpn`; sem o ícone nos temas do sistema o
# atalho aparece genérico. Instalar em hicolor (tema padrão) e em pixmaps
# (compatibilidade) resolve. Sem o 256x256, o hicolor não acha o ícone.
install -m 0644 assets/icon.png "$BUILD_DIR/usr/share/icons/hicolor/256x256/apps/${PKG_NAME}.png"
install -m 0644 assets/icon.png "$BUILD_DIR/usr/share/pixmaps/${PKG_NAME}.png"
install -m 0644 assets/forticlient-vpn.desktop "$BUILD_DIR/usr/share/applications/${PKG_NAME}.desktop"

cat << EOF > "$BUILD_DIR/usr/bin/${PKG_NAME}"
#!/bin/sh
exec /usr/bin/python3 ${SHARE_DIR}/vpn-gui.py "\$@"
EOF
chmod 0755 "$BUILD_DIR/usr/bin/${PKG_NAME}"

# ─────────────────────────────────────────── permissões
# Normaliza tudo para 0644 primeiro: `cp` herda as permissões da árvore de
# trabalho (664 em checkout local) e o dpkg não quer isso no pacote. Depois
# reabre só o que precisa ser executável.
find "$BUILD_DIR/usr" -type f -exec chmod 0644 {} +
chmod 0755 "$BUILD_DIR/usr/bin/${PKG_NAME}" "$BUILD_DIR${SHARE_DIR}/vpn-gui.py"

# ─────────────────────────────────────────── md5sums
# dpkg espera a lista em DEBIAN/md5sums, com caminhos relativos à raiz do
# pacote e sem os próprios arquivos de controle.
( cd "$BUILD_DIR" && find usr -type f -printf '%p\0' | xargs -0 md5sum ) > "$DOC_DIR/md5sums"

# ─────────────────────────────────────────── construção
mkdir -p dist
OUT="dist/${PKG_NAME}_${VERSION}_${ARCH}.deb"
echo "Construindo $OUT..."
dpkg-deb --root-owner-group --build "$BUILD_DIR" "$OUT"

echo
echo "Pacote gerado: $OUT"
dpkg-deb -I "$OUT" | sed -n '/Package:/,/^$/p'
