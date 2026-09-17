# 🛡️ FortiClient VPN GUI para Linux (Ubuntu / Debian)

Um aplicativo nativo com **Interface Gráfica (GUI em Tkinter)** para conexão a VPNs corporativas **FortiGate (Fortinet)** utilizando o protocolo **IKEv2 / IPsec**, autenticação dupla (**Pre-Shared Key + EAP-MSCHAPv2**) e alocação dinâmica de IP Virtual (DHCP / CPRP).

O programa foi desenvolvido sob medida para o Linux (Ubuntu/Debian) como alternativa leve, estável e intuitiva ao FortiClient oficial, trazendo compatibilidade total com o grupo Diffie-Hellman **MODP_8192 (DH Group 18)**.

---

## 🚀 Funcionalidades da Interface Gráfica

- **Conexão e Desconexão com 1 Clique:** Botões intuitivos e de alta resposta.
- **Indicador de Status em Tempo Real:** Mostra visualmente se a VPN está conectada e exibe o IP Virtual dinâmico atribuído pelo FortiGate (ex: `10.64.4.13`).
- **Campos Editáveis:** Permite configurar diretamente na tela:
  - Gateway VPN (IP Privado)
  - IP Local de Origem
  - Usuário (EAP-MSCHAPv2)
  - Senha
  - Chave Pré-compartilhada (PSK)
- **Acesso Direto ao Painel Web:** Botão **"🌐 Abrir Painel Web"** que abre automaticamente o endereço corporativo interno (`https://10.64.10.1:6464/login?redir=%2F`) no navegador padrão.
- **Validação de Conectividade:** Botão **"🔍 Validar Conexão Web"** que testa a resposta HTTP do painel interno via túnel em tempo real.
- **Console de Diagnóstico Integrado:** Caixa de logs na parte inferior para acompanhar a negociação IKEv2/ESP e eventuais mensagens do firewall.

---

## 📂 Estrutura do Projeto

```text
forticlient-vpn-linux/
├── .git/                           # Repositório Git (branch 'main')
├── .gitignore                      # Protege arquivos locais de credenciais (*.conf)
├── README.md                       # Documentação completa
├── install.sh                      # Instalador automatizado
├── uninstall.sh                    # Desinstalador
├── bin/
│   └── vpn-gui                     # Programa com Interface Gráfica (Python 3 / Tkinter)
├── config/
│   ├── forti.conf.example          # Modelo de configuração base para o swanctl
│   └── sudoers-vpn.example         # Exemplo de permissão sudo sem senha
└── assets/
    └── forticlient-vpn.desktop     # Atalho para Área de Trabalho e Menu GNOME
```

---

## 📋 Pré-requisitos

- **Sistema Operacional:** Ubuntu 20.04+, 22.04+, 24.04+ ou Debian 11/12.
- **Permissão de Administrador (`sudo`):** Necessária para o strongSwan criar os túneis IPsec no kernel.
- **Liberação de Rede:** O seu IP local (ex: `203.0.113.7`) deve estar autorizado no firewall corporativo.

---

## ⚡ Instalação Rápida

1. Clone ou copie este repositório para o seu computador:
   ```bash
   git clone <URL_DO_REPOSITORIO> forticlient-vpn-linux
   cd forticlient-vpn-linux
   ```

2. Execute o instalador:
   ```bash
   chmod +x install.sh uninstall.sh bin/vpn-gui
   ./install.sh
   ```

O instalador irá:
1. Instalar as dependências do sistema (`strongswan`, `strongswan-swanctl`, `python3-tk`, `curl`).
2. Copiar o aplicativo `vpn-gui` para `/usr/local/bin/`.
3. Criar os atalhos gráficos na **Área de Trabalho** e no **Menu de Aplicativos**.
4. Habilitar os serviços de rede do strongSwan.

---

## 🖥️ Como Usar

1. **Abrir o Programa:**
   - Dê um duplo-clique no ícone **FortiClient VPN** na sua Área de Trabalho; ou
   - Abra o terminal e digite:
     ```bash
     vpn-gui
     ```
2. **Conectar:**
   - Preencha ou confirme suas credenciais e o IP do Gateway.
   - Clique em **▶ CONECTAR VPN**.
   - Em poucos segundos, o indicador ficará verde indicando **CONECTADO** com o IP Virtual recebido.
3. **Acessar o Painel Web:**
   - Clique em **🌐 Abrir Painel Web (10.64.10.1:6464)** para abrir o navegador no sistema corporativo.
   - Ou clique em **🔍 Validar Conexão Web** para verificar se o serviço está respondendo com HTTP 200.
4. **Desconectar:**
   - Clique em **⏹ DESCONECTAR**.

---

## ⚙️ Configuração Manual (Opcional)

O aplicativo armazena as configurações no arquivo padrão do strongSwan:
`/etc/swanctl/conf.d/forti.conf`

```ini
connections {
    forticlient {
        version  = 2
        remote_addrs = 198.51.100.100       # Gateway Privado
        local_addrs  = 203.0.113.7         # IP Local autorizado
        proposals    = aes256-sha256-modp8192, aes256-sha256-modp4096, aes128-sha256-modp4096, aes256-sha256-modp2048, aes256-sha1-modp2048, aes128-sha256-modp2048
        encap        = yes
        mobike       = no
        dpd_delay    = 5s
        vips         = 0.0.0.0            # Dynamic VIP

        local {
            auth     = eap-mschapv2
            id       = seu_usuario
            eap_id   = seu_usuario
        }

        remote {
            auth = psk
            id   = %any
        }

        children {
            forticlient {
                remote_ts     = 0.0.0.0/0
                local_ts      = dynamic
                esp_proposals = aes256-sha256-modp8192, aes256-sha1-modp8192, aes128-sha256-modp8192, aes256-sha256, aes128-sha256
                dpd_action    = restart
                mode          = tunnel
            }
        }
    }
}

secrets {
    ike-forticlient { secret = "sua_chave_psk" }
    eap-forticlient { id = seu_usuario secret = "sua_senha" }
}
```

---

## 🗑️ Desinstalação

Caso precise desinstalar o aplicativo do sistema:
```bash
./uninstall.sh
```

---

## 📄 Licença

Uso institucional interno (DTIC / CBMPA / PRODEPA).
