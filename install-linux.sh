#!/usr/bin/env bash
#
# Instala o FortiClient VPN a partir do binário único da release.
#
# Uso:
#   ./install-linux.sh                 # instala em ~/.local (sem sudo para o binário)
#   sudo ./install-linux.sh            # instala em /usr/local, vale para todos
#
# O binário é autocontido (Python e GUI embutidos), mas o motor VPN é o
# strongSwan do sistema — este script instala o pacote e as regras do sudoers
# que permitem ao aplicativo operar o `swanctl` sem pedir senha a cada ação.

set -euo pipefail

GREEN="\033[1;32m"
YELLOW="\033[1;33m"
RED="\033[1;31m"
RESET="\033[0m"

log()  { echo -e "${GREEN}[install]${RESET} $*"; }
warn() { echo -e "${YELLOW}[aviso]${RESET} $*"; }
die()  { echo -e "${RED}[erro]${RESET} $*" >&2; exit 1; }

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_SRC="$DIR/FortiClient-VPN"
PKG_NAME="forticlient-vpn"

[ -f "$BIN_SRC" ] || die "FortiClient-VPN não encontrado ao lado deste script ($BIN_SRC)."

# ─────────────────────────────────────────────────────── prefixo de instalação
if [ "$(id -u)" -eq 0 ]; then
    PREFIX="${PREFIX:-/usr/local}"
else
    PREFIX="${PREFIX:-$HOME/.local}"
fi
BIN_DIR="$PREFIX/bin"
SHARE_DIR="$PREFIX/share/$PKG_NAME"

# ────────────────────────────────────────────────────── dependências do motor
# O binário não traz o strongSwan: ele fala com o `swanctl` do sistema.
if command -v apt-get >/dev/null 2>&1; then
    log "Instalando o strongSwan do sistema..."
    # Ambas com guarda: sem rede ou sem acesso aos repositórios o resto da
    # instalação (binário, sudoers, atalho) ainda vale, e o `set -e` não pode
    # abortar aqui deixando o sistema pela metade.
    sudo apt-get update -qq || warn "apt-get update falhou; seguindo com os repositórios atuais."
    sudo apt-get install -y strongswan strongswan-swanctl || \
        warn "não foi possível instalar o strongswan via apt; seguindo."
else
    warn "sem apt-get: instale strongswan + swanctl pelo seu gerenciador antes de usar."
fi

command -v swanctl >/dev/null 2>&1 || \
    warn "swanctl ainda ausente: o aplicativo vai acusar 'Motor strongSwan não encontrado'."

# Prefixo no diretório do próprio usuário não precisa (nem pode) ser root: usar
# sudo aqui criaria ~/.local/bin como root e travaria futuras atualizações.
# Vale só para os arquivos do aplicativo — o sudoers é sempre system-wide.
if [ "$(id -u)" -eq 0 ] || [ "${PREFIX#"$HOME"}" != "$PREFIX" ]; then
    run() { "$@"; }
else
    run() { sudo "$@"; }
fi

# ──────────────────────────────────────────────────────────── regras sudoers
#
# Sem estas regras o `sudo swanctl` não consegue pedir senha: o aplicativo é
# GUI e executa os comandos sem terminal anexado. Este é o mesmo conjunto que
# o .deb instala via postinst. Sempre com root, seja qual for o prefixo.
SUDOERS_FILE="/etc/sudoers.d/$PKG_NAME"
as_root() { if [ "$(id -u)" -eq 0 ]; then "$@"; else sudo "$@"; fi; }

log "Instalando as regras do sudoers ($SUDOERS_FILE)..."
as_root tee "$SUDOERS_FILE" > /dev/null << 'EOF'
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
ALL ALL=(root) NOPASSWD: /usr/sbin/ip rule add lookup 220 pref 220
ALL ALL=(root) NOPASSWD: /sbin/ip rule add lookup 220 pref 220
EOF
as_root chmod 0440 "$SUDOERS_FILE"
# O tee acima já roda como root, então o dono já é root: o chown é só
# garantia. Não-fatal para não abortar uma instalação válida por isso.
as_root chown root:root "$SUDOERS_FILE" || true

# Um sudoers malformado tranca o `sudo` do sistema inteiro. Confere antes de
# seguir; sem `visudo` (instalações mínimas) segue com aviso em vez de travar.
if command -v visudo >/dev/null 2>&1; then
    as_root visudo -cf "$SUDOERS_FILE" > /dev/null 2>&1 \
        || die "regras do sudoers recusadas pelo visudo; remova $SUDOERS_FILE e tente de novo."
else
    warn "visudo ausente: regras instaladas sem conferência de sintaxe."
fi

# ─────────────────────────────────────────────────────────────── diretórios
run mkdir -p "$BIN_DIR" "$SHARE_DIR"

# ──────────────────────────────────────────────────────────────── o binário
log "Instalando o binário em $BIN_DIR..."
run cp "$BIN_SRC" "$BIN_DIR/FortiClient-VPN"
run chmod 0755 "$BIN_DIR/FortiClient-VPN"

# ──────────────────────────────────────────────── ícone e atalho do menu
# O ícone vive DENTRO do binário (PyInstaller); o --extract-assets o despeja
# para podermos montar o atalho sem os fontes do projeto.
log "Extraindo ícone e montando o atalho do menu..."
ICON_DIR="$SHARE_DIR/assets"
mkdir -p "$ICON_DIR" 2>/dev/null || run mkdir -p "$ICON_DIR"
if "$BIN_DIR/FortiClient-VPN" --extract-assets "$ICON_DIR" > /dev/null 2>&1; then
    # O .desktop é sempre machine-wide (o desktop o lê de /usr/share), então o
    # ícone e o atalho vão para lá com root — mesmo quando o binário é do usuário.
    as_root mkdir -p /usr/share/icons/hicolor/256x256/apps /usr/share/pixmaps /usr/share/applications
    as_root cp "$ICON_DIR/icon.png" "/usr/share/icons/hicolor/256x256/apps/$PKG_NAME.png"
    as_root cp "$ICON_DIR/icon.png" "/usr/share/pixmaps/$PKG_NAME.png"

    as_root tee /usr/share/applications/$PKG_NAME.desktop > /dev/null << EOF
[Desktop Entry]
Type=Application
Name=FortiClient VPN
Comment=Conexao VPN IKEv2 (FortiGate) - DTIC
Exec=$BIN_DIR/FortiClient-VPN
Icon=$PKG_NAME
Terminal=false
Categories=Network;
StartupNotify=true
EOF
    as_root chmod 0644 /usr/share/applications/$PKG_NAME.desktop

    if command -v gtk-update-icon-cache >/dev/null 2>&1; then
        as_root gtk-update-icon-cache -f /usr/share/icons/hicolor 2>/dev/null || true
    fi
    if command -v update-desktop-database >/dev/null 2>&1; then
        as_root update-desktop-database /usr/share/applications 2>/dev/null || true
    fi
else
    warn "não foi possível extrair o ícone; o atalho do menu não foi criado."
    warn "você ainda pode abrir com: $BIN_DIR/FortiClient-VPN"
fi

log "Concluído."
echo
echo "  Aplicativo: $BIN_DIR/FortiClient-VPN"
echo "  Menu:       FortiClient VPN"
echo
echo "  Regras do sudoers permitem 'swanctl' sem senha para TODOS os usuários"
echo "  ($SUDOERS_FILE). Para restringir, troque 'ALL ALL' pelo seu usuário."
echo "  Para remover: sudo rm -f \"$SUDOERS_FILE\" \"$BIN_DIR/FortiClient-VPN\""
