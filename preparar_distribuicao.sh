#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════
#  preparar_distribuicao.sh
#
#  Prepara as pastas de distribuição prontas para enviar aos usuários.
#  Executa os builds e organiza tudo em:
#
#    distribuir/
#    ├── linux/           ← Enviar esta pasta para usuários Linux
#    │   ├── instalar.sh
#    │   ├── desinstalar.sh
#    │   └── forticlient-vpn_1.0.0_all.deb
#    │
#    └── windows/         ← Copiar para um PC Windows para gerar o Setup.exe
#        ├── FortiClient-VPN-Setup.iss
#        └── LEIA-ME.txt
#
#  Após gerar o Setup.exe no Windows, a pasta windows/ conterá:
#    └── FortiClient-VPN-Setup-1.0.0.exe  ← Enviar ao usuário
# ═══════════════════════════════════════════════════════════════════
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

GREEN='\033[1;32m'
YELLOW='\033[1;33m'
BLUE='\033[1;34m'
RED='\033[1;31m'
RESET='\033[0m'

echo -e "${BLUE}════════════════════════════════════════════════════════${RESET}"
echo -e "${BLUE}  Preparador de Distribuição — FortiClient VPN v1.0.0  ${RESET}"
echo -e "${BLUE}════════════════════════════════════════════════════════${RESET}"
echo ""

# ═══════════════════════════════════
#  ETAPA 1: Build do .deb
# ═══════════════════════════════════
echo -e "${YELLOW}[1/3] Gerando pacote .deb para Linux...${RESET}"

if [ -f "build_deb.sh" ]; then
    bash build_deb.sh
    echo ""
else
    echo -e "${RED}  ✗ build_deb.sh não encontrado${RESET}"
    exit 1
fi

# ═══════════════════════════════════
#  ETAPA 2: Montar pasta Linux
# ═══════════════════════════════════
echo -e "${YELLOW}[2/3] Preparando pasta de distribuição Linux...${RESET}"

mkdir -p distribuir/linux

# Copiar .deb para a pasta de distribuição
cp dist/forticlient-vpn_1.0.0_all.deb distribuir/linux/

# Garantir permissões de execução nos scripts
chmod +x distribuir/linux/instalar.sh
chmod +x distribuir/linux/desinstalar.sh

# Criar LEIA-ME para Linux
cat > distribuir/linux/LEIA-ME.txt <<'EOF'
╔══════════════════════════════════════════════════════════╗
║        FortiClient VPN — Instalação no Linux             ║
╚══════════════════════════════════════════════════════════╝

 COMO INSTALAR:

   Opção 1 (Recomendada):
     Dê duplo-clique no arquivo "instalar.sh"
     e siga as instruções na tela.

   Opção 2 (Terminal):
     Abra o terminal nesta pasta e execute:
       sudo apt install ./forticlient-vpn_1.0.0_all.deb

 COMO DESINSTALAR:

   Opção 1:
     Dê duplo-clique no arquivo "desinstalar.sh"

   Opção 2 (Terminal):
     sudo apt remove forticlient-vpn

 COMO USAR:

   Após instalar, abra o programa:
     • Pelo ícone "FortiClient VPN" no menu de aplicativos
     • Pelo atalho na Área de Trabalho
     • Pelo terminal: forticlient-vpn

   Preencha os campos de Gateway, Usuário e Senha e clique
   em "CONECTAR VPN".

 REQUISITOS:
   • Ubuntu 20.04+ ou Debian 11+
   • Conexão de rede ativa

 SUPORTE:
   DTIC - dtic@bombeiros.pa.gov.br

EOF

echo -e "${GREEN}  ✓ Pasta Linux pronta: distribuir/linux/${RESET}"

# ═══════════════════════════════════
#  ETAPA 3: Montar pasta Windows
# ═══════════════════════════════════
echo -e "\n${YELLOW}[3/3] Preparando pasta de distribuição Windows...${RESET}"

mkdir -p distribuir/windows

# Copiar ícone para o Windows
if [ -f "assets/icon.ico" ]; then
    cp assets/icon.ico distribuir/windows/FortiClient-VPN.ico
fi

# Criar LEIA-ME para Windows
cat > distribuir/windows/LEIA-ME.txt <<'WINEOF'
╔══════════════════════════════════════════════════════════╗
║     FortiClient VPN — Gerar Instalador Windows           ║
╚══════════════════════════════════════════════════════════╝

 PARA O DISTRIBUIDOR (time de TI):

   Este procedimento gera o "FortiClient-VPN-Setup-1.0.0.exe"
   que será enviado aos usuários finais.

   Passo 1: No PC Windows, instale Python 3.10+
            https://www.python.org/downloads/
            (Marque "Add python.exe to PATH")

   Passo 2: Copie todo o projeto para o PC Windows

   Passo 3: Execute "build_windows.bat" para gerar o .exe
            O resultado ficará em: dist\FortiClient-VPN.exe

   Passo 4: Copie dist\FortiClient-VPN.exe para esta pasta

   Passo 5: Instale o Inno Setup (gratuito):
            https://jrsoftware.org/isdl.php

   Passo 6: Abra o arquivo "FortiClient-VPN-Setup.iss" no Inno Setup
            e clique em Build > Compile (Ctrl+F9)

   Passo 7: O instalador será gerado nesta pasta:
            FortiClient-VPN-Setup-1.0.0.exe

   Passo 8: Distribua APENAS este arquivo .exe aos usuários.

 ──────────────────────────────────────────────────────────

 PARA O USUÁRIO FINAL:

   Dê duplo-clique em "FortiClient-VPN-Setup-1.0.0.exe"
   e siga o assistente de instalação.

   Após instalar, abra pelo atalho na Área de Trabalho
   ou pelo Menu Iniciar.

 SUPORTE:
   DTIC - dtic@bombeiros.pa.gov.br

WINEOF

echo -e "${GREEN}  ✓ Pasta Windows pronta: distribuir/windows/${RESET}"

# ═══════════════════════════════════
#  RESUMO FINAL
# ═══════════════════════════════════
echo ""
echo -e "${GREEN}════════════════════════════════════════════════════════${RESET}"
echo -e "${GREEN}  ✅ Distribuição preparada com sucesso!${RESET}"
echo -e "${GREEN}════════════════════════════════════════════════════════${RESET}"
echo ""
echo -e "  ${BLUE}📁 distribuir/linux/${RESET}"
echo -e "     ├── instalar.sh                     (duplo-clique para instalar)"
echo -e "     ├── desinstalar.sh                  (duplo-clique para desinstalar)"
echo -e "     ├── forticlient-vpn_1.0.0_all.deb   (pacote de instalação)"
echo -e "     └── LEIA-ME.txt                     (instruções)"
echo ""
echo -e "  ${BLUE}📁 distribuir/windows/${RESET}"
echo -e "     ├── FortiClient-VPN-Setup.iss        (script do instalador)"
echo -e "     ├── FortiClient-VPN.ico              (ícone)"
echo -e "     ├── LEIA-ME.txt                      (instruções)"
echo -e "     └── (gerar FortiClient-VPN-Setup-1.0.0.exe no Windows)"
echo ""
echo -e "  ${YELLOW}Para Linux:${RESET}"
echo -e "    Envie a pasta ${BLUE}distribuir/linux/${RESET} ao usuário."
echo -e "    Ele dá duplo-clique em ${BLUE}instalar.sh${RESET} e pronto."
echo ""
echo -e "  ${YELLOW}Para Windows:${RESET}"
echo -e "    Siga o LEIA-ME.txt na pasta ${BLUE}distribuir/windows/${RESET}"
echo -e "    para gerar o Setup.exe e depois distribua."
echo ""
