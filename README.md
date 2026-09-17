# 🛡️ FortiClient IKEv2 VPN Manager para Linux (Ubuntu / Debian)

Uma solução nativa, leve e robusta para conexão a VPNs corporativas **FortiGate (Fortinet)** utilizando o protocolo **IKEv2 / IPsec** com autenticação dupla (**Pre-Shared Key + EAP-MSCHAPv2**) e alocação dinâmica de IP Virtual (DHCP / CPRP).

O projeto inclui uma **Interface Gráfica (GUI em Tkinter)** e um utilitário de **Linha de Comando (CLI)** projetados especificamente para substituir a versão oficial do FortiClient no Linux, oferecendo suporte total a algoritmos avançados como **Diffie-Hellman Group 18 (MODP_8192)**.

---

## 🚀 Funcionalidades

- **100% Nativo no Linux:** Utiliza o subsistema de rede do kernel Linux (XFRM) e a biblioteca moderna `swanctl` do strongSwan (sem containers Docker desnecessários).
- **Interface Gráfica Moderna (GUI):**
  - Conexão e desconexão com 1 clique.
  - Status em tempo real do túnel (com detecção do IP Virtual atribuído).
  - Edição instantânea de parâmetros (Gateway Privado, IP de Origem, Usuário EAP, Senha, Chave PSK).
  - Botão de abertura direta do Painel Web interno no navegador padrão.
  - Botão de validação de conectividade Web (HTTP status code).
  - Terminal de logs e diagnóstico integrado.
- **Linha de Comando Amigável (`vpn`):**
  - `vpn connect`: Inicia o túnel e sincroniza credenciais.
  - `vpn disconnect`: Encerra a conexão de forma limpa.
  - `vpn status`: Mostra status do túnel, IP virtual atribuído e detalhes das SAs IKE/ESP.
  - `vpn test`: Valida o tráfego dentro do túnel contra o painel interno.
  - `vpn logs`: Acompanha o journal do strongSwan em tempo real.
  - `vpn gui`: Abre a interface gráfica.
- **Segurança Reforçada:**
  - Armazenamento de credenciais protegido com permissões restritas (`chmod 600`).
  - Suporte ao grupo Diffie-Hellman **MODP_8192** (Group 18) e cifras AES-256.

---

## 📂 Estrutura do Projeto

```text
forticlient-vpn-linux/
├── .gitignore                      # Ignora arquivos de credenciais e caches
├── install.sh                      # Script de instalação automatizada
├── uninstall.sh                    # Script de desinstalação
├── README.md                       # Documentação completa
├── bin/
│   ├── vpn                         # Utilitário CLI (Bash)
│   └── vpn-gui                     # Interface Gráfica (Python / Tkinter)
├── config/
│   ├── forti.conf.example          # Modelo de configuração para o swanctl
│   └── sudoers-vpn.example         # Modelo de permissões sudo sem senha
└── assets/
    └── forticlient-vpn.desktop     # Atalho para Área de Trabalho e Menu GNOME
```

---

## 📋 Pré-requisitos

- **Sistema Operacional:** Ubuntu 20.04+, 22.04+, 24.04+ ou Debian 11/12.
- **Privilégios de Administrador (`sudo`):** Necessário para interagir com as interfaces de rede e carregar túneis IPsec no kernel.
- **Liberação de Rede:** O seu IP local de rede interna (ex: `203.0.113.7`) deve estar devidamente autorizado no firewall do FortiGate de destino.

---

## ⚡ Instalação Rápida

1. Clone o repositório ou copie a pasta para sua máquina:
   ```bash
   git clone <URL_DO_REPOSITORIO> forticlient-vpn-linux
   cd forticlient-vpn-linux
   ```

2. Torne os scripts executáveis e rode o instalador:
   ```bash
   chmod +x install.sh uninstall.sh bin/*
   ./install.sh
   ```

O instalador irá:
- Instalar os pacotes necessários (`strongswan`, `strongswan-swanctl`, `python3-tk`, `curl`).
- Copiar `vpn` e `vpn-gui` para `/usr/local/bin/`.
- Instalar os atalhos gráficos na Área de Trabalho e no menu de aplicativos.
- Configurar o serviço systemd do strongSwan.

---

## ⚙️ Configuração

As configurações do túnel residem em `/etc/swanctl/conf.d/forti.conf`. Você pode editá-las diretamente pela interface gráfica ou manualmente no arquivo.

### Exemplo de Configuração (`/etc/swanctl/conf.d/forti.conf`):

```ini
connections {
    forticlient {
        version  = 2
        remote_addrs = 198.51.100.100       # IP Privado do Gateway FortiGate
        local_addrs  = 203.0.113.7         # Seu IP local autorizado
        
        # Propostas da Fase 1 (IKE SA) - MODP_8192 é a preferencial do FortiGate
        proposals    = aes256-sha256-modp8192, aes256-sha256-modp4096, aes128-sha256-modp4096, aes256-sha256-modp2048, aes256-sha1-modp2048, aes128-sha256-modp2048
        encap        = yes
        mobike       = no
        dpd_delay    = 5s
        keyingtries  = 0
        rekey_time   = 86400s

        # 0.0.0.0 instrui o FortiGate a alocar um IP virtual dinâmico (CPRP)
        vips = 0.0.0.0

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
                rekey_time    = 43200s
            }
        }
    }
}

secrets {
    ike-forticlient {
        secret = "sua_chave_psk"
    }
    eap-forticlient {
        id     = seu_usuario
        secret = "sua_senha"
    }
}
```

> **Atenção:** Mantenha o arquivo com permissão restrita para proteger as senhas:
> ```bash
> sudo chmod 600 /etc/swanctl/conf.d/forti.conf
> ```

---

## 💻 Como Usar

### Modo Gráfico (GUI)
- Dê um duplo-clique no ícone **FortiClient VPN** na sua Área de Trabalho ou execute no terminal:
  ```bash
  vpn-gui
  ```
- Clique em **CONECTAR VPN**. O status mudará para verde indicando o IP virtual recebido (ex: `10.64.4.13`).
- Use o botão **🌐 Abrir Painel Web** para abrir a URL interna diretamente no navegador.
- Use o botão **🔍 Validar Conexão Web** para checar se o servidor respondeu com `HTTP 200 OK`.

### Modo Linha de Comando (CLI)
- **Conectar à VPN:**
  ```bash
  vpn connect
  ```
- **Verificar Status e IP Virtual:**
  ```bash
  vpn status
  ```
- **Testar Acesso Web ao Serviço Interno:**
  ```bash
  vpn test
  ```
- **Desconectar:**
  ```bash
  vpn disconnect
  ```
- **Acompanhar Logs em Tempo Real:**
  ```bash
  vpn logs
  ```

---

## 🔍 Resolução de Problemas (Troubleshooting)

| Sintoma | Causa Mais Comum | Solução |
| :--- | :--- | :--- |
| `NO_PROPOSAL_CHOSEN` | O FortiGate rejeitou as cifras ou o IP de origem não está na lista de permissão. | Verifique se está usando o IP de Gateway Privado (`198.51.100.100`) e se o seu IP local (`203.0.113.7`) foi liberado pelo administrador do firewall. |
| Timeout na porta 500 / 4500 | Rota bloqueada ou gateway incorreto. | Certifique-se de que a rota até o IP privado `198.51.100.100` está ativa. |
| Ping não responde | Políticas de firewall do FortiGate bloqueiam pacotes ICMP internamente. | Use `vpn test` ou o botão de validação HTTP da GUI. O tráfego HTTPS funciona mesmo quando o ping é descartado. |

---

## 🗑️ Desinstalação

Para desinstalar o programa e remover os binários do sistema:
```bash
./uninstall.sh
```

---

## 📄 Licença

Uso interno institucional (DTIC / CBMPA / PRODEPA).
Desenvolvido para ambiente Linux corporativo.
