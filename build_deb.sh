#!/usr/bin/env bash
# =============================================================================
# build_deb.sh — Gerador de pacote Debian (.deb) para FortiClient VPN Manager
#
# Gera um pacote .deb profissional com:
#   - Validação de dependências de build
#   - Geração automática de ícones circulares
#   - Scripts de manutenção (postinst, prerm, postrm)
#   - Configuração de sudoers segura
#   - Desktop entry compatível com freedesktop.org
#   - Validação final com lintian (se disponível)
# =============================================================================
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

# --- Metadados do pacote ---
VERSION="1.0.0"
PKG_NAME="forticlient-vpn"
ARCH="all"
DEB_NAME="${PKG_NAME}_${VERSION}_${ARCH}.deb"
BUILD_ROOT="build/deb"

# --- Cores para output ---
RED='\033[1;31m'
GREEN='\033[1;32m'
YELLOW='\033[1;33m'
BLUE='\033[1;34m'
RESET='\033[0m'

echo -e "${BLUE}========================================================${RESET}"
echo -e "${BLUE}  Gerador de Pacote .deb — FortiClient VPN Manager v${VERSION}${RESET}"
echo -e "${BLUE}========================================================${RESET}"
echo ""

# --- 1. Validação de pré-requisitos ---
echo -e "${YELLOW}[1/8] Verificando pré-requisitos de build...${RESET}"

errors=0

if ! command -v dpkg-deb &>/dev/null; then
    echo -e "${RED}  ✗ dpkg-deb não encontrado. Instale: sudo apt install dpkg${RESET}"
    errors=1
fi

if ! command -v python3 &>/dev/null; then
    echo -e "${RED}  ✗ python3 não encontrado. Instale: sudo apt install python3${RESET}"
    errors=1
fi

if ! python3 -c "from PIL import Image, ImageDraw" 2>/dev/null; then
    echo -e "${RED}  ✗ Pillow não encontrado. Instale: sudo apt install python3-pil ou pip3 install Pillow${RESET}"
    errors=1
fi

if [ ! -f "vpn-gui.py" ]; then
    echo -e "${RED}  ✗ Arquivo vpn-gui.py não encontrado no diretório do projeto${RESET}"
    errors=1
fi

if [ ! -f "assets/dtic-logo-whasapp.jpeg" ]; then
    echo -e "${RED}  ✗ Logo DTIC não encontrada em assets/dtic-logo-whasapp.jpeg${RESET}"
    errors=1
fi

if [ "$errors" -eq 1 ]; then
    echo -e "\n${RED}[ERRO] Pré-requisitos não atendidos. Corrija os problemas acima e tente novamente.${RESET}"
    exit 1
fi

echo -e "${GREEN}  ✓ Todos os pré-requisitos OK${RESET}"

# --- 2. Gerar ícones circulares ---
echo -e "\n${YELLOW}[2/8] Gerando ícones circulares DTIC...${RESET}"

python3 - <<'PYEOF'
import sys
from PIL import Image, ImageDraw
import os

src = "assets/dtic-logo-whasapp.jpeg"
if not os.path.exists(src):
    print(f"  ERRO: {src} não encontrado", file=sys.stderr)
    sys.exit(1)

img = Image.open(src).convert("RGBA")
w, h = img.size
m = min(w, h)
c = img.crop(((w - m) // 2, (h - m) // 2, (w - m) // 2 + m, (h - m) // 2 + m))

scale = 4
mask = Image.new("L", (m * scale, m * scale), 0)
ImageDraw.Draw(mask).ellipse((0, 0, m * scale, m * scale), fill=255)
mask = mask.resize((m, m), Image.Resampling.LANCZOS)
c.putalpha(mask)

# Salvar PNG de alta qualidade
c.save("assets/icon.png", "PNG", optimize=True)

# Salvar ICO com múltiplas resoluções
try:
    c.save(
        "assets/icon.ico",
        format="ICO",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    )
except Exception as e:
    print(f"  Aviso: Não foi possível gerar .ico: {e}")

print("  -> Ícones redondos atualizados com sucesso.")
PYEOF

echo -e "${GREEN}  ✓ Ícones gerados${RESET}"

# --- 3. Limpar e criar estrutura de diretórios ---
echo -e "\n${YELLOW}[3/8] Preparando estrutura do pacote...${RESET}"

rm -rf "$BUILD_ROOT"
mkdir -p "$BUILD_ROOT/DEBIAN"
mkdir -p "$BUILD_ROOT/usr/bin"
mkdir -p "$BUILD_ROOT/usr/share/$PKG_NAME/assets"
mkdir -p "$BUILD_ROOT/usr/share/applications"
mkdir -p "$BUILD_ROOT/usr/share/pixmaps"
mkdir -p "$BUILD_ROOT/usr/share/icons/hicolor/256x256/apps"
mkdir -p "$BUILD_ROOT/usr/share/icons/hicolor/128x128/apps"
mkdir -p "$BUILD_ROOT/usr/share/icons/hicolor/64x64/apps"
mkdir -p "$BUILD_ROOT/usr/share/icons/hicolor/48x48/apps"
mkdir -p "$BUILD_ROOT/etc/sudoers.d"
mkdir -p "dist"

echo -e "${GREEN}  ✓ Estrutura criada${RESET}"

# --- 4. Arquivo DEBIAN/control ---
echo -e "\n${YELLOW}[4/8] Criando arquivos de controle Debian...${RESET}"

# Calcular Installed-Size (em KB)
INSTALLED_SIZE=$(du -sk "$DIR/vpn-gui.py" "$DIR/assets" 2>/dev/null | awk '{s+=$1} END{print s+50}')

cat > "$BUILD_ROOT/DEBIAN/control" <<EOF
Package: ${PKG_NAME}
Version: ${VERSION}
Section: net
Priority: optional
Architecture: ${ARCH}
Maintainer: DTIC Bombeiros <dtic@bombeiros.pa.gov.br>
Depends: strongswan, strongswan-swanctl, libcharon-extra-plugins, python3 (>= 3.8), python3-tk, python3-pil, python3-pil.imagetk
Recommends: curl
Suggests: network-manager-strongswan
Installed-Size: ${INSTALLED_SIZE}
Homepage: https://github.com/dtic-bombeiros/forticlient-vpn
Description: FortiClient IKEv2 VPN Manager - Interface Gráfica
 Interface gráfica nativa em Python/Tkinter para gerenciamento e conexão
 a VPNs corporativas FortiGate utilizando protocolo IKEv2/IPsec com
 EAP-MSCHAPv2 e autenticação PSK.
 .
 Recursos principais:
  - Conexão automática via strongSwan (swanctl)
  - Detecção automática de IP local
  - Salvamento seguro de credenciais
  - Painel de diagnóstico em tempo real
  - Ícone oficial DTIC integrado
EOF

# --- 5. conffiles: marca arquivos de configuração que o apt deve preservar ---
cat > "$BUILD_ROOT/DEBIAN/conffiles" <<EOF
/etc/sudoers.d/forticlient-vpn
EOF

# --- 6. Script postinst ---
cat > "$BUILD_ROOT/DEBIAN/postinst" <<'POSTINST'
#!/bin/sh
set -e

# Garantir permissões corretas
chmod 755 /usr/bin/forticlient-vpn 2>/dev/null || true
chmod 755 /usr/share/forticlient-vpn/vpn-gui.py 2>/dev/null || true

# Sudoers deve ser 0440 e pertencer ao root
chown root:root /etc/sudoers.d/forticlient-vpn 2>/dev/null || true
chmod 440 /etc/sudoers.d/forticlient-vpn 2>/dev/null || true

# Validar sintaxe do sudoers para não travar o sudo
if command -v visudo >/dev/null 2>&1; then
    if ! visudo -cf /etc/sudoers.d/forticlient-vpn >/dev/null 2>&1; then
        echo "AVISO: Arquivo sudoers com sintaxe inválida. Removendo por segurança."
        rm -f /etc/sudoers.d/forticlient-vpn
    fi
fi

# Atualizar caches de ícone e desktop
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database /usr/share/applications 2>/dev/null || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -f -t /usr/share/icons/hicolor 2>/dev/null || true
fi

# Habilitar e iniciar o strongSwan
if command -v systemctl >/dev/null 2>&1; then
    systemctl enable strongswan-starter.service 2>/dev/null || \
    systemctl enable strongswan.service 2>/dev/null || true

    if systemctl is-system-running >/dev/null 2>&1; then
        systemctl start strongswan-starter.service 2>/dev/null || \
        systemctl start strongswan.service 2>/dev/null || true
    fi
fi

# Criar diretório de configuração swanctl
mkdir -p /etc/swanctl/conf.d

echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║  FortiClient VPN instalado com sucesso!              ║"
echo "╠══════════════════════════════════════════════════════╣"
echo "║  Execute: forticlient-vpn                            ║"
echo "║  Ou localize no menu de aplicativos.                 ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""

exit 0
POSTINST
chmod 755 "$BUILD_ROOT/DEBIAN/postinst"

# --- 7. Script prerm ---
cat > "$BUILD_ROOT/DEBIAN/prerm" <<'PRERM'
#!/bin/sh
set -e

# Desconectar VPN ativa antes de remover
if command -v swanctl >/dev/null 2>&1; then
    swanctl --terminate --ike forticlient >/dev/null 2>&1 || true
fi

exit 0
PRERM
chmod 755 "$BUILD_ROOT/DEBIAN/prerm"

# --- 8. Script postrm (limpeza completa na remoção) ---
cat > "$BUILD_ROOT/DEBIAN/postrm" <<'POSTRM'
#!/bin/sh
set -e

case "$1" in
    purge)
        # Remover configurações ao fazer purge
        rm -f /etc/swanctl/conf.d/forti.conf 2>/dev/null || true
        rm -f /etc/sudoers.d/forticlient-vpn 2>/dev/null || true

        # Atualizar caches
        if command -v update-desktop-database >/dev/null 2>&1; then
            update-desktop-database /usr/share/applications 2>/dev/null || true
        fi
        if command -v gtk-update-icon-cache >/dev/null 2>&1; then
            gtk-update-icon-cache -f -t /usr/share/icons/hicolor 2>/dev/null || true
        fi
        ;;

    remove|upgrade|failed-upgrade|abort-install|abort-upgrade|disappear)
        # Atualizar caches de desktop
        if command -v update-desktop-database >/dev/null 2>&1; then
            update-desktop-database /usr/share/applications 2>/dev/null || true
        fi
        if command -v gtk-update-icon-cache >/dev/null 2>&1; then
            gtk-update-icon-cache -f -t /usr/share/icons/hicolor 2>/dev/null || true
        fi
        ;;
esac

exit 0
POSTRM
chmod 755 "$BUILD_ROOT/DEBIAN/postrm"

echo -e "${GREEN}  ✓ Arquivos de controle criados (control, conffiles, postinst, prerm, postrm)${RESET}"

# --- 9. Executável wrapper ---
echo -e "\n${YELLOW}[5/8] Criando executável wrapper...${RESET}"

cat > "$BUILD_ROOT/usr/bin/forticlient-vpn" <<'WRAPPER'
#!/usr/bin/env bash
# FortiClient VPN Manager - Wrapper de execução
# Garante que o aplicativo funcione mesmo sem DISPLAY configurado

# Verificar se tem display disponível (para X11 ou Wayland)
if [ -z "${DISPLAY:-}" ] && [ -z "${WAYLAND_DISPLAY:-}" ]; then
    echo "Erro: Nenhum display gráfico detectado."
    echo "Este programa requer um ambiente gráfico (X11 ou Wayland)."
    echo "Se estiver em um terminal remoto, use: ssh -X usuario@host"
    exit 1
fi

# Verificar se python3 está disponível
if ! command -v python3 >/dev/null 2>&1; then
    echo "Erro: python3 não encontrado."
    echo "Instale com: sudo apt install python3"
    exit 1
fi

# Verificar se tkinter está disponível
if ! python3 -c "import tkinter" 2>/dev/null; then
    echo "Erro: python3-tk não encontrado."
    echo "Instale com: sudo apt install python3-tk"
    exit 1
fi

exec /usr/bin/python3 /usr/share/forticlient-vpn/vpn-gui.py "$@"
WRAPPER
chmod 755 "$BUILD_ROOT/usr/bin/forticlient-vpn"

echo -e "${GREEN}  ✓ Wrapper criado com verificações de ambiente${RESET}"

# --- 10. Copiar aplicação e assets ---
echo -e "\n${YELLOW}[6/8] Copiando aplicação e recursos...${RESET}"

cp vpn-gui.py "$BUILD_ROOT/usr/share/$PKG_NAME/"
chmod 755 "$BUILD_ROOT/usr/share/$PKG_NAME/vpn-gui.py"

# Copiar todos os assets
cp -r assets/* "$BUILD_ROOT/usr/share/$PKG_NAME/assets/"

# Instalar ícones em múltiplas resoluções para compatibilidade total
if [ -f "assets/icon.png" ]; then
    cp assets/icon.png "$BUILD_ROOT/usr/share/pixmaps/forticlient-vpn.png"
    cp assets/icon.png "$BUILD_ROOT/usr/share/icons/hicolor/256x256/apps/forticlient-vpn.png"

    # Gerar ícones em resoluções menores se possível
    python3 - <<'PYEOF2' 2>/dev/null || true
from PIL import Image
import os

src = "assets/icon.png"
img = Image.open(src)

sizes = {
    "build/deb/usr/share/icons/hicolor/128x128/apps/forticlient-vpn.png": (128, 128),
    "build/deb/usr/share/icons/hicolor/64x64/apps/forticlient-vpn.png": (64, 64),
    "build/deb/usr/share/icons/hicolor/48x48/apps/forticlient-vpn.png": (48, 48),
}

for path, size in sizes.items():
    resized = img.resize(size, Image.Resampling.LANCZOS)
    resized.save(path, "PNG", optimize=True)
    print(f"  -> Ícone {size[0]}x{size[1]} gerado")
PYEOF2
fi

echo -e "${GREEN}  ✓ Aplicação e recursos copiados${RESET}"

# --- 11. Desktop entry ---
echo -e "\n${YELLOW}[7/8] Criando desktop entry e sudoers...${RESET}"

cat > "$BUILD_ROOT/usr/share/applications/forticlient-vpn.desktop" <<'DESKTOP'
[Desktop Entry]
Version=1.0
Type=Application
Name=FortiClient VPN
GenericName=VPN Client
Comment=Gerenciador FortiClient VPN IKEv2 (DTIC/PRODEPA)
Comment[en]=FortiClient VPN IKEv2 Manager (DTIC/PRODEPA)
Exec=forticlient-vpn
Icon=forticlient-vpn
Terminal=false
Categories=Network;Security;
Keywords=vpn;fortinet;forticlient;ikev2;ipsec;dtic;prodepa;
StartupWMClass=Tk
StartupNotify=true
DESKTOP
chmod 644 "$BUILD_ROOT/usr/share/applications/forticlient-vpn.desktop"

# Sudoers seguro: apenas os comandos estritamente necessários
cat > "$BUILD_ROOT/etc/sudoers.d/forticlient-vpn" <<'SUDOERS'
# FortiClient VPN - Permissões sudo para operação da VPN
# Permite que qualquer usuário execute os comandos swanctl e ip rule sem senha
# Gerado automaticamente pelo pacote forticlient-vpn

# Gerenciamento do strongSwan (conexão/desconexão VPN)
ALL ALL=(root) NOPASSWD: /usr/sbin/swanctl --load-all
ALL ALL=(root) NOPASSWD: /usr/sbin/swanctl --list-sas
ALL ALL=(root) NOPASSWD: /usr/sbin/swanctl --initiate --child forticlient
ALL ALL=(root) NOPASSWD: /usr/sbin/swanctl --terminate --ike forticlient
ALL ALL=(root) NOPASSWD: /usr/bin/swanctl --load-all
ALL ALL=(root) NOPASSWD: /usr/bin/swanctl --list-sas
ALL ALL=(root) NOPASSWD: /usr/bin/swanctl --initiate --child forticlient
ALL ALL=(root) NOPASSWD: /usr/bin/swanctl --terminate --ike forticlient

# Criação do arquivo de configuração swanctl
ALL ALL=(root) NOPASSWD: /usr/bin/tee /etc/swanctl/conf.d/forti.conf
ALL ALL=(root) NOPASSWD: /usr/bin/chmod 600 /etc/swanctl/conf.d/forti.conf
ALL ALL=(root) NOPASSWD: /usr/bin/mkdir -p /etc/swanctl/conf.d

# Regras de roteamento IP
ALL ALL=(root) NOPASSWD: /usr/sbin/ip rule add lookup 220 pref 220
ALL ALL=(root) NOPASSWD: /sbin/ip rule add lookup 220 pref 220
SUDOERS
chmod 440 "$BUILD_ROOT/etc/sudoers.d/forticlient-vpn"

echo -e "${GREEN}  ✓ Desktop entry e sudoers criados${RESET}"

# --- 12. Empacotar e validar ---
echo -e "\n${YELLOW}[8/8] Empacotando com dpkg-deb...${RESET}"

# Garantir permissões corretas no diretório DEBIAN
find "$BUILD_ROOT/DEBIAN" -type f -exec chmod 755 {} \; 2>/dev/null || true
chmod 644 "$BUILD_ROOT/DEBIAN/control"
chmod 644 "$BUILD_ROOT/DEBIAN/conffiles"

# Garantir owner correto para todos os arquivos (compatível com fakeroot)
# dpkg-deb --root-owner-group já cuida disso

dpkg-deb --build --root-owner-group "$BUILD_ROOT" "dist/$DEB_NAME"

echo -e "${GREEN}  ✓ Pacote criado: dist/${DEB_NAME}${RESET}"

# Verificar tamanho
DEB_SIZE=$(du -h "dist/$DEB_NAME" | cut -f1)
echo -e "  Tamanho: ${DEB_SIZE}"

# Validação com lintian (se disponível)
if command -v lintian &>/dev/null; then
    echo -e "\n${YELLOW}[*] Validando pacote com lintian...${RESET}"
    lintian "dist/$DEB_NAME" --no-tag-display-limit 2>&1 || true
    echo -e "${GREEN}  ✓ Validação lintian concluída${RESET}"
else
    echo -e "\n${BLUE}[*] lintian não instalado. Para validação extra: sudo apt install lintian${RESET}"
fi

# Verificar integridade do .deb
echo -e "\n${YELLOW}[*] Verificando integridade do pacote...${RESET}"
dpkg-deb --info "dist/$DEB_NAME" >/dev/null 2>&1 && echo -e "${GREEN}  ✓ Pacote válido e íntegro${RESET}" || echo -e "${RED}  ✗ Pacote com problemas${RESET}"

echo ""
echo -e "${GREEN}========================================================${RESET}"
echo -e "${GREEN}  ✅ Build .deb concluído com sucesso!${RESET}"
echo -e "${GREEN}========================================================${RESET}"
echo ""
echo -e "Arquivo gerado: ${BLUE}dist/${DEB_NAME}${RESET}"
echo ""
echo -e "Para instalar no Ubuntu/Debian:"
echo -e "  ${YELLOW}sudo apt install ./dist/${DEB_NAME}${RESET}"
echo ""
echo -e "Para desinstalar:"
echo -e "  ${YELLOW}sudo apt remove ${PKG_NAME}${RESET}"
echo -e "  ${YELLOW}sudo apt purge ${PKG_NAME}${RESET}  (remove também configurações)"
echo ""
