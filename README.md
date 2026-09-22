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

# 🐧 Instalação e Execução no LINUX

Compatível com **Ubuntu (20.04+)**, **Debian (11+)**, **Linux Mint**, **Pop!_OS**, **Fedora** e **Arch**.

### Opção 1: Inicialização Simplificada e Anti-Interferência (Recomendada)

Ideal para desenvolvimento e ambientes corporativos com antivírus/EDR:

```bash
chmod +x iniciar_linux.sh
./iniciar_linux.sh
```

O `iniciar_linux.sh`:
- Diagnostica e satisfaz automaticamente todas as dependências do sistema (`strongswan`, `python3-tk`, `python3-pil`).
- Configura as permissões estritas em `/etc/sudoers.d/forticlient-vpn` validadas com `visudo -cf`, evitando travamento de interface gráfica por falta de TTY e prevenindo alertas heurísticos de antivírus.
- Cria o atalho oficial na Área de Trabalho (`FortiClient-VPN.desktop`) com o ícone DTIC já marcado como confiável.

---

### Opção 2: Instalação via Pacote `.deb` (Debian / Ubuntu)

Você pode instalar o pacote diretamente gerado na pasta `dist/`:

```bash
# 1. Gerar o pacote .deb (se ainda não gerado)
./build_deb.sh

# 2. Instalar o pacote
sudo apt install ./dist/forticlient-vpn_1.0.0_all.deb
```

---

### Opção 3: Instalação Completa via Script (`install.sh`)

```bash
chmod +x install.sh uninstall.sh vpn-gui.py build_deb.sh iniciar_linux.sh
./install.sh
```

---

# 🪟 Instalação e Execução no WINDOWS

Compatível com **Windows 10** e **Windows 11**.

### Opção 1: Execução via Código-Fonte com Atalho Administrador (Recomendada contra Antivírus)

Esta abordagem **elimina 100% dos falsos positivos** causados por empacotadores binários (PyInstaller), executando o código legítimo diretamente:

1. Dê um duplo-clique no arquivo **`criar_atalho_windows.bat`**.
2. Um atalho oficial chamado **`FortiClient VPN`** com o ícone DTIC será criado na sua Área de Trabalho.
3. Ao clicar no atalho:
   - O Windows abre a janela UAC solicitando privilégios de Administrador.
   - O terminal CMD verifica a presença do Python e instala automaticamente todas as dependências (`pip install -r requirements.txt`).
   - O perfil nativo IKEv2 / Diffie-Hellman Group 18 é validado no subsistema de rede.
   - A aplicação gráfica é iniciada com autoridade administrativa total, permitindo a conexão imediata.

---

### Opção 2: Gerar Executável Portátil (`.exe`)

1. Dê um duplo-clique no arquivo **`build_windows.bat`**.
2. O executável será compilado em `dist\FortiClient-VPN.exe`.

---

### Opção 3: Configuração do Perfil de Rede via PowerShell

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\install.ps1
```

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
