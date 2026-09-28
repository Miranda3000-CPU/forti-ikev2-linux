# 🛡️ FortiClient VPN - DTIC / PRODEPA

Interface gráfica para conexão VPN IKEv2 (FortiGate) com autenticação
**EAP-MSCHAPv2 + PSK**. Não depende do FortiClient: o motor é o
[strongSwan](https://www.strongswan.org/) nos dois sistemas operacionais.

## Instalação

**Você não precisa compilar nada.** Baixe o instalador pronto da
[**última release**](https://github.com/Miranda3000-CPU/forti-ikev2-linux/releases/latest):

| Sistema           | Arquivo                             | Como instalar                                              |
| ----------------- | ----------------------------------- | ---------------------------------------------------------- |
| Windows 10/11 x64 | `FortiClient-VPN-Setup.exe`         | Execute e aceite o UAC                                     |
| Debian / Ubuntu   | `forticlient-vpn_<versão>_all.deb` | `sudo apt install ./forticlient-vpn_<versão>_all.deb`      |

Cada release traz também `SHA256SUMS` (para conferir a integridade) e o tarball
do strongSwan, exigido pela GPLv2 — ver [Licença](#licença).

<details>
<summary>Instalar a partir do código-fonte</summary>

```bash
# Linux: gera dist/forticlient-vpn_<versão>_all.deb
./build/build_deb.sh
sudo apt install ./dist/forticlient-vpn_*.deb

# ou, sem empacotar:
sudo ./install.sh
```

No Windows, `./build/preparar_instalador_windows.sh` faz tudo em um comando
(instala MinGW/Wine, compila o motor, instala Python e Inno Setup no Wine e
gera `dist/FortiClient-VPN-Setup.exe`).

</details>

O instalador do Windows registra e **inicia** o serviço `strongSwan IKE service`,
libera as portas UDP 500/4500 e remove resíduos de versões antigas. O
aplicativo ainda se recupera sozinho se algo faltar: sobe o motor em segundo
plano, para o serviço `IKEEXT` por dois caminhos diferentes, tenta instalar o IP
virtual em todas as interfaces ativas e, se não conseguir em nenhuma, conecta
mesmo assim.

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

## Como usar

1. Preencha **Gateway**, **Chave PSK**, **Usuário** e **Senha**.
2. Clique **▶ CONECTAR VPN**.
3. **Opções Avançadas** contém o IP local (detecção automática) e a estratégia
   de VIP.

As credenciais ficam guardadas no próprio computador — DPAPI no Windows, arquivo
com `0600` no Linux — e não são enviadas a lugar nenhum além do seu gateway.

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

A versão vive em um único lugar, o arquivo [`VERSION`](VERSION) na raiz. O
`build/gen_build_info.py` a propaga para o `build_info.py` (gravado no
executável), para o `AppVersion` do instalador Windows e para o `Version` do
`.deb` — assim não há como Linux e Windows saírem com versões diferentes. O CI
falha se algum desses divergir.

```bash
# Linux: dist/forticlient-vpn_<versão>_all.deb
./build/build_deb.sh

# Windows a partir do Linux, um comando (instala MinGW, Wine, Python e Inno Setup)
./build/preparar_instalador_windows.sh

# Só os metadados (após editar ./VERSION)
python3 build/gen_build_info.py
```

O atalho **"Abrir Painel Web"** / **"Validar HTTP"** só entra no build se você
defini-lo na compilação via `FCT_WEB_URL`. O padrão é vazio — os artefatos
públicos não embutem nenhum endereço interno:

```bash
# Build público (sem painel embutido) — padrão
python3 build/gen_build_info.py

# Build interno do time (painel FortiOS embutido)
FCT_WEB_URL='https://seu-fortigate:10443/login?redir=%2F' python3 build/gen_build_info.py
```

O **GitHub Actions** faz tudo sozinho: compila o motor com MSYS2, roda os
testes, gera o `.exe` e o `.deb`, e ao criar uma tag `v<versão>` publica os dois
como **Release** (junto do tarball do strongSwan, exigido pela GPLv2).

Passos manuais do Windows (só se quiser controle fino):
```bash
sudo apt install build-essential mingw-w64 wine curl bzip2 perl make
./build/build_strongswan_windows.sh        # motor strongSwan para Windows
./build/build_windows.sh                   # .exe (PyInstaller/Wine) + instalador
```
`ISCC=/caminho/ISCC.exe`, `WINE_PYTHON=C:/Python312/python.exe` e
`WINE_BIN=wine` permitem ajustar caminhos.

### Publicar uma release

```bash
echo 2.2.0 > VERSION
python3 build/gen_build_info.py     # propaga para .iss e debian/control
git commit -am "release: 2.2.0"
git tag v2.2.0 && git push origin main --tags
```

O CI exige que a tag corresponda a `VERSION`; se divergir, a release falha.

## Assinatura de código do Windows

Sem certificado, o Windows exibe "O Windows protegeu o seu PC" e o usuário
precisa clicar em **Mais informações → Executar assim mesmo**. Isso é
esperado: **a assinatura não sai de um script, ela vem de um certificado
emitido por uma autoridade que o Windows confia.**

O que é preciso ter:

1. **Certificado de assinatura de código** (X.509 com a EKU
   `1.3.6.1.5.5.7.3.3`). Opções:
   - **CA interna da DTIC/PRODEPA** — gratuita, e o resultado é um instalador
     sem aviso **nas máquinas do domínio**, desde que a raiz seja publicada
     por GPO em *Autoridades de Certificação Raiz Confiáveis* e
     *Editores Confiáveis*. É a via indicada para uso interno no governo.
   - **CA pública** (DigiCert, Sectigo, GlobalSign, SSL.com, ou ICP-Brasil
     via authority national) — funciona fora do domínio, custo de centenas
     de reais/ano, exige documentação da pessoa jurídica.
   - **SignPath Foundation** — gratuita, mas para projetos open source
     elegíveis (GPLv3 + repositório público) e sujeita a aprovação.
2. **A chave privada** em PFX, guardada no cofre de segredos do repositório
   (`FCT_SIGN_PFX_BASE64`, `FCT_SIGN_PASS`) — nunca no Git. O ideal é um
   token/HSM ou um serviço de assinatura; PFX em disco é o piso aceitável.
3. **Carimbo de tempo RFC 3161** (padrão: `timestamp.digicert.com`). Sem ele a
   assinatura deixa de valer quando o certificado expira.

Assinar localmente:

```bash
FCT_SIGN_PFX=cert.pfx FCT_SIGN_PASS=... ./build/sign_windows.sh
```

O script assina **o executável e o instalador** — o instalador sem assinatura
continua disparando o alerta mesmo que o `.exe` dentro dele esteja assinado.
Ele usa `osslsigncode` (`apt install osslsigncode`) ou `signtool` do Windows
SDK, e roda depois do Inno Setup, nunca antes.

**Os binários do strongSwan em `vendor/windows/` não são assinados.** São
terceiros (GPLv2) e selar com o certificado da DTIC deturparia a
procedência. O `SOURCE-OFFER` e o tarball correspondente viajam na release.

No CI, um build de tag **falha** se não houver certificado configurado, para
não publicar release não assinada por engano.

Expectativa realista: mesmo com certificado novo, o SmartScreen pode avisar
por um tempo, porque a reputação se constrói com volume de downloads.

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

## Diagnóstico de problemas

| Sintoma                              | Causa provável / ação                            |
| ------------------------------------ | ------------------------------------------------ |
| "Motor strongSwan não encontrado"    | `vendor/windows` ausente — reinstale o pacote.    |
| "Conflito de portas IKE (`IKEEXT`)"  | `sc stop IKEEXT` (o app tenta automaticamente).   |
| "Falha de autenticação"              | Usuário/senha, ou PSK incorreta.                  |
| "Tempo esgotado"                     | Gateway inacessível ou UDP 500/4500 bloqueado.    |
| "CHILD_SA config 'forticlient' not found" | O swanctl não encontrou o `conf.d` — ver abaixo. |
| Status fica "DESCONECTADO" conectado | Envie o `--diagnose`; veja `swanctl --list-sas`.  |

### Onde está o log do motor (Windows)

O `app.log` registra o que **o aplicativo** fez. O que o **motor** respondeu
vive em outro arquivo, e é lá que está a causa real de uma falha de IKE:

```
C:\ProgramData\FortiClientVPN\charon.log
```

O pacote `diagnostico-<data>.zip` já anexa as últimas 200 linhas desse arquivo
como `log do charon (ultimas linhas)`, e a mensagem de falha da conexão
aponta o caminho. Sem ele, uma falha de autenticação ou de proposta aparecia
apenas como "tempo esgotado".

O `strongswan.conf` do motor fica em `vendor\windows\strongswan.conf`. Como o
`charon-svc` é registrado como serviço **sem argumentos**, ele lê a
configuração de onde está o executável e **apenas no arranque** — por isso o
aplicativo regrava esse arquivo e reinicia o serviço quando o `path` do log
está faltando.

| Código IKE no log                    | Significado                                    |
| ------------------------------------ | ---------------------------------------------- |
| `AUTHENTICATION_FAILED`              | Usuário, senha ou PSK divergentes.             |
| `NO_PROPOSAL_CHOSEN`                 | Propostas criptográficas incompatíveis.        |
| `ID_MISMATCH`                        | O `local-id` do FortiGate não bate.            |
| `TS_UNACCEPTABLE`                    | O FortiGate recusou a faixa de tráfego.        |
| Retransmissões sem resposta alguma   | Caminho de rede bloqueado (ver `pktmon`).      |

**Para distinguir "não chega" de "chega e é rejeitado"**, a sonda em TCP não
serve: IKEv2 é exclusivamente UDP (500/4500) e um FortiGate saudável não tem
listener TCP nessas portas, então o timeout do TCP é o resultado esperado. Use
captura de pacote:

```powershell
pktmon start --capture --comp nics --pkt-size 0 --file-name C:\Temp\ike.etl
# conecte na GUI
pktmon stop
pktmon etl2txt C:\Temp\ike.etl -o C:\Temp\ike.txt
Select-String "500|4500" C:\Temp\ike.txt
```

Nada voltando = firewall/rota/ACL por IP de origem. Resposta no IKE_SA_INIT
seguida de nada no IKE_AUTH = o servidor recebeu e recusou.

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

- `VERSION`: versão do projeto — fonte única, propagada para `.deb`, `.exe` e executável.
- `vpn-gui.py`: interface gráfica, modo CLI e empacotamento.
- `vpn_engine.py`: motor VPN (configuração, comandos, status, erros).
- `vpn_config.py`: credenciais (DPAPI no Windows), logging e diagnóstico.
- `build/`: empacotamento (`build_deb.sh`, `build_windows.sh`,
  `build_strongswan_windows.sh`, `gen_build_info.py`, spec do PyInstaller, Inno Setup).
- `vendor/windows/`: motor strongSwan para Windows (binários não versionados).
- `tests/`: testes unitários.
- `debian/`, `config/`, `assets/`: empacotamento Linux, exemplos e ícones.
- `.github/workflows/build.yml`: testes, artefatos e publicação da release.

## Segurança e segredos

`config/forti.conf` guarda o PSK e a senha do gateway reais. Ele **não** é
versionado (ver `.gitignore`) e o CI falha se ele entrar no índice. Use
`config/forti.conf.example` como modelo e preencha o arquivo local — ou,
melhor ainda, digite as credenciais na interface, que as guarda protegidas
(DPAPI no Windows, arquivo com `0600` no Linux).

Se um segredo já entrou no histórico, `git log` ainda o mostra. Remover o arquivo
do índice não basta: é preciso reescrever o histórico (`git filter-repo`) e
**rotacionar a credencial no FortiGate**.

## Licença

Este projeto é distribuído sob a **GNU GPLv3 ou superior** — ver
[`LICENSE`](LICENSE). Copyright (C) 2026 DTIC / PRODEPA.

O instalador do Windows distribui o motor **strongSwan** (GPLv2) como programa
separado; cada release publica o tarball do fonte correspondente para cumprir a
GPLv2. Ver [`NOTICE`](NOTICE) e [`SOURCE-OFFER.txt`](SOURCE-OFFER.txt).

"Fortinet", "FortiGate" e "FortiClient" são marcas da Fortinet, Inc. Este projeto
é independente e não é endossado pela Fortinet.
