# Binários do motor VPN para Windows

Este diretório guarda o motor strongSwan compilado para Windows. Ele é o que
permite **IKEv2 + PSK + EAP-MSCHAPv2** sem depender do FortiClient — combinação
que o cliente IKEv2 nativo do Windows não oferece.

Os binários **não são versionados** (ver `.gitignore`); são gerados por:

```bash
sudo apt install build-essential mingw-w64 curl bzip2 perl make
./build/build_strongswan_windows.sh
```

## Conteúdo esperado

| Arquivo             | Papel                                                              |
| ------------------- | ------------------------------------------------------------------ |
| `charon-svc.exe`    | Serviço IKE (equivalente ao `charon` no Linux).                     |
| `swanctl.exe`       | Cliente de configuração/controle via VICI — mesmo uso do Linux.     |
| `strongswan.conf`   | Log em arquivo e carga automática da configuração do `swanctl`.     |
| `libcrypto*.dll` / `libssl*.dll` | Só existem se o OpenSSL não for linkado estaticamente. |

## Onde o aplicativo procura

`vpn_engine.windows_engine_dir()` procura, nesta ordem:

1. a variável de ambiente `FCT_VPN_ENGINE_DIR`;
2. `<pasta do executável>/vendor/windows` (layout instalado);
3. `<pasta do executável>/vendor` e a própria pasta do executável.

## Licença

O strongSwan é distribuído sob **GPLv2**. Ao redistribuir o instalador com estes
binários, a obrigação de disponibilizar o código-fonte correspondente se aplica
(ver `NOTICE`).
