# FortiClient VPN — DTIC

Cliente VPN **IKEv2** para FortiGate, com autenticação **EAP-MSCHAPv2 + PSK**.
Não é o FortiClient da Fortinet: o motor é o [strongSwan](https://www.strongswan.org/),
o mesmo nos dois sistemas.

> Projeto independente. "Fortinet", "FortiGate" e "FortiClient" são marcas da
> Fortinet, Inc. Este projeto **não** é endossado pela Fortinet.

## O que baixar

Cada release traz quatro arquivos:

| Arquivo | Sistema | O que é |
| --- | --- | --- |
| `FortiClient-VPN` | Linux | Aplicativo em um arquivo só |
| `install-linux.sh` | Linux | Instala dependências, regras e atalho do menu |
| `FortiClient-VPN.exe` | Windows | Aplicativo em um arquivo só, com o motor embutido |
| `SHA256SUMS` | — | Checksums para conferir a integridade |

Confira sempre o download antes de usar:

```bash
sha256sum -c SHA256SUMS --ignore-missing
```

## Linux

O aplicativo é um arquivo único, mas ele fala com o **strongSwan do sistema** —
e é o `install-linux.sh` que instala isso (pacote + regras do sudoers + atalho
do menu). Sem essas regras o aplicativo não consegue operar a VPN, porque é
gráfico e não tem onde pedir a senha do `sudo`.

```bash
chmod +x FortiClient-VPN install-linux.sh
./install-linux.sh
```

Depois abra **FortiClient VPN** pelo menu, ou direto do terminal:

```bash
./FortiClient-VPN
```

Para instalar em `/usr/local` (em vez de `~/.local`, valendo para todos os
usuários):

```bash
sudo ./install-linux.sh
```

**Requisitos:** Debian ou Ubuntu (usa `apt-get`). Em outras distribuições,
instale `strongswan` e `strongswan-swanctl` pelo seu gerenciador e copie as
regras de `/etc/sudoers.d/` descritas dentro do próprio `install-linux.sh`.

## Windows

Basta executar o `FortiClient-VPN.exe`. O motor strongSwan vem embutido e é
extraído na primeira execução, então não há instalador nem pasta adicional.

Na primeira conexão o Windows pode exibir **"Windows protegeu o seu PC"**.
Clique em **Mais informações → Executar assim mesmo**. O executável não é
assinado digitalmente — ver [Assinatura de código](#assinatura-de-código).

## Como usar

1. Preencha **Gateway** (IP do FortiGate), **Chave PSK**, **Usuário** e **Senha**.
2. Clique em **▶ CONECTAR VPN**.
3. **Opções Avançadas** tem o IP local (detectado automaticamente) e a
   estratégia de IP virtual.

As credenciais ficam guardadas apenas no seu computador (DPAPI no Windows,
arquivo com `0600` no Linux) e não são enviadas a nenhum lugar além do seu
gateway.

### Comandos de linha

Útil para diagnóstico, já que na interface as falhas não aparecem em terminal:

```bash
--diagnose     # gera um .zip com tudo que é preciso para investigar
--connect      # conecta com as credenciais salvas
--disconnect
--cleanup      # remove resíduos de versões antigas
```

No Windows, `FortiClient-VPN.exe --diagnose`. No Linux, `./FortiClient-VPN --diagnose`.

### Onde está o log

| Sistema | Arquivo |
| --- | --- |
| Linux | `~/.local/state/forticlient-vpn/logs/app.log` |
| Windows | `%LOCALAPPDATA%\FortiClientVPN\logs\app.log` |
| Windows (motor) | `C:\ProgramData\FortiClientVPN\charon.log` |
| Linux (motor) | `journalctl -u strongswan -n 200 --no-pager` |

Sempre que possível, anexe o `.zip` gerado por **Exportar diagnóstico**.

## Diagnóstico de problemas

| Sintoma | Causa provável / o que fazer |
| --- | --- |
| "Motor strongSwan não encontrado" | Linux: rode o `install-linux.sh`. Windows: execute o `.exe` do release, não uma cópia movida de lugar. |
| Fica em "Conectando..." sem resposta | Gateway vazio, ou ainda o IP de exemplo `198.51.100.100` (faixa de documentação: ninguém responde). Confira o campo **Gateway**. |
| "Falha de autenticação" | Usuário, senha ou **PSK** incorretos. |
| "Tempo esgotado" | Gateway inacessível, ou portas UDP 500/4500 bloqueadas. |
| "Conflito de portas IKE (`IKEEXT`)" | O app tenta parar sozinho; se persistir, `sc stop IKEEXT` no Windows. |
| "CHILD_SA config 'forticlient' not found" | O `swanctl` não achou a configuração — veja o log do motor. |
| "A configuração não foi carregada no motor" | O `--load-all` respondeu sem carregar nada. Veja o log do motor. |
| Só conecta no PC onde foi configurado | O IP local salvo é de outra máquina. Limpe o campo **IP local** — o app volta a detectar. |
| Status em "DESCONECTADO" mesmo conectado | Envie o `--diagnose` e olhe o `swanctl --list-sas`. |

### Limitações conhecidas no Windows

- **IP virtual:** o strongSwan no Windows não instala IP de cliente sozinho,
  então o aplicativo tenta em cascata (interface padrão → demais interfaces →
  seguir sem). Nada precisa ser decidido por você; o resultado sai no log.
- **Serviço `IKEEXT`:** ocupa as portas UDP 500/4500 e é interrompido durante o
  uso. É restaurado quando você fecha o aplicativo.
- **SmartScreen:** sem assinatura, o Windows avisa. É esperado.

## Assinatura de código

Sem certificado, o Windows exibe "O Windows protegeu o seu PC" e é preciso
clicar em **Mais informações → Executar assim mesmo**. Isso é esperado: **a
assinatura não sai de um script — ela vem de um certificado emitido por uma
autoridade em que o Windows confia.**

Para eliminar o aviso é preciso um **certificado de assinatura de código**
(EKU `1.3.6.1.5.5.7.3.3`):

- **CA interna da DTIC** — gratuita, e o resultado é um executável sem aviso
  nas máquinas do domínio, desde que a raiz seja publicada por GPO. É a via
  indicada para uso interno no governo.
- **CA pública** (DigiCert, Sectigo, GlobalSign, SSL.com, ou ICP-Brasil) —
  funciona fora do domínio, custa centenas de reais por ano e exige
  documentação de pessoa jurídica.
- **SignPath Foundation** — gratuita para projetos open source elegíveis
  (GPLv3 + repositório público), sujeita a aprovação.

Mesmo com certificado novo, o SmartScreen pode avisar por um tempo: a
reputação se constrói com volume de downloads.

## Licença

**GNU GPLv3 ou superior** — ver [`LICENSE`](LICENSE).
Copyright (C) 2026 Jeiel Miranda.

O executável do Windows distribui o motor **strongSwan** como programa
separado, sob **GPLv2**. Cada release publica o tarball do fonte
correspondente (`strongswan-<versão>.tar.bz2`) para cumprir a GPLv2. Ver
[`NOTICE`](NOTICE) e [`SOURCE-OFFER.txt`](SOURCE-OFFER.txt).

O **Linux** usa o strongSwan do sistema, cuja GPLv2 já é satisfeita pela
distribuição do próprio sistema operacional.
