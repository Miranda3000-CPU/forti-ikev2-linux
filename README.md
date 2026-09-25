# 🛡️ FortiClient VPN - DTIC / PRODEPA

Interface gráfica para conexão VPN IKEv2 (FortiGate) com autenticação
**EAP-MSCHAPv2 + PSK**. Não depende do FortiClient: o motor é o
[strongSwan](https://www.strongswan.org/) nos dois sistemas operacionais.

## Como funciona

|              | Linux                                       | Windows                                              |
| ------------ | ------------------------------------------- | ---------------------------------------------------- |
| Motor        | strongSwan do sistema (`swanctl`)           | strongSwan vendorizado em `vendor/windows/`           |
| Privilégio   | `sudo swanctl` (regras em `/etc/sudoers.d`) | GUI como usuário; UAC só para serviço/IKEEXT/VIP      |
| Configuração | `/etc/swanctl/conf.d/forti.conf`            | `%APPDATA%\FortiClientVPN\swanctl\conf.d\forti.conf`  |

A configuração `swanctl.conf` é **a mesma** nos dois sistemas.

### Por que não usar o IKEv2 nativo do Windows?

O cliente IKEv2 do próprio Windows só aceita certificado X.509 ou
EAP-MSCHAPv2, e **exige que o gateway se autentique com certificado**. Este
FortiGate se autentica com **PSK**, combinação que o Windows não suporta. Por
isso o motor é o strongSwan, que fala PSK + EAP-MSCHAPv2.

## Instalação

### Linux (Debian/Ubuntu)

```bash
./build/build_deb.sh
sudo dpkg -i dist/forticlient-vpn_1.0.0_amd64.deb
```

Ou, sem empacotar: `sudo ./install.sh`.

### Windows

Você **não precisa compilar nada**. Duas opções:

**Opção A — baixar pronto (recomendado)**
1. No repositório, abra a aba **Actions → "Instalador Windows" → Run workflow**.
2. Quando terminar, baixe o artefato **FortiClient-VPN-Setup**.
3. Leve o `FortiClient-VPN-Setup.exe` para o Windows e execute (aceite o UAC).

**Opção B — gerar na sua máquina com um comando**
```bash
./build/preparar_instalador_windows.sh
```
Esse único comando instala o que faltar (MinGW, Wine), compila o motor
strongSwan, instala Python e Inno Setup dentro do Wine e gera
`dist/FortiClient-VPN-Setup.exe`.

O instalador registra e **inicia** o serviço `strongSwan IKE service`, libera as
portas UDP 500/4500 e remove resíduos de versões antigas. O aplicativo ainda se
recupera sozinho se algo faltar: sobe o motor em segundo plano, para o serviço
`IKEEXT` por dois caminhos diferentes, tenta instalar o IP virtual em todas as
interfaces ativas e, se não conseguir em nenhuma, conecta mesmo assim.

## Como usar

1. Preencha **Gateway**, **Chave PSK**, **Usuário** e **Senha**.
2. Clique **▶ CONECTAR VPN**.
3. **Opções Avançadas** contém o IP local (detecção automática) e a estratégia
   de VIP.

### Modo sem interface (diagnóstico)

O executável do Windows é GUI, então falhas não aparecem em terminal. Use:

```bat
FortiClient-VPN.exe --diagnose     :: gera um .zip com tudo que é preciso
FortiClient-VPN.exe --connect      :: conecta com as credenciais salvas
FortiClient-VPN.exe --disconnect
FortiClient-VPN.exe --cleanup      :: remove resíduos de versões antigas
```

O log fica em `%LOCALAPPDATA%\FortiClientVPN\logs\app.log` (Windows) e
`~/.local/state/forticlient-vpn/logs/app.log` (Linux).

## Compilação

### Linux

```bash
./build/build_deb.sh         # gera dist/forticlient-vpn_1.0.0_amd64.deb
```

### Windows (a partir do Linux ou pelo CI)

**Um comando, sem preparar nada:**
```bash
./build/preparar_instalador_windows.sh     # gera dist/FortiClient-VPN-Setup.exe
```

Ou deixe o **GitHub Actions** fazer (aba *Actions → Instalador Windows*):
o workflow compila o motor com MSYS2, roda os testes, gera o `.exe` e publica o
instalador como artefato.

Passos manuais (só se quiser controle fino):
```bash
sudo apt install build-essential mingw-w64 wine curl bzip2 perl make
./build/build_strongswan_windows.sh        # motor strongSwan para Windows
./build/build_windows.sh                   # .exe (PyInstaller/Wine) + instalador
```
`ISCC=/caminho/ISCC.exe`, `WINE_PYTHON=C:/Python312/python.exe` e
`WINE_BIN=wine` permitem ajustar caminhos.

## Testes

```bash
python3 -m unittest discover -s tests -v
```

## Limitações conhecidas no Windows

- **IP virtual:** o backend `kernel-iph` do strongSwan no Windows não instala
  VIPs de cliente, então o aplicativo faz isso em cascata (interface padrão →
  demais interfaces ativas → seguir sem VIP). Nada precisa ser decidido por
  você; o resultado aparece no log.
- **Serviço `IKEEXT`:** é interrompido na instalação e reconferido a cada
  conexão, pois ocupa as portas UDP 500/4500. É restaurado na desinstalação.
- **SmartScreen:** o instalador não é assinado digitalmente. O Windows pode
  exibir aviso em *Mais informações → Executar assim mesmo*. A solução
  definitiva é assinar com um certificado interno (`signtool`).
- **Licença:** o strongSwan é GPLv2 — ver `NOTICE` antes de redistribuir.

## Diagnóstico de problemas

| Sintoma                              | Causa provável / ação                            |
| ------------------------------------ | ------------------------------------------------ |
| "Motor strongSwan não encontrado"    | `vendor/windows` ausente — reinstale o pacote.    |
| "Conflito de portas IKE (`IKEEXT`)"  | `sc stop IKEEXT` (o app tenta automaticamente).   |
| "Falha de autenticação"              | Usuário/senha, ou PSK incorreta.                  |
| "Tempo esgotado"                     | Gateway inacessível ou UDP 500/4500 bloqueado.    |
| "CHILD_SA config 'forticlient' not found" | O swanctl não encontrou o `conf.d` — ver abaixo. |
| Status fica "DESCONECTADO" conectado | Envie o `--diagnose`; veja `swanctl --list-sas`.  |

### Onde o swanctl procura a configuração (já resolvido no código)

O `swanctl` resolve o diretório de configuração assim:

```
file        = <swanctl_dir>/strongswan.conf   # aborta se não encontrar
swanctl_dir = dirname(file)                   # passa a valer este
conexões    = <swanctl_dir>/conf.d/*.conf
```

Ou seja, `conf.d/` é **irmão direto** do `strongswan.conf` que ele encontrou. Se
o `swanctl.exe` for executado na pasta do motor, ele acha o `strongswan.conf` de
lá e procura `conf.d/` no lugar errado: carrega **zero conexões**, retorna
código 0 (sem erro) e só falha depois, no `--initiate`.

Por isso o aplicativo grava e executa sempre a partir de:

```
%APPDATA%\FortiClientVPN\strongswan.conf
%APPDATA%\FortiClientVPN\conf.d\forti.conf
```

com `cwd` e `SWANCTL_DIR` apontando para `%APPDATA%\FortiClientVPN` — o mesmo
lugar, pelas duas formas de resolução.

Sempre que possível, anexe o `.zip` gerado por **Exportar diagnóstico**.

## Estrutura do projeto

- `vpn-gui.py`: interface gráfica, modo CLI e empacotamento.
- `vpn_engine.py`: motor VPN (configuração, comandos, status, erros).
- `vpn_config.py`: credenciais (DPAPI no Windows), logging e diagnóstico.
- `build/`: empacotamento (`build_deb.sh`, `build_windows.sh`,
  `build_strongswan_windows.sh`, spec do PyInstaller, Inno Setup).
- `vendor/windows/`: motor strongSwan para Windows (não versionado).
- `tests/`: testes unitários.
- `debian/`, `config/`, `assets/`: empacotamento Linux, exemplos e ícones.

## Licença

Distribuído sob licença interna. Componentes de terceiros em `NOTICE`.
