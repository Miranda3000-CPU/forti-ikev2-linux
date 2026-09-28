#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FortiClient VPN Manager - motor VPN multiplataforma (strongSwan / swanctl).

O mesmo motor e a mesma configuração (`swanctl.conf`) são usados no Linux e no
Windows. No Linux opera sobre o strongSwan do sistema via `sudo swanctl`; no
Windows opera sobre os binários vendorizados em `vendor/windows/`
(`charon-svc.exe` + `swanctl.exe`).

Módulo sem dependência de Tkinter: toda a E/S de processo passa por um `runner`
injetável, o que permite testar sem rede e sem privilégios.
"""

from __future__ import annotations

import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from collections import namedtuple

from vpn_config import config_dir, ensure_dir, get_logger

IS_WINDOWS = sys.platform == "win32"
IS_LINUX = sys.platform.startswith("linux")

CHILD_NAME = "forticlient"
CONN_NAME = "forticlient"
LINUX_CONF_FILE = "/etc/swanctl/conf.d/forti.conf"

WIN_SERVICE_NAME = "strongSwan IKE service"
WIN_ENGINE_DIR_ENV = "FCT_VPN_ENGINE_DIR"
IKEEXT_SERVICE = "IKEEXT"

# Portas usadas pelo IKE; o socket-win as exige exclusivas.
IKE_PORTS = (500, 4500)

Status = namedtuple("Status", "connected vip detail error")

# Propostas idênticas às validadas com o FortiGate no Linux.
IKE_PROPOSALS = (
    "aes256-sha256-modp8192, aes256-sha256-modp4096, aes128-sha256-modp4096, "
    "aes256-sha256-modp2048, aes256-sha1-modp2048, aes128-sha256-modp2048"
)
ESP_PROPOSALS = (
    "aes256-sha256-modp8192, aes256-sha1-modp8192, aes128-sha256-modp8192, "
    "aes256-sha256, aes128-sha256"
)


# ═══════════════════════════════════════════════════════════════ configuração

def _escape(value):
    """Escapa um valor para uso dentro de string aspeada do swanctl.conf."""
    return str(value or "").replace("\\", "\\\\").replace('"', '\\"')


def build_swanctl_conf(gw, local_ip="", user="", pwd="", psk="", include_local_addrs=True):
    """Gera o swanctl.conf (IKEv2 + PSK no remote + EAP-MSCHAPv2 no local)."""
    local_line = ""
    if include_local_addrs and local_ip:
        local_line = "        local_addrs  = %s\n" % local_ip

    return (
        "connections {\n"
        "    %(conn)s {\n"
        "        version  = 2\n"
        "        remote_addrs = %(gw)s\n"
        "%(local_line)s"
        "        proposals    = %(ike)s\n"
        "        encap        = yes\n"
        "        mobike       = no\n"
        "        dpd_delay    = 5s\n"
        # 3 = padrao do strongSwan. Com 0 (infinito) uma falha de IKE_AUTH
        # nunca encerra a SA: ela retransmite para sempre e o --initiate só
        # volta no timeout do app (90s), sem nunca expor o notify do motivo.
        "        keyingtries  = 3\n"
        "        rekey_time   = 86400s\n"
        "\n"
        "        vips = 0.0.0.0\n"
        "\n"
        "        local {\n"
        "            auth     = eap-mschapv2\n"
        "            id       = %(user)s\n"
        "            eap_id   = %(user)s\n"
        "        }\n"
        "\n"
        "        remote {\n"
        "            auth = psk\n"
        "            id   = %%any\n"
        "        }\n"
        "\n"
        "        children {\n"
        "            %(conn)s {\n"
        "                remote_ts     = 0.0.0.0/0\n"
        "                local_ts      = dynamic\n"
        "                esp_proposals = %(esp)s\n"
        "                dpd_action    = restart\n"
        "                mode          = tunnel\n"
        "                rekey_time    = 43200s\n"
        "            }\n"
        "        }\n"
        "    }\n"
        "}\n"
        "\n"
        "secrets {\n"
        "    ike-%(conn)s {\n"
        '        secret = "%(psk)s"\n'
        "    }\n"
        "    eap-%(conn)s {\n"
        "        id     = %(user)s\n"
        '        secret = "%(pwd)s"\n'
        "    }\n"
        "}\n"
    ) % {
        "conn": CHILD_NAME,
        "gw": gw,
        "local_line": local_line,
        "ike": IKE_PROPOSALS,
        "esp": ESP_PROPOSALS,
        "user": user,
        "psk": _escape(psk),
        "pwd": _escape(pwd),
    }


def build_strongswan_conf(log_name="charonlog", log_path=None):
    """
    strongswan.conf usado pelo `charon-svc` (serviço) e pelo `swanctl.exe`.

    Log em arquivo: o serviço não tem console.

    `path` é obrigatório. Um bloco `filelog` sem ele não escreve nada — o
    daemon não tem para onde enviar, e o log some. Foi exatamente o que
    aconteceu em campo: 163 KB de app.log e zero linha de erro, porque o
    único lugar com o motivo da falha (AUTHENTICATION_FAILED,
    NO_PROPOSAL_CHOSEN, ID_MISMATCH) é o log do charon.

    Sem `start-scripts`: o serviço roda como SYSTEM na pasta do motor e não
    enxerga o nosso diretório de configuração. Quem carrega conexões/segredos é
    o próprio aplicativo, chamando `swanctl --load-all`.

    Atenção: o nome do alvo do `filelog` não pode conter ponto nem aspas — o
    parser do strongSwan rejeita as duas formas ("syntax error").
    """
    log_target = (log_name or "charonlog").replace("\\", "/").replace('"', "").replace(".", "_")
    # Barras normais: o parser do strongSwan não processa escape, e o Windows
    # aceita "/" em qualquer caminho.
    target = (log_path or "").replace("\\", "/").replace('"', "")
    path_line = "      path = %s\n" % target if target else ""
    # Sem comentário neste arquivo: ele é reescrito a cada conexão e só o
    # daemon vai lê-lo. A justificativa de cada campo fica no docstring.
    return (
        "charon-svc {\n"
        "  loglevel = 2\n"
        "  filelog {\n"
        "    %(log_target)s {\n"
        "%(path_line)s"
        "      flush_line = yes\n"
        "      ike_name = yes\n"
        "    }\n"
        "  }\n"
        "}\n"
    ) % {"log_target": log_target, "path_line": path_line}


# ═══════════════════════════════════════════════════════════ parsing/erros

_SECRET_LINE = re.compile(r"^(\s*secret\s*=\s*).*$", re.IGNORECASE | re.MULTILINE)


def redact_conf_text(text):
    """Remove senha/PSK de um swanctl.conf antes de anexá-lo ao diagnóstico."""
    if not text:
        return text or ""
    return _SECRET_LINE.sub(r'\1"***REDACTED***"', text)

_BRACKETED_IPV4 = re.compile(r"\[(\d{1,3}(?:\.\d{1,3}){3})\]")


def parse_list_sas(output):
    """
    Interpreta `swanctl --list-sas`.

    Retorna (conectado, vip, detalhe). Só considera conectado quando existe
    um IKE_SA ESTABLISHED pertencente ao nosso perfil.
    """
    text = output or ""
    if "ESTABLISHED" not in text.upper():
        return False, None, "nenhum IKE_SA estabelecido"
    if CONN_NAME not in text and CHILD_NAME not in text:
        return False, None, "IKE_SA estabelecida pertence a outro perfil"

    vip = None
    for match in _BRACKETED_IPV4.finditer(text):
        vip = match.group(1)
        break
    detail = "IKE_SA estabelecida"
    if vip:
        detail += " (VIP %s)" % vip
    return True, vip or "Ativo", detail


def map_engine_error(output):
    """Traduz a saída do motor em mensagem acionável para o usuário."""
    raw = output or ""
    lower = raw.lower()

    if "wfp mm failure" in lower or "ikeext" in lower:
        return (
            "Conflito de portas IKE no Windows: o servico 'IKEEXT' (IKE and AuthIP IPsec "
            "Keying Modules) esta usando as portas UDP 500/4500. Pare e desabilite o "
            "servico IKEEXT e tente novamente."
        )
    if "authentication_failure" in lower or "authentication failed" in lower or "eap_mschapv2 method failed" in lower or "auth_failed" in lower:
        return "Falha de autenticacao: verifique usuario e senha (sem caracteres extras como #)."
    if "no_proposal_chosen" in lower:
        return "O FortiGate respondeu NO_PROPOSAL_CHOSEN (propostas criptograficas incompativeis)."
    if "retransmit" in lower or "timed out" in lower or "timeout" in lower:
        return "Tempo esgotado: sem resposta do Gateway nas portas UDP 500/4500 (rede/firewall)."
    if "psk" in lower and ("missing" in lower or "no secret" in lower or "found no" in lower):
        return "PSK ausente ou nao carregada no motor (verifique a Chave PSK)."
    if "vip" in lower and ("not supported" in lower or "failed to install" in lower):
        return (
            "O motor nao conseguiu instalar o IP virtual devolvido pelo FortiGate. "
            "Tente a estrategia de VIP 'loopback' nas opcoes avancadas."
        )
    if "permission denied" in lower or "access is denied" in lower or "elevacao" in lower:
        return "Permissao negada: o Windows exigiu elevacao e ela nao foi concedida."

    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    lines = [line for line in lines if not line.startswith("[NET]") and not line.startswith("[ENC]")]
    if lines:
        return "Falha na conexao: " + " | ".join(lines[-3:])[:200]
    return "Falha na conexao (sem detalhes do motor)."


# ═══════════════════════════════════════════════════════════ descoberta

def _base_dirs():
    dirs = []
    if getattr(sys, "frozen", False):
        dirs.append(os.path.dirname(os.path.abspath(sys.executable)))
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        dirs.append(meipass)
    dirs.append(os.path.dirname(os.path.abspath(__file__)))
    if IS_LINUX:
        dirs.append("/usr/share/forticlient-vpn")
    seen, unique = set(), []
    for path in dirs:
        if path and path not in seen:
            seen.add(path)
            unique.append(path)
    return unique


def windows_engine_dir():
    """Localiza o diretório com charon-svc.exe/swanctl.exe (vendor/windows)."""
    override = os.environ.get(WIN_ENGINE_DIR_ENV)
    candidates = []
    if override:
        candidates.append(override)
    for base in _base_dirs():
        candidates.extend(
            [
                os.path.join(base, "vendor", "windows"),
                os.path.join(base, "vendor"),
                base,
            ]
        )
    for candidate in candidates:
        if all(os.path.isfile(os.path.join(candidate, exe)) for exe in ("charon-svc.exe", "swanctl.exe")):
            return candidate
    return None


def _current_platform():
    if IS_WINDOWS:
        return "windows"
    if IS_LINUX:
        return "linux"
    return "unknown"


def swanctl_path(platform=None):
    """
    Caminho do `swanctl` para a plataforma informada.

    Recebe a plataforma explicitamente (em vez de olhar só para sys.platform)
    para que a seleção seja testável e acompanhe o `platform` do VpnEngine.
    """
    platform = platform or _current_platform()
    if platform == "windows":
        engine = windows_engine_dir()
        if engine:
            return os.path.join(engine, "swanctl.exe")
        return shutil.which("swanctl.exe")
    return shutil.which("swanctl") or "/usr/sbin/swanctl"


def charon_svc_path():
    engine = windows_engine_dir()
    if engine:
        return os.path.join(engine, "charon-svc.exe")
    return None


def windows_swanctl_dir():
    """
    Diretório-base de configuração do swanctl no Windows (gravável sem admin).

    Layout exigido pelo swanctl (verificado na prática, strongSwan 6.1.0):
        <dir>/strongswan.conf       -> o swanctl ABORTA se não encontrar
        <dir>/conf.d/*.conf         -> conexões e segredos

    Por quê: o swanctl faz
        file        = <swanctl_dir>/strongswan.conf   (aborta se não achar)
        swanctl_dir = dirname(file)
    e depois procura `conf.d` DENTRO de `swanctl_dir`. Ou seja, `conf.d` é irmão
    direto do `strongswan.conf` que ele encontrou — não uma subpasta extra.
    Apontar o SWANCTL_DIR/cwd para cá satisfaz as duas formas de resolução.
    """
    return config_dir()


def windows_engine_workdir():
    """cwd para executar o swanctl.exe: o mesmo diretório-base."""
    return windows_swanctl_dir()


def windows_conf_dir():
    """Alias do diretório-base do swanctl (compatibilidade)."""
    return windows_swanctl_dir()


def windows_swanctl_conf_file():
    """
    `<dir>/swanctl.conf` — o arquivo que o swanctl realmente lê (SWANCTL_CONF).

    Descoberta em campo: o swanctl NÃO lê `strongswan.conf` (esse é o da
    biblioteca/daemon). As conexões e segredos vêm do `swanctl.conf`:

        load_conns/load_creds/load_authorities/load_pools
            -> load_swanctl_conf()  ->  <swanctl_dir>/swanctl.conf
            -> create_section_enumerator(cfg, "connections"/"secrets")

    No Linux `/etc/swanctl/swanctl.conf` tem uma única linha ativa,
    `include conf.d/*.conf`. Aqui gravamos o conteúdo COMPLETO direto neste
    arquivo: dispensa o `include` e a resolução de `conf.d`.

    Sem ele o swanctl carrega ZERO conexões e ainda retorna rc=0, falhando só
    depois com "CHILD_SA config 'forticlient' not found".
    """
    return os.path.join(windows_swanctl_dir(), "swanctl.conf")


def windows_strongswan_conf_file():
    return os.path.join(windows_swanctl_dir(), "strongswan.conf")


# ─────────────────────────────────────────────── log do daemon (charon)

def windows_charon_log_dir():
    """
    Diretório machine-wide do log do charon.

    Fica em ProgramData (e não na pasta do motor) por dois motivos: o
    charon-svc roda como SYSTEM, que não enxerga o perfil do usuário, e o
    aplicativo precisa LER esse arquivo para anexá-lo ao diagnóstico — em
    Program Files o usuário só tem leitura, o que também serviria, mas ali o
    log se mistura com os binários e o desinstalador teria de limpá-lo.
    """
    base = os.environ.get("ProgramData") or "C:\\ProgramData"
    return os.path.join(base, "FortiClientVPN")


def windows_charon_log_file():
    return os.path.join(windows_charon_log_dir(), "charon.log")


def windows_engine_strongswan_conf_file():
    """
    O strongswan.conf que o DAEMON lê: o que está ao lado do charon-svc.exe.

    Diferente do arquivo do usuário (windows_strongswan_conf_file), que serve
    ao swanctl. O serviço é criado sem argumentos, então o strongSwan resolve a
    configuração a partir do diretório do executável — e só a lê no arranque.
    Sem reescrever este arquivo, mexer no do usuário não muda o log do daemon.
    """
    charon = charon_svc_path()
    if not charon:
        return None
    return os.path.join(os.path.dirname(charon), "strongswan.conf")


# ═══════════════════════════════════════════════════════════ runner

class Result:
    """Resultado mínimo de processo, compatível com subprocess.CompletedProcess."""

    def __init__(self, returncode=0, stdout="", stderr="", command=None, elevated=False, ok=None):
        self.returncode = returncode
        self.stdout = stdout or ""
        self.stderr = stderr or ""
        self.command = command or []
        self.elevated = elevated
        self._ok_override = ok

    @property
    def ok(self):
        return self.returncode == 0 if self._ok_override is None else bool(self._ok_override)

    @property
    def output(self):
        return (self.stdout + self.stderr).strip()

    def __repr__(self):  # pragma: no cover - auxiliar de debug
        return "Result(rc=%r, elevated=%r, out=%r)" % (self.returncode, self.elevated, self.output[:120])


def _read_log_tail(path, lines=200, max_bytes=512_000):
    """
    Últimas `lines` linhas de um log, para anexar ao pacote de diagnóstico.

    Lê no máximo `max_bytes` do FIM do arquivo: o charon.log cresce sem
    rotação e o pacote não pode virar um disco. A linha em que o corte cai é
    descartada, senão ela aparece truncada e confunde quem lê.
    """
    if not path or not os.path.isfile(path):
        return "(log inexistente: %s)" % (path or "caminho vazio")
    try:
        size = os.path.getsize(path)
        with open(path, "rb") as handle:
            if size > max_bytes:
                handle.seek(size - max_bytes)
                handle.readline()
            raw = handle.read()
    except OSError as exc:
        return "(nao foi possivel ler: %s)" % exc

    text = raw.decode("utf-8", errors="replace")
    todas = text.splitlines()
    if not todas:
        return "(vazio)"
    if len(todas) <= lines:
        return "\n".join(todas)
    return "(... %d linhas anteriores omitidas ...)\n%s" % (
        len(todas) - lines,
        "\n".join(todas[-lines:]),
    )


def _ps_quote(value):
    return "'" + str(value).replace("'", "''") + "'"


def _write_elevated(path, text):
    """
    Grava `text` em `path`; se não houver permissão, tenta com UAC.

    O conteúdo vai por um arquivo temporário porque o comando elevado precisa
    de um argumento só — passar o texto multilinha inline exigiria escaping e
    qualquer aspas quebraria a gravação.

    Devolve True só se o arquivo estiver no disco com o conteúdo desejado.
    """
    try:
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        return True
    except OSError:
        pass

    if not IS_WINDOWS:
        return False

    staged = tempfile.NamedTemporaryFile(
        "w", suffix=".conf", delete=False, encoding="utf-8", errors="replace"
    )
    try:
        staged.write(text)
        staged.close()
        result = default_runner(
            [
                "powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command",
                "$ErrorActionPreference='Stop'; "
                "Copy-Item -LiteralPath %s -Destination %s -Force"
                % (_ps_quote(staged.name), _ps_quote(path)),
            ],
            timeout=90,
            elevate=True,
        )
        return result.ok
    except OSError:
        return False
    finally:
        try:
            os.unlink(staged.name)
        except OSError:
            pass


def _run_elevated_windows(argv, timeout=None):
    """
    Executa um comando com elevação (UAC) no Windows e aguarda o término.

    Sempre passa por `Start-Process -Verb RunAs -Wait -PassThru`, de modo que o
    usuário veja o texto do comando antes de aprovar.
    """
    if not argv:
        return Result(2, "", "comando vazio", elevated=True)
    file_path = _ps_quote(argv[0])
    if len(argv) > 1:
        arg_list = "-ArgumentList @(" + ",".join(_ps_quote(a) for a in argv[1:]) + ")"
    else:
        arg_list = ""
    script = (
        "$ErrorActionPreference='Stop'; "
        "$p = Start-Process -FilePath %s %s -Verb RunAs -Wait -PassThru; "
        "exit $p.ExitCode" % (file_path, arg_list)
    )
    creationflags = 0x08000000
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
            capture_output=True,
            text=True,
            errors="replace",
            timeout=timeout or 120,
            creationflags=creationflags,
        )
        return Result(proc.returncode, proc.stdout or "", proc.stderr or "", command=argv, elevated=True)
    except FileNotFoundError as exc:
        return Result(127, "", "powershell nao encontrado: %s" % exc, command=argv, elevated=True)
    except subprocess.TimeoutExpired:
        return Result(124, "", "timeout aguardando elevacao", command=argv, elevated=True)


def _kill_tree(proc):
    """Mata o processo (e o grupo, no POSIX) sem depender de SIGTERM."""
    try:
        if IS_LINUX:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            return
    except Exception:
        pass
    try:
        proc.kill()
    except Exception:
        pass


def default_runner(argv, input_text=None, timeout=None, env=None, elevate=False, cwd=None):
    """
    Runner real. `elevate=True` só tem efeito no Windows.

    Usa Popen com grupo próprio e SIGKILL no timeout: o `swanctl` pode ficar
    preso no socket VICI e `subprocess.run(timeout=...)` sozinho bloqueia depois
    do prazo esperando os pipes fecharem.
    """
    if elevate and IS_WINDOWS:
        return _run_elevated_windows(argv, timeout=timeout)

    creationflags = 0x08000000 if IS_WINDOWS else 0
    popen_kwargs = {
        "stdin": subprocess.PIPE if input_text is not None else subprocess.DEVNULL,
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "text": True,
        "errors": "replace",
        "env": env,
        "creationflags": creationflags,
    }
    if cwd:
        # No Windows o swanctl.exe procura strongswan.conf no diretório atual.
        popen_kwargs["cwd"] = cwd
    if IS_LINUX:
        popen_kwargs["start_new_session"] = True

    try:
        proc = subprocess.Popen(argv, **popen_kwargs)
    except FileNotFoundError as exc:
        return Result(127, "", str(exc), command=argv)
    except OSError as exc:
        return Result(1, "", str(exc), command=argv)

    try:
        out, err = proc.communicate(input=input_text, timeout=timeout)
        return Result(proc.returncode, out, err, command=argv)
    except subprocess.TimeoutExpired:
        _kill_tree(proc)
        try:
            out, err = proc.communicate(timeout=5)
        except Exception:
            out, err = "", ""
        return Result(124, out or "", ((err or "") + "\ntimeout apos %ss" % timeout).strip(), command=argv)


# ═══════════════════════════════════════════════════════════ motor

class VpnEngine:
    """Operações de conexão/desconexão/status por plataforma."""

    def __init__(self, platform=None, runner=None, logger=None):
        self.platform = platform or ("windows" if IS_WINDOWS else ("linux" if IS_LINUX else "unknown"))
        self.runner = runner or default_runner
        self.logger = logger or get_logger()
        self._vip_strategy_used = None

    # ---------------------------------------------------------- utilidades
    def _log(self, message):
        try:
            self.logger.info(message)
        except Exception:
            pass

    def _call(self, argv, **kwargs):
        kwargs.setdefault("timeout", 60)
        result = self.runner(argv, **kwargs)
        if not isinstance(result, Result):
            result = Result(
                getattr(result, "returncode", 0),
                getattr(result, "stdout", "") or "",
                getattr(result, "stderr", "") or "",
                command=argv,
                elevated=kwargs.get("elevate", False),
            )
        if result.elevated:
            self._log("(elevado) %s -> rc=%s" % (" ".join(argv), result.returncode))
        else:
            self._log("%s -> rc=%s" % (" ".join(argv), result.returncode))
        # A saída do motor é a única pista real quando algo falha em silêncio
        # (ex.: --load-all com rc=0 sem carregar conexão nenhuma).
        output = result.output
        if output:
            for line in output.splitlines():
                if line.strip():
                    self._log("    | %s" % line.strip()[:300])
        return result

    def availability(self):
        """Retorna (disponivel, caminho_ou_mensagem)."""
        if self.platform == "linux":
            path = shutil.which("swanctl")
            if path:
                return True, path
            return False, "swanctl nao encontrado no PATH (instale o pacote strongswan-swanctl)."
        if self.platform == "windows":
            engine = windows_engine_dir()
            if engine:
                return True, engine
            return False, (
                "Motor strongSwan para Windows nao encontrado (vendor/windows/charon-svc.exe). "
                "Reinstale o pacote do FortiClient VPN."
            )
        return False, "plataforma nao suportada: %s" % self.platform

    # ------------------------------------------------------------- status
    def status(self):
        if self.platform == "linux":
            return self._status_linux()
        if self.platform == "windows":
            return self._status_windows()
        return Status(False, None, "", "plataforma nao suportada")

    def _parse_status(self, output):
        connected, vip, detail = parse_list_sas(output)
        if connected:
            return Status(True, vip, detail, "")
        return Status(False, None, detail, "")

    def _status_linux(self):
        result = self._call(["sudo", "swanctl", "--list-sas"], timeout=15)
        return self._parse_status(result.output)

    def _status_windows(self):
        swanctl = swanctl_path(self.platform)
        if not swanctl:
            return Status(False, None, "", "swanctl.exe nao encontrado")
        result = self._call([swanctl, "--list-sas"], timeout=15, env=self._win_env(), cwd=self._win_workdir())
        return self._parse_status(result.output)

    def _win_workdir(self):
        """cwd do swanctl.exe: o diretório que contém swanctl.conf/strongswan.conf."""
        return windows_swanctl_dir()

    def _win_env(self):
        env = dict(os.environ)
        env["SWANCTL_DIR"] = windows_swanctl_dir()
        return env

    # ------------------------------------------------------------ conectar
    def connect(self, settings):
        if self.platform == "windows":
            return self._connect_windows(settings)
        if self.platform == "linux":
            return self._connect_linux(settings)
        return Status(False, None, "", "plataforma nao suportada")

    def _connect_linux(self, settings):
        conf = build_swanctl_conf(
            gw=settings.get("gateway", "").strip(),
            local_ip=settings.get("local_ip", "").strip(),
            user=settings.get("user", "").strip(),
            pwd=settings.get("password", "").strip(),
            psk=settings.get("psk", "").strip(),
        )
        self._call(["sudo", "mkdir", "-p", "/etc/swanctl/conf.d"], timeout=20)
        self._call(["sudo", "tee", LINUX_CONF_FILE], input_text=conf, timeout=20)
        self._call(["sudo", "chmod", "600", LINUX_CONF_FILE], timeout=20)
        self._call(["sudo", "swanctl", "--load-all"], timeout=40)
        self._call(["sudo", "ip", "rule", "add", "lookup", "220", "pref", "220"], timeout=15)

        if not os.path.exists("/var/run/charon.ctl"):
            self._log("Socket /var/run/charon.ctl ausente: iniciando o servico strongSwan.")
            started = self._call(["sudo", "systemctl", "start", "strongswan-starter.service"], timeout=40)
            if started.returncode != 0:
                self._call(["sudo", "systemctl", "start", "strongswan.service"], timeout=40)
            time.sleep(1)

        proc = self._call(["sudo", "swanctl", "--initiate", "--child", CHILD_NAME], timeout=90)
        output = proc.output
        lines = [line for line in output.splitlines() if "agent plugin" not in line and "plugin 'agent'" not in line]
        clean = "\n".join(lines)

        status = self.status()
        if proc.returncode == 0 and status.connected:
            return Status(True, status.vip, "conectado", "")
        return Status(False, None, clean, map_engine_error(clean))

    def _connect_windows(self, settings):
        available, detail = self.availability()
        if not available:
            return Status(False, None, "", detail)

        problems = []
        # A ordem importa: o strongswan.conf do daemon só é lido no arranque do
        # serviço, então ele precisa estar no disco ANTES de subirmos o serviço.
        # Sem este sync, um strongswan.conf sem `path` (instalação antiga) deixa
        # o daemon sem log nenhum.
        if self._sync_engine_strongswan_conf():
            problems.append("strongswan.conf do motor estava sem log e o servico foi reiniciado")
        if not self._ensure_windows_service():
            problems.append("servico charon-svc nao pode ser iniciado")
        if not self._ensure_ikext_stopped():
            problems.append(
                "servico IKEEXT ativo: ele usa as portas UDP 500/4500 e impede o motor de escutar"
            )

        conf = build_swanctl_conf(
            gw=settings.get("gateway", "").strip(),
            local_ip=settings.get("local_ip", "").strip(),
            user=settings.get("user", "").strip(),
            pwd=settings.get("password", "").strip(),
            psk=settings.get("psk", "").strip(),
        )

        # Três arquivos, papéis distintos:
        #   swanctl.conf     -> conexões + segredos (é ESTE que o swanctl lê)
        #   strongswan.conf  -> configuração da biblioteca/daemon (log)
        #   ambos no mesmo diretório, que é o cwd e o SWANCTL_DIR
        # O swanctl aborta se o strongswan.conf não existir, e só carrega
        # conexões que estejam no swanctl.conf.
        ensure_dir(windows_swanctl_dir())
        try:
            with open(windows_swanctl_conf_file(), "w", encoding="utf-8") as handle:
                handle.write(conf)
        except OSError as exc:
            return Status(False, None, "", "falha ao gravar swanctl.conf: %s" % exc)

        try:
            with open(windows_strongswan_conf_file(), "w", encoding="utf-8") as handle:
                handle.write(build_strongswan_conf(log_path=windows_charon_log_file()))
        except OSError as exc:
            return Status(False, None, "", "falha ao gravar strongswan.conf: %s" % exc)

        swanctl = swanctl_path(self.platform)
        self._log("Diretorio de configuracao do swanctl: %s" % windows_swanctl_dir())

        # Derruba SAs penduradas de tentativas anteriores ANTES de iniciar.
        # Com keyingtries finito elas se encerram sozinhas, mas uma tentativa
        # interrompida no meio (timeout do app, fechar a janela) deixa meia SA
        # viva: em campo foram observadas duas simultâneas, uma delas com o IP
        # local obsoleto. Elas somam retransmisses, competem pelas portas 500/4500
        # e fazem o --list-sas do diagnóstico ficar ambíguo.
        stale = self._call(
            [swanctl, "--terminate", "--ike", CHILD_NAME],
            timeout=30,
            env=self._win_env(),
            cwd=self._win_workdir(),
        )
        if stale.ok:
            self._log("Encerrada SA pendurada de tentativa anterior.")
        else:
            self._log("Nao ha SA pendurada a encerrar (%s)." % (stale.output or "sem resposta"))

        load = self._call(
            [swanctl, "--load-all"], timeout=60, env=self._win_env(), cwd=self._win_workdir()
        )

        # Guarda contra a falha silenciosa que já ocorreu em campo: --load-all
        # retornava rc=0 sem carregar nada e o erro só aparecia no --initiate
        # ("CHILD_SA config not found"), sem indicar o motivo.
        listed = self._call(
            [swanctl, "--list-conns"], timeout=60, env=self._win_env(), cwd=self._win_workdir()
        )
        if CHILD_NAME not in listed.output:
            return Status(
                False,
                None,
                (load.output + "\n" + listed.output).strip(),
                "A configuracao nao foi carregada no motor (conexao '%s' ausente). "
                "Diretorio esperado: %s" % (CHILD_NAME, windows_swanctl_dir()),
            )

        proc = self._call([swanctl, "--initiate", "--child", CHILD_NAME], timeout=90, env=self._win_env(), cwd=self._win_workdir())

        status = self.status()
        if proc.returncode == 0 and status.connected:
            applied = self._apply_vip(status.vip, settings.get("vip_strategy", "auto"))
            note = "conectado"
            if applied:
                note += " (%s)" % applied
            return Status(True, status.vip, note, "")
        error = map_engine_error(proc.output)
        if problems:
            error = error + " | " + "; ".join(problems)
        # Aponta o log do daemon. O stdout do swanctl nem sempre traz o notify
        # do servidor, e sem essa pista o usuário só tinha "timeout" para
        # investigate — o motivo real estava no charon.log, que ele não sabia
        # que existia.
        charon_log = windows_charon_log_file()
        if os.path.isfile(charon_log):
            error += " | Log do motor (motivo real): %s" % charon_log
        return Status(False, None, proc.output, error)


    # --------------------------------------------------------- desconectar
    def disconnect(self):
        if self.platform == "windows":
            return self._disconnect_windows()
        if self.platform == "linux":
            result = self._call(["sudo", "swanctl", "--terminate", "--ike", CHILD_NAME], timeout=45)
            if result.ok:
                return Status(False, None, "desconectado", "")
            return Status(False, None, result.output, map_engine_error(result.output))
        return Status(False, None, "", "plataforma nao suportada")

    def _disconnect_windows(self):
        swanctl = swanctl_path(self.platform)
        detail = ""
        if swanctl:
            result = self._call([swanctl, "--terminate", "--ike", CHILD_NAME], timeout=45, env=self._win_env(), cwd=self._win_workdir())
            detail = result.output
        self._remove_vip()
        return Status(False, None, "desconectado", "")

    # -------------------------------------------------- Windows: serviço
    def _sc_query(self, service):
        return self._call(["sc", "query", service], timeout=20)

    def _sync_engine_strongswan_conf(self):
        """
        Garante que o strongswan.conf do DAEMON tenha `path` no filelog.

        O charon-svc é registrado sem argumentos, então lê a configuração de
        onde está o executável — e apenas no arranque. Duas consequências:

        1. installations antigas têm ali o conf sem `path` (o log nunca foi
           escrito). Reescrevemos com o path correto.
        2.reescrever não basta: o serviço precisa reiniciar para reler.

        Devolve True se o arquivo mudou (ou seja, se o serviço deve reiniciar).
        """
        target = windows_engine_strongswan_conf_file()
        if not target:
            return False

        desired = build_strongswan_conf(log_path=windows_charon_log_file())
        try:
            with open(target, "r", encoding="utf-8", errors="replace") as handle:
                current = handle.read()
        except OSError:
            current = ""

        if current.strip() == desired.strip():
            return False

        self._log("strongswan.conf do motor sem log utilizavel; regravando com path.")
        if IS_WINDOWS:
            # Fora do Windows `windows_charon_log_dir()` resolve para um caminho
            # relativo sem sentido; criar isso sujaria o diretório de trabalho.
            ensure_dir(windows_charon_log_dir())
        if not _write_elevated(target, desired):
            # Sem permissão de escrita o daemon segue com a config antiga: ainda
            # funciona, mas continua sem log. Só um aviso, não um erro fatal.
            self._log("Nao foi possivel gravar %s (sem elevacao); o log do motor pode ficar indisponivel." % target)
            return False

        if "RUNNING" in self._sc_query(WIN_SERVICE_NAME).output.upper():
            self._log("Reiniciando '%s' para o motor reler a configuracao de log." % WIN_SERVICE_NAME)
            self._call(["sc", "stop", WIN_SERVICE_NAME], timeout=120, elevate=True)
            time.sleep(2)
        return True

    def _ensure_windows_service(self):
        query = self._sc_query(WIN_SERVICE_NAME)
        if query.ok and "RUNNING" in query.output.upper():
            return True
        charon = charon_svc_path()
        if not charon:
            self._log("charon-svc.exe nao encontrado.")
            return False

        if not query.ok:
            self._log("Instalando o servico '%s'." % WIN_SERVICE_NAME)
            self._call(
                [
                    "sc", "create", WIN_SERVICE_NAME,
                    "binPath=", charon,
                    "start=", "demand",
                    "DisplayName=", WIN_SERVICE_NAME,
                ],
                timeout=120,
                elevate=True,
            )
        started = self._call(["sc", "start", WIN_SERVICE_NAME], timeout=120, elevate=True)
        time.sleep(1)
        verify = self._sc_query(WIN_SERVICE_NAME)
        if verify.ok and "RUNNING" in verify.output.upper():
            return True

        # Autonomia: sem serviço, sobe o charon-svc.exe diretamente (elevado, em
        # segundo plano). Assim o usuário não precisa corrigir a instalação.
        self._log("Servico nao iniciou (%s); subindo charon-svc.exe diretamente." % (started.output or verify.output))
        return self._start_charon_background(charon)

    def _start_charon_background(self, charon):
        """Inicia o motor IKE elevado, sem console e sem bloquear, via UAC."""
        workdir = os.path.dirname(charon)
        script = (
            "$ErrorActionPreference='Stop'; "
            "Start-Process -FilePath %s -WorkingDirectory %s -Verb RunAs -WindowStyle Hidden; "
            "Start-Sleep -Seconds 2; exit 0" % (_ps_quote(charon), _ps_quote(workdir))
        )
        result = self._call(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
            timeout=90,
        )
        if not result.ok:
            self._log("Nao foi possivel subir charon-svc.exe: %s" % result.output)
        return result.ok

    # ------------------------------------------------ Windows: IKEEXT
    def _ensure_ikext_stopped(self):
        query = self._sc_query(IKEEXT_SERVICE)
        if not query.ok:
            # Serviço inexistente ou inacessível: não há conflito a resolver.
            return True
        if "RUNNING" not in query.output.upper():
            return True
        self._log("Parando '%s' (conflito nas portas UDP %s)." % (IKEEXT_SERVICE, IKE_PORTS))
        stopped = self._call(["sc", "stop", IKEEXT_SERVICE], timeout=120, elevate=True)
        time.sleep(1)
        verify = self._sc_query(IKEEXT_SERVICE)
        if verify.ok and "RUNNING" not in verify.output.upper():
            return True

        # Segunda tentativa por outro caminho, para não depender do serviço `sc`.
        self._call(["net", "stop", IKEEXT_SERVICE], timeout=120, elevate=True)
        time.sleep(1)
        verify = self._sc_query(IKEEXT_SERVICE)
        if verify.ok and "RUNNING" not in verify.output.upper():
            return True
        self._log("Nao foi possivel parar '%s': %s" % (IKEEXT_SERVICE, stopped.output))
        return False

    def restore_ikext(self):
        """Restaura o estado original do IKEEXT (usado na desinstalação)."""
        result = self._call(["sc", "start", IKEEXT_SERVICE], timeout=120, elevate=True)
        return result.ok

    # --------------------------------------------------- Windows: VIP
    def _active_interface(self):
        """Descobre o nome da interface com a rota padrão (para instalar o VIP)."""
        result = self._call(["powershell", "-NoProfile", "-Command", "(Get-NetRoute -DestinationPrefix '0.0.0.0/0' | Sort-Object RouteMetric | Select-Object -First 1).InterfaceAlias"], timeout=30)
        name = (result.stdout or "").strip().splitlines()
        return name[0].strip() if name else ""

    def _up_interfaces(self):
        """Todas as interfaces IPv4 ativas — candidatas a receber o VIP."""
        result = self._call(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "(Get-NetAdapter | Where-Object {$_.Status -eq 'Up'}).Name",
            ],
            timeout=30,
        )
        names = [line.strip() for line in (result.stdout or "").splitlines() if line.strip()]
        active = self._active_interface()
        if active:
            names = [active] + [n for n in names if n != active]
        return names

    def _add_address(self, interface, vip):
        self._call(
            ["netsh", "interface", "ipv4", "add", "address", interface, vip, "255.255.255.255"],
            timeout=120,
            elevate=True,
        )
        verify = self._call(["netsh", "interface", "ipv4", "show", "addresses", interface], timeout=30)
        return vip in verify.output

    def _apply_vip(self, vip, strategy="auto"):
        """
        Instala o IP virtual devolvido pelo FortiGate, sem exigir decisão do usuário.

        O backend `kernel-iph` do strongSwan no Windows não instala VIPs de
        cliente, então a instalação é feita aqui em cascata:
          1. interface com a rota padrão;
          2. qualquer outra interface ativa;
          3. seguir sem VIP (o FortiGate pode aceitar o IP físico).

        Nunca falha a conexão: no pior caso apenas informa que seguiu sem VIP.
        """
        if not vip or vip in ("Ativo", None):
            return ""
        if strategy == "none":
            return "VIP %s nao instalado (estrategia none)" % vip

        for interface in self._up_interfaces():
            if self._add_address(interface, vip):
                self._vip_strategy_used = (vip, interface)
                return "VIP %s instalado em %s" % (vip, interface)

        self._log("VIP %s nao pode ser instalado em nenhuma interface; seguindo sem VIP." % vip)
        return "VIP %s nao instalado (seguindo sem VIP)" % vip

    def _remove_vip(self):
        used = self._vip_strategy_used
        if not used:
            return
        if isinstance(used, tuple):
            vip, interface = used
        else:  # compatibilidade com registros antigos
            vip, interface = used, self._active_interface()
        if interface:
            self._call(
                ["netsh", "interface", "ipv4", "delete", "address", interface, vip],
                timeout=120,
                elevate=True,
            )
        self._vip_strategy_used = None

    # -------------------------------------------------- limpeza de conflitos
    def cleanup_conflicts(self):
        """
        Remove resíduos deixados por versões anteriores do aplicativo.

        Versões antigas criavam um perfil RAS (`FortiClient-VPN`) e chaves de
        registro de túnel SSL-VPN apontando para "DTIC-VPN". Ambos conflitam
        com o motor atual e precisam sair.
        """
        removed = []
        if self.platform != "windows":
            return removed

        # 1. Perfil RAS criado por Add-VpnConnection em versões anteriores.
        ps_remove_profile = (
            "$ErrorActionPreference='SilentlyContinue'; "
            "Remove-VpnConnection -Name 'FortiClient-VPN' -Force -ErrorAction SilentlyContinue; "
            "$u = Get-VpnConnection -Name 'FortiClient-VPN' -ErrorAction SilentlyContinue; "
            "if ($u) { exit 3 } else { exit 0 }"
        )
        result = self._call(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_remove_profile],
            timeout=60,
        )
        if result.ok:
            removed.append("perfil RAS 'FortiClient-VPN'")

        # 2. Chaves de registro do túnel falso em Sslvpn\\Tunnels e FA_Tunnel.
        try:
            import winreg

            targets = [
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Fortinet\FortiClient\Sslvpn\Tunnels", "DTIC-VPN"),
                (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Fortinet\FortiClient\Sslvpn\Tunnels", "DTIC-VPN"),
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Fortinet\FortiClient\FA_Tunnel", None),
                (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Fortinet\FortiClient\FA_Tunnel", None),
            ]
            for root, path, subkey in targets:
                try:
                    if subkey:
                        winreg.DeleteKey(root, path + "\\" + subkey)
                        removed.append("%s\\%s" % (path, subkey))
                    else:
                        winreg.DeleteKey(root, path)
                        removed.append(path)
                except FileNotFoundError:
                    pass
                except OSError as exc:
                    self._log("Nao foi possivel remover %s: %s" % (path, exc))
        except Exception as exc:  # pragma: no cover - winreg ausente fora do Windows
            self._log("Limpeza de registro indisponivel: %s" % exc)

        return removed

    # ------------------------------------------------------- diagnóstico
    def diagnose(self):
        """Coleta saída de comandos relevantes para o pacote de diagnóstico."""
        info = {}
        available, detail = self.availability()
        info["motor_disponivel"] = "%s (%s)" % (available, detail)
        info["swanctl"] = swanctl_path(self.platform) or "-"

        if self.platform == "windows":
            for service in (WIN_SERVICE_NAME, IKEEXT_SERVICE):
                result = self._sc_query(service)
                info["sc query %s" % service] = result.output or "(sem resposta)"
            result = self._call(["ipconfig", "/all"], timeout=30)
            info["ipconfig /all"] = result.output
            info["dir configuracao swanctl"] = windows_conf_dir()

            # Estado real do motor: o que está carregado no daemon e o que existe
            # em disco. Sem isso, um --load-all com rc=0 engana.
            swanctl = swanctl_path(self.platform)
            if swanctl:
                for label, args in (
                    ("swanctl --list-conns", ["--list-conns"]),
                    ("swanctl --list-sas", ["--list-sas"]),
                ):
                    result = self._call(
                        [swanctl] + args, timeout=30, env=self._win_env(), cwd=self._win_workdir()
                    )
                    info[label] = result.output or "(sem resposta)"
                result = self._call(
                    [swanctl, "--version"], timeout=30, env=self._win_env(), cwd=self._win_workdir()
                )
                info["swanctl --version"] = result.output

            conf_dir = windows_conf_dir()
            listing = []
            for root, _dirs, files in os.walk(conf_dir):
                for name in files:
                    listing.append(os.path.join(root, name))
            info["arquivos de configuracao"] = "\n".join(listing) or "(nenhum)"
            info["log do charon (caminho)"] = windows_charon_log_file()
            info["log do charon (ultimas linhas)"] = _read_log_tail(windows_charon_log_file())
            for path in (windows_swanctl_conf_file(), windows_strongswan_conf_file()):
                try:
                    with open(path, "r", encoding="utf-8", errors="replace") as handle:
                        info["conteudo de %s" % os.path.basename(path)] = redact_conf_text(handle.read())
                except OSError as exc:
                    info["conteudo de %s" % os.path.basename(path)] = "nao foi possivel ler: %s" % exc
        else:
            # `swanctl` pode bloquear no socket VICI; timeout curto e SIGKILL.
            result = self._call(["swanctl", "--version"], timeout=10)
            info["swanctl --version"] = result.output
            result = self._call(["ip", "-brief", "address"], timeout=20)
            info["ip -brief address"] = result.output
        return info
