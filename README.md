# 🛡️ FortiClient VPN Manager (Container Edition)

Uma solução completa, independente e conteinerizada (Docker) para conexão a VPNs corporativas **FortiGate (Fortinet)** via protocolo **IKEv2 / IPsec**, utilizando autenticação dupla (**Pre-Shared Key + EAP-MSCHAPv2**) e IP Virtual dinâmico (CPRP).

Projetada para funcionar em **qualquer máquina Linux com Docker instalado**, sem a necessidade de instalar manualmente dependências, bibliotecas ou serviços no sistema operacional host.

---

## 🌟 Principais Vantagens do Container

- **Portabilidade Total:** Funciona de forma idêntica em qualquer distribuição Linux (Ubuntu, Debian, Fedora, Arch, AlmaLinux, openSUSE, etc.) com Docker.
- **Isolamento de Dependências:** O daemon do strongSwan, swanctl, bibliotecas de cifras avançadas e Python/Tkinter rodam 100% isolados dentro do container.
- **Modo de Rede Host (`network_mode: host`):** O túnel IPsec criado no container é compartilhado com a máquina host, permitindo que navegadores e ferramentas do seu sistema acessem serviços internos (ex: `https://10.64.10.1:6464`) de forma transparente.
- **Interface Gráfica Dupla:**
  1. **Desktop GUI (Tkinter):** Abre diretamente como uma janela nativa no seu desktop (via X11).
  2. **Web GUI (Navegador):** Painel web responsivo disponível em **`http://localhost:8080`**, acessível de qualquer navegador.

---

## 📂 Estrutura do Repositório

```text
forticlient-vpn-linux/
├── .git/                           # Repositório Git (branch 'main')
├── .gitignore                      # Protege arquivos com senhas locais (*.conf)
├── Dockerfile                      # Definição da imagem com Debian, strongSwan e GUI
├── docker-compose.yml              # Orquestração do container com privilégios de rede
├── entrypoint.sh                   # Inicialização do daemon charon e da aplicação
├── run.sh                          # Script prático de 1 comando para subir a aplicação
├── install.sh                      # Instalador de atalhos no Desktop e comando global
├── uninstall.sh                    # Desinstalador
├── README.md                       # Documentação completa
├── app/
│   └── vpn-gui.py                  # Aplicação gráfica (Tkinter + Web Server HTTP 8080)
├── config/
│   ├── forti.conf.example          # Modelo de configuração para o swanctl
│   └── forti.conf                  # Arquivo montado e persistido no container
└── assets/
    └── forticlient-vpn.desktop     # Atalho para Área de Trabalho e Menu GNOME
```

---

## 📋 Pré-requisitos

- **Docker** e **Docker Compose** instalados na máquina:
  ```bash
  docker --version
  docker compose version
  ```
- O seu IP local na rede interna (ex: `203.0.113.7`) deve estar liberado nas regras do firewall do FortiGate.

---

## ⚡ Como Rodar (Início Rápido)

### 1. Clonar o Repositório
```bash
git clone <URL_DO_REPOSITORIO> forticlient-vpn-linux
cd forticlient-vpn-linux
```

### 2. Iniciar a Aplicação
Basta executar o script de inicialização:
```bash
chmod +x run.sh
./run.sh
```
ou diretamente via Docker Compose:
```bash
docker compose up --build
```

O container irá:
1. Conceder permissão local para exibição gráfica no X11.
2. Iniciar o daemon de IPsec (`charon`) isoladamente.
3. Abrir a janela gráfica **FortiClient VPN** na sua tela.
4. Disponibilizar a interface web em **`http://localhost:8080`**.

---

## 🖥️ Utilização

### Pela Janela Desktop (Tkinter)
- Clique em **▶ CONECTAR VPN**.
- Quando o indicador ficar verde, o IP virtual dinâmico (ex: `10.64.4.13`) estará ativo.
- Clique em **🌐 Abrir Painel Web (10.64.10.1:6464)** para copiar a URL e abrir o navegador.
- Clique em **🔍 Validar Conexão Web** para verificar se o serviço interno respondeu com `HTTP 200 OK`.

### Pelo Navegador (Web UI)
- Abra no seu navegador: **`http://localhost:8080`**
- Tenha os mesmos controles de conexão, status, edição de credenciais, logs e link direto para o painel corporativo.

---

## ⚙️ Configurações e Persistência

As configurações são salvas em `config/forti.conf` e persistidas fora do container.

### Exemplo de Configuração (`config/forti.conf`):

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

## 📌 Instalação do Atalho na Área de Trabalho (Opcional)

Para criar um atalho na Área de Trabalho e poder executar com dois cliques:
```bash
./install.sh
```

---

## 🗑️ Desinstalação

Para parar o container e remover os atalhos criados:
```bash
./uninstall.sh
```

---

## 📄 Licença

Uso institucional interno (DTIC / CBMPA / PRODEPA).
