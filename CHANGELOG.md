# Changelog

Todas as mudanças relevantes deste projeto. O formato segue
[Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/) e o versionamento
segue [SemVer](https://semver.org/lang/pt-BR/).

A versão é declarada em [`VERSION`](VERSION) e propagada para o `.deb`, para o
instalador Windows e para o executável.

## [Não publicado]

### Corrigido

- **Endereço do Painel FortiOS saía no artefato público.** O atalho
  "Abrir Painel Web" trazia um endereço interno hardcoded, que ia parar dentro
  do `.exe` e do `.deb`. Agora a URL só entra no build via `FCT_WEB_URL`
  (builds internos do time); o padrão é vazio, então o público compila sem
  nenhum endereço interno. O default do Subject do certificado de assinatura
  também deixou de apontar para o host interno do governo.
- **O log do daemon não era gravado em lugar nenhum.** O `filelog` do
  `strongswan.conf` não tinha `path`, e um bloco sem `path` não escreve nada.
  Efeito prático: uma falha de IKE real produzia um pacote de diagnóstico com
  163 KB de `app.log` e **zero** linha de erro, porque o único registro do
  motivo (`AUTHENTICATION_FAILED`, `NO_PROPOSAL_CHOSEN`, `ID_MISMATCH`,
  `TS_UNACCEPTABLE`) é o log do charon. Agora o `path` aponta para
  `%ProgramData%\FortiClientVPN\charon.log` e o `diagnostico-<data>.zip`
  inclui as últimas 200 linhas desse arquivo.
- **`keyingtries` infinito impedia o motor de reportar a causa da falha.** Com
  `keyingtries = 0` a SA retransmite para sempre e o `--initiate` só retorna no
  timeout de 90 s do aplicativo, sempre como "timeout", sem nunca expor o
  notify do servidor. Passou para 3 (padrão do strongSwan), que faz o daemon
  desistir e devolver o erro real.
- **SAs penduradas de tentativas anteriores sobreviviam a um novo `--initiate`.**
  Numa tentativa interrompida no meio sobrava meia SA viva: em campo foram
  observadas duas simultâneas, uma delas já com o IP local obsoleto. Elas
  somavam retransmisses, competiam pelas portas 500/4500 e tornavam o
  `--list-sas` do diagnóstico ambíguo. Agora o `_connect_windows` encerra a SA
  pendurada antes de carregar a configuração.
- **O `strongswan.conf` do daemon é regravado quando falta `path`, com reinício
  do serviço.** O `charon-svc` é registrado sem argumentos, então lê a
  configuração do diretório do executável e **apenas no arranque** — grava-lo
  não bastava. Uma instalação antiga continuava com o conf antigo e sem log.
- A mensagem de falha da conexão agora **aponta o caminho do `charon.log`**. O
  stdout do `swanctl` nem sempre traz o notify do servidor, e sem essa pista o
  usuário só tinha a palavra "timeout" para investigar.

## [2.1.2] — primeira versão publicada em repositório público

### Adicionado

- **Instaladores prontos para download**, sem compilar: `FortiClient-VPN-Setup.exe`
  (Windows x64) e `forticlient-vpn_<versão>_all.deb` (Debian/Ubuntu).
- Pipeline único `.github/workflows/build.yml`: testes, empacotamento do `.deb`,
  compilação do instalador Windows com MSYS2 e publicação da **Release** ao
  criar uma tag `v<versão>`.
- `VERSION` como fonte única da versão, propagada por `build/gen_build_info.py`
  para o `build_info.py`, o `AppVersion` do Inno Setup e o `Version` do
  `debian/control`. O CI falha se algum desses divergir.
- `SHA256SUMS` e o tarball do strongSwan anexados a cada release, para
  satisfazer a GPLv2 §2 (fonte correspondente do binário embarcado).
- `debian/changelog` e `debian/copyright`; o `.deb` passa a ser instalável por
  `apt` com metadados válidos.
- Ícone do aplicativo instalado em `hicolor/256x256/apps` e em `pixmaps`, com
  `update-desktop-database`/`gtk-update-icon-cache` no `install.sh`.
- Documentação de licença: `LICENSE` (GPLv3), `NOTICE` reescrito e
  `SOURCE-OFFER.txt` (oferta escrita de fonte, GPLv2 §3(b)).
- Verificação no CI de que `config/forti.conf` (PSK e senha do gateway) não está
  versionado.

### Corrigido

- **Segredos de produção removidos do histórico do git.** `config/forti.conf`
  estava versionado com o PSK e a senha EAP do gateway; blobs antigos em
  `app/vpn-gui.py`, `bin/vpn-gui` e `bin/vpn` também carregavam os valores.
  > **A credencial que estava exposta precisa ser rotacionada no FortiGate** —
  > remover do histórico não invalida o que já foi publicado.
- Versões divergentes: o `.deb` era `1.0.0` e o instalador Windows `2.1.2`.
- O `.deb` reportava a versão como `dev`: `build_info.py` não era gerado nem
  empacotado no Linux.
- Ícone do atalho do menu não aparecia: o `.desktop` declara
  `Icon=forticlient-vpn` e nada era instalado nos temas do sistema. O
  `uninstall.sh` já removia esses caminhos, o que confirmava a intenção.
- `build/deb` era empacotado com um nível `payload/` a mais, quebrando o layout
  do pacote.
- `Architecture: all` no `control` com arquivo nomeado `_amd64.deb`.
- Permissões 664 da árvore de trabalho vazando para dentro do `.deb`.
- Filtro `paths` no workflow, que impedia a release de rodar em push de tag.
- `A && B` num passo de CI sob `set -e`, que abortava o passo inteiro quando
  `A` falhava de forma esperada.

### Segurança

- IPs internos reais (gateway e host) trocados por faixas reservadas para
  documentação (RFC 5737) em código, exemplo e testes.

[Não publicado]: https://github.com/Miranda3000-CPU/forti-ikev2-linux/compare/v2.1.2...HEAD
[2.1.2]: https://github.com/Miranda3000-CPU/forti-ikev2-linux/releases/tag/v2.1.2
