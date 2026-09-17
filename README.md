# 🛡️ FortiClient VPN Manager - Multiplataforma (Linux & Windows)

Aplicativo com **Interface Gráfica Nativa** e identidade visual institucional (DTIC), desenvolvido para conexão a VPNs corporativas **FortiGate (Fortinet)** utilizando o protocolo **IKEv2 / IPsec**, autenticação dupla (**Pre-Shared Key + EAP-MSCHAPv2**) e IP Virtual dinâmico (CPRP).

---

## 💻 Recursos da Aplicação Gráfica

- **Ícone Institucional Personalizado:** O logotipo DTIC (`assets/dtic-logo-whasapp.jpeg`) é recortado dinamicamente em formato **redondo**, utilizado tanto no cabeçalho da janela, barra de tarefas, atalhos do sistema e executável.
- **Segurança de Credenciais:** As credenciais (Usuário, Senha e PSK) **NÃO** ficam gravadas no código-fonte nem no Git. Elas são salvas localmente no computador do usuário (`~/.config/forticlient-vpn/config.json` no Linux com permissão `0600`, ou `%APPDATA%\FortiClientVPN\config.json` no Windows) apenas após o cadastro na interface.
- **Multiplataforma Nativa:**
  - **Windows:** Executável portátil (`.exe`) e integração com `rasdial` / PowerShell VPN API.
  - **Linux:** Pacote `.deb` nativo para Debian/Ubuntu e script instalador para Fedora/Arch (via `strongSwan / swanctl`).
- **Conexão e Desconexão com 1 Clique:** Detecção em tempo real de status e captura automática do IP Virtual (VIP) atribuído.
- **Acesso Direto ao Painel Web:** Botão rápido para abrir `https://10.64.10.1:6464` no navegador padrão e teste integrado de conectividade HTTP.

---

## 📂 Estrutura do Repositório

```text
forticlient-vpn-linux/
├── assets/
│   ├── dtic-logo-whasapp.jpeg      # Logotipo oficial DTIC
│   ├── icon.png                    # Ícone recortado redondo (PNG)
│   ├── icon.ico                    # Ícone multi-resolução para Windows (.exe)
│   └── forticlient-vpn.desktop     # Lançador para o menu de aplicativos Linux
├── config/
│   └── forti.conf.example          # Modelo swanctl com placeholders
├── dist/                           # Executáveis gerados (.deb e .exe)
├── vpn-gui.py                      # Aplicação gráfica Python (Tkinter + PIL)
├── FortiClient-VPN.spec            # Especificação PyInstaller para gerar executável Windows
├── build_windows.bat               # Script para compilar o .exe no Windows
├── build_deb.sh                    # Script para gerar o pacote .deb no Linux
├── install.sh                      # Instalador de script para Linux
├── install.ps1                     # Instalador/configurador para Windows PowerShell
├── uninstall.sh                    # Desinstalador Linux
├── requirements.txt                # Dependências Python (Pillow)
└── README.md                       # Documentação
```

---

# 🐧 Instalação no LINUX

Compatível com **Ubuntu (20.04+)**, **Debian (11+)**, **Linux Mint**, **Pop!_OS**, **Fedora** e **Arch**.

### Opção 1: Instalação via Pacote `.deb` (Recomendada para Debian / Ubuntu)

Você pode instalar o pacote diretamente gerado na pasta `dist/`:

```bash
# 1. Gerar o pacote .deb (se ainda não gerado)
./build_deb.sh

# 2. Instalar o pacote
sudo apt install ./dist/forticlient-vpn_1.0.0_all.deb
```

Ao instalar o `.deb`:
- O comando `forticlient-vpn` fica disponível globalmente no sistema.
- O atalho com o **ícone redondo oficial DTIC** é adicionado ao menu de aplicativos e pode ser fixado na barra de tarefas.
- As dependências de rede (`strongswan`, `strongswan-swanctl`) e Python são configuradas automaticamente.

---

### Opção 2: Instalação via Script (`install.sh`)

Caso prefira instalar via script em qualquer distribuição:

```bash
chmod +x install.sh uninstall.sh vpn-gui.py build_deb.sh
./install.sh
```

---

# 🪟 Instalação e Executável no WINDOWS

Compatível com **Windows 10** e **Windows 11**.

### Opção 1: Gerar e Rodar como Programa Executável (`.exe`)

1. No Windows, clone o repositório ou baixe os arquivos.
2. Dê um duplo-clique no arquivo **`build_windows.bat`** (ou execute via Prompt de Comando):
   ```cmd
   build_windows.bat
   ```
3. O script irá instalar o `Pillow` e `PyInstaller` e compilar o executável com o **ícone oficial redondo DTIC** em:
   ```text
   dist\FortiClient-VPN.exe
   ```
4. Basta mover o **`FortiClient-VPN.exe`** para onde desejar (Área de Trabalho, Arquivos de Programas, etc.) e executá-lo diretamente com 2 cliques, **sem precisar abrir terminal nem instalar Python em outros computadores**.

---

### Opção 2: Configuração Rápida do Perfil de Rede (PowerShell)

Execute no PowerShell como Administrador para registrar a conexão IKEv2 com as cifras seguras (Diffie-Hellman Group 18 / MODP_8192):

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\install.ps1
```

O `install.ps1` detecta automaticamente se o `FortiClient-VPN.exe` existe e cria o atalho oficial na Área de Trabalho.

---

## 🔐 Configuração das Credenciais na Interface

Ao abrir o programa pela primeira vez:
1. **Gateway VPN:** `198.51.100.100` (ou IP corporativo fornecido)
2. **Meu IP Local:** Detectado automaticamente pela interface de rede
3. **Usuário (EAP):** Seu usuário institucional
4. **Senha:** Sua senha de rede
5. **Chave PSK:** Chave pré-compartilhada fornecida pela DTIC
6. Clique em **💾 Salvar Configurações** (ou clique diretamente em **▶ CONECTAR VPN** com a caixa "Salvar dados neste computador" marcada).

Suas credenciais serão salvas de forma segura no seu próprio diretório de usuário e **nunca** serão enviadas a repositórios.
