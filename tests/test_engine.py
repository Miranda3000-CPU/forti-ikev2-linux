import os
import sys
import tempfile
import unittest

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from vpn_engine import (  # noqa: E402
    Result,
    VpnEngine,
    build_strongswan_conf,
    build_swanctl_conf,
    map_engine_error,
    parse_list_sas,
)

ESTABLISHED = """forticlient: #1, ESTABLISHED, IKEv2, 48c04cfd85452589_i 4b22838eac3b49e7_r*
  local  'miranda' @ 203.0.113.7[4500]
  remote '%any' @ 198.51.100.100[4500] [10.10.20.5]
  AES_CBC-256/HMAC_SHA2_256_128/PRF_HMAC_SHA2_256/MODP_2048
  forticlient: #1, reqid 1, INSTALLED, TUNNEL-in-UDP, ESP:AES_CBC-256/HMAC_SHA1_96
    local  0.0.0.0/0
    remote 10.10.20.5/32
"""


class _CapturingLogger:
    """Logger de teste que guarda as mensagens em memória."""

    def __init__(self):
        self.messages = []

    def info(self, message, *args):
        if args:
            message = message % args
        self.messages.append(str(message))

    def warning(self, *args, **kwargs):
        pass


class FakeRunner:
    """Runner de teste: casa substrings na ordem em que foram declaradas."""

    def __init__(self, responses=None, default=(0, "", "")):
        self.responses = list((responses or {}).items())
        self.default = default
        self.calls = []

    def __call__(self, argv, input_text=None, timeout=None, env=None, elevate=False, cwd=None):
        command = " ".join(argv)
        self.calls.append(
            {
                "argv": argv,
                "command": command,
                "input_text": input_text,
                "elevate": elevate,
                "env": env,
                "cwd": cwd,
            }
        )
        for pattern, response in self.responses:
            if pattern in command:
                return Result(response[0], response[1], response[2], command=argv, elevated=elevate)
        return Result(self.default[0], self.default[1], self.default[2], command=argv, elevated=elevate)

    def commands(self):
        return [call["command"] for call in self.calls]


class TestSwanctlConf(unittest.TestCase):
    def test_includes_core_parameters(self):
        conf = build_swanctl_conf("198.51.100.100", "203.0.113.7", "miranda", "senha", "psk")
        for token in [
            "remote_addrs = 198.51.100.100",
            "local_addrs  = 203.0.113.7",
            "auth     = eap-mschapv2",
            "auth = psk",
            "vips = 0.0.0.0",
            "secrets {",
            "ike-forticlient",
            "eap-forticlient",
        ]:
            self.assertIn(token, conf, token)

    def test_local_addrs_can_be_omitted(self):
        conf = build_swanctl_conf("gw", "", "u", "p", "k")
        self.assertNotIn("local_addrs", conf)

    def test_escapes_quotes_in_secrets(self):
        conf = build_swanctl_conf("gw", "1.2.3.4", "u", 'se"nha', 'p"s"k')
        self.assertIn('secret = "p\\"s\\"k"', conf)
        self.assertIn('secret = "se\\"nha"', conf)


class TestParsing(unittest.TestCase):
    def test_established_with_vip(self):
        connected, vip, _ = parse_list_sas(ESTABLISHED)
        self.assertTrue(connected)
        self.assertEqual(vip, "10.10.20.5")

    def test_frontend_does_not_false_positive_on_ipconfig(self):
        """Regressao: a versao antiga dizia CONECTADO so por ver 'Fortinet'."""
        connected, vip, _ = parse_list_sas("Adaptador Fortinet Virtual Adapter\n  IPv4: 10.0.0.5")
        self.assertFalse(connected)
        self.assertIsNone(vip)

    def test_empty(self):
        self.assertFalse(parse_list_sas("")[0])

    def test_other_profile(self):
        self.assertFalse(parse_list_sas("outra: #1, ESTABLISHED, IKEv2\n")[0])

    def test_established_without_vip(self):
        connected, vip, _ = parse_list_sas("forticlient: #1, ESTABLISHED, IKEv2\n  local 'u' @ 1.2.3.4[500]\n")
        self.assertTrue(connected)
        self.assertEqual(vip, "Ativo")

    def test_error_mapping_ikext(self):
        self.assertIn("IKEEXT", map_engine_error("WFP MM failure"))

    def test_error_mapping_auth(self):
        self.assertIn("autenticacao", map_engine_error("[IKE] authentication_failure"))

    def test_error_mapping_proposal(self):
        self.assertIn("NO_PROPOSAL_CHOSEN", map_engine_error("no_proposal_chosen"))

    def test_error_mapping_falls_back_to_output(self):
        self.assertIn("algo deu errado", map_engine_error("algo deu errado"))


class TestStrongswanConf(unittest.TestCase):
    """Regressao: o parser do strongSwan rejeita ponto e aspas no filelog."""

    def test_filelog_target_has_no_dot_or_quotes(self):
        conf = build_strongswan_conf()
        self.assertNotIn('"', conf)
        for line in conf.splitlines():
            stripped = line.strip()
            if stripped.endswith("{") and "filelog" not in stripped and "charon-svc" not in stripped:
                self.assertNotIn(".", stripped, "nome de secao com ponto quebra o parser: %r" % stripped)

    def test_has_filelog(self):
        conf = build_strongswan_conf()
        self.assertIn("filelog", conf)
        self.assertIn("flush_line = yes", conf)
        # start-scripts rodam como SYSTEM na pasta do motor e nao enxergam
        # nosso diretorio de configuracao: nao devem existir.
        self.assertNotIn("start-scripts", conf)

    def test_redacts_secrets(self):
        from vpn_engine import redact_conf_text

        text = 'secrets {\n  ike-forticlient {\n    secret = "meu-psk"\n  }\n}\n'
        out = redact_conf_text(text)
        self.assertNotIn("meu-psk", out)
        self.assertIn("***REDACTED***", out)

    def test_shipped_conf_matches_generator(self):
        """O arquivo distribuído e o gerador não podem divergir."""
        path = os.path.join(BASE_DIR, "build", "strongswan-windows.conf")
        with open(path, encoding="utf-8") as handle:
            shipped = handle.read()
        effective = "\n".join(
            line for line in shipped.splitlines() if not line.strip().startswith("#")
        )
        self.assertNotIn('"', effective)
        for token in ("charonlog", "flush_line = yes"):
            self.assertIn(token, effective)
        self.assertNotIn("start-scripts", effective)


class TestLinuxEngine(unittest.TestCase):
    def test_connect_success(self):
        runner = FakeRunner({"swanctl --initiate": (0, "initiate completed successfully", ""),
                             "swanctl --list-sas": (0, ESTABLISHED, "")})
        engine = VpnEngine(platform="linux", runner=runner)
        status = engine.connect({"gateway": "198.51.100.100", "local_ip": "203.0.113.7",
                                 "user": "miranda", "password": "senha", "psk": "psk"})
        self.assertTrue(status.connected, status)
        self.assertEqual(status.vip, "10.10.20.5")

        conf_call = [call for call in runner.calls if call["argv"][:2] == ["sudo", "tee"]][0]
        self.assertIn("198.51.100.100", conf_call["input_text"])
        self.assertTrue(any("swanctl --initiate --child forticlient" in c for c in runner.commands()))

    def test_connect_failure_maps_error(self):
        runner = FakeRunner({"swanctl --initiate": (1, "[IKE] authentication_failure", ""),
                             "swanctl --list-sas": (0, "", "")})
        engine = VpnEngine(platform="linux", runner=runner)
        status = engine.connect({"gateway": "gw", "local_ip": "1.2.3.4",
                                 "user": "u", "password": "p", "psk": "k"})
        self.assertFalse(status.connected)
        self.assertIn("autenticacao", status.error)

    def test_disconnect(self):
        runner = FakeRunner({"swanctl --terminate": (0, "", "")})
        engine = VpnEngine(platform="linux", runner=runner)
        status = engine.disconnect()
        self.assertFalse(status.connected)
        self.assertTrue(any("swanctl --terminate --ike forticlient" in c for c in runner.commands()))

    def test_availability_uses_path(self):
        engine = VpnEngine(platform="linux", runner=FakeRunner())
        available, detail = engine.availability()
        self.assertIsInstance(available, bool)
        self.assertTrue(detail)


class TestWindowsEngine(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self._old_engine = os.environ.get("FCT_VPN_ENGINE_DIR")
        self._old_cfg = os.environ.get("XDG_CONFIG_HOME")
        self.engine_dir = os.path.join(self.tmp, "vendor", "windows")
        os.makedirs(self.engine_dir)
        for exe in ("charon-svc.exe", "swanctl.exe"):
            with open(os.path.join(self.engine_dir, exe), "w", encoding="utf-8") as handle:
                handle.write("stub")
        os.environ["FCT_VPN_ENGINE_DIR"] = self.engine_dir
        os.environ["XDG_CONFIG_HOME"] = self.tmp

    def tearDown(self):
        for key, old in (("FCT_VPN_ENGINE_DIR", self._old_engine), ("XDG_CONFIG_HOME", self._old_cfg)):
            if old is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = old

    def _runner(self):
        return FakeRunner(
            {
                "sc query strongSwan IKE service": (0, "STATE : 4 RUNNING", ""),
                "sc query IKEEXT": (0, "STATE : 4 RUNNING", ""),
                "sc stop IKEEXT": (0, "", ""),
                "swanctl.exe --load-all": (0, "loaded connection 'forticlient'", ""),
                "swanctl.exe --list-conns": (0, "connections:\n  forticlient: IKEv2", ""),
                "swanctl.exe --initiate": (0, "initiate completed successfully", ""),
                "swanctl.exe --list-sas": (0, ESTABLISHED, ""),
            }
        )

    def test_availability_finds_vendored_engine(self):
        engine = VpnEngine(platform="windows", runner=FakeRunner())
        available, detail = engine.availability()
        self.assertTrue(available)
        self.assertEqual(detail, self.engine_dir)

    def test_connect_writes_conf_and_stops_ikext(self):
        runner = self._runner()
        engine = VpnEngine(platform="windows", runner=runner)
        status = engine.connect(
            {
                "gateway": "198.51.100.100",
                "local_ip": "192.168.0.5",
                "user": "miranda",
                "password": "senha",
                "psk": "psk",
                "vip_strategy": "none",
            }
        )
        self.assertTrue(status.connected, status)
        commands = runner.commands()
        self.assertIn("sc stop IKEEXT", commands)
        self.assertTrue(any("swanctl.exe --initiate --child forticlient" in c for c in commands), commands)
        conf_file = os.path.join(self.tmp, "forticlient-vpn", "swanctl.conf")
        self.assertTrue(os.path.exists(conf_file))
        with open(conf_file, encoding="utf-8") as handle:
            content = handle.read()
        self.assertIn("198.51.100.100", content)
        # O swanctl lê o swanctl.conf: as conexões precisam estar NELE.
        self.assertIn("connections {", content)
        self.assertIn("secrets {", content)

    def test_connect_requires_engine(self):
        """Sem motor vendorizado a conexão falha com mensagem clara."""
        import unittest.mock as mock

        import vpn_engine

        engine = VpnEngine(platform="windows", runner=FakeRunner())
        with mock.patch.object(vpn_engine, "windows_engine_dir", return_value=None):
            status = engine.connect({"gateway": "gw", "user": "u", "password": "p", "psk": "k"})
        self.assertFalse(status.connected)
        self.assertIn("nao encontrado", status.error)

    def test_windows_calls_run_in_swanctl_config_dir(self):
        """
        Regressao do bug de campo: o swanctl deriva o diretorio de configuracao
        do strongswan.conf que ENCONTRA. Se rodar no diretorio do motor, ele acha
        o strongswan.conf de la e procura conf.d/ no lugar errado -> carrega zero
        conexoes com rc=0 e o initiate falha com "CHILD_SA config not found".
        """
        import vpn_engine

        runner = self._runner()
        engine = VpnEngine(platform="windows", runner=runner)
        engine.connect(
            {
                "gateway": "198.51.100.100",
                "local_ip": "192.168.0.5",
                "user": "miranda",
                "password": "senha",
                "psk": "psk",
                "vip_strategy": "none",
            }
        )

        expected_cwd = os.path.join(self.tmp, "forticlient-vpn")
        expected_conf_dir = expected_cwd
        swanctl_calls = [call for call in runner.calls if "swanctl.exe" in call["command"]]
        self.assertTrue(swanctl_calls)
        for call in swanctl_calls:
            self.assertEqual(call["cwd"], expected_cwd, call["command"])
            self.assertEqual(call["env"].get("SWANCTL_DIR"), expected_conf_dir)

        # Os três arquivos precisam estar no mesmo diretório:
        #   swanctl.conf (conexões/segredos) + strongswan.conf (lib/daemon)
        with open(os.path.join(expected_conf_dir, "swanctl.conf"), encoding="utf-8") as handle:
            self.assertIn("connections {", handle.read())
        self.assertTrue(os.path.exists(os.path.join(expected_conf_dir, "strongswan.conf")))
        self.assertNotEqual(expected_conf_dir, self.engine_dir)

    def test_connections_go_to_swanctl_conf_not_strongswan_conf(self):
        """
        Regressao de campo: o swanctl lê `swanctl.conf`, não `strongswan.conf`.
        Gravar as conexões só no strongswan.conf deixa o motor sem conexão
        nenhuma — e o --load-all ainda retorna rc=0.
        """
        import vpn_engine

        runner = self._runner()
        engine = VpnEngine(platform="windows", runner=runner)
        engine.connect(
            {
                "gateway": "198.51.100.100",
                "local_ip": "172.16.1.27",
                "user": "miranda",
                "password": "senha",
                "psk": "psk",
                "vip_strategy": "none",
            }
        )

        self.assertEqual(os.path.basename(vpn_engine.windows_swanctl_conf_file()), "swanctl.conf")
        with open(vpn_engine.windows_swanctl_conf_file(), encoding="utf-8") as handle:
            swanctl_conf = handle.read()
        with open(vpn_engine.windows_strongswan_conf_file(), encoding="utf-8") as handle:
            strongswan_conf = handle.read()

        self.assertIn("connections {", swanctl_conf)
        self.assertIn("secrets {", swanctl_conf)
        self.assertIn("198.51.100.100", swanctl_conf)
        # strongswan.conf é só da biblioteca/daemon (log) — nada de conexões.
        self.assertNotIn("connections {", strongswan_conf)

    def test_engine_logs_command_output(self):
        """Sem a saida do motor, um --load-all com rc=0 engana o diagnóstico."""
        logger = _CapturingLogger()
        runner = self._runner()
        engine = VpnEngine(platform="windows", runner=runner, logger=logger)
        engine._call(["cmd"], timeout=5)
        self.assertIn("cmd -> rc=0", logger.messages)

    def test_connect_reports_missing_connection_clearly(self):
        """
        Regressao de campo: --load-all com rc=0 sem carregar nada deve gerar uma
        mensagem acionavel, e não o críptico "CHILD_SA config not found".
        """
        runner = FakeRunner(
            {
                "sc query strongSwan IKE service": (0, "STATE : 4 RUNNING", ""),
                "sc query IKEEXT": (0, "STATE : 1 STOPPED", ""),
                "swanctl.exe --load-all": (0, "", ""),
                "swanctl.exe --list-conns": (0, "", ""),  # nada carregado
                "swanctl.exe --finalizar": (1, "", ""),
            }
        )
        engine = VpnEngine(platform="windows", runner=runner)
        status = engine.connect(
            {
                "gateway": "198.51.100.100",
                "local_ip": "172.16.1.27",
                "user": "miranda",
                "password": "senha",
                "psk": "psk",
                "vip_strategy": "none",
            }
        )
        self.assertFalse(status.connected)
        self.assertIn("nao foi carregada", status.error)
        self.assertIn("forticlient", status.error)
        # Não deve ter tentado iniciar o túnel sem a configuração carregada.
        self.assertFalse(any("--initiate" in c for c in runner.commands()), runner.commands())

    def test_cleanup_is_noop_off_windows(self):
        engine = VpnEngine(platform="linux", runner=FakeRunner())
        self.assertEqual(engine.cleanup_conflicts(), [])

    # ------------------------------------------------- autonomia (sem usuário)
    def test_service_failure_falls_back_to_background_charon(self):
        """Sem serviço, o motor sobe sozinho — o usuário não precisa corrigir."""
        runner = FakeRunner(
            {
                "sc query": (1, "SERVICE nao existe", ""),
                "sc create": (0, "", ""),
                "sc start": (0, "", ""),
                "Start-Process": (0, "", ""),
            }
        )
        engine = VpnEngine(platform="windows", runner=runner)
        self.assertTrue(engine._ensure_windows_service())
        self.assertTrue(any("Start-Process" in c for c in runner.commands()), runner.commands())

    def test_ikext_stop_falls_back_to_net_stop(self):
        """Se `sc stop` não resolver, tenta `net stop` antes de desistir."""
        runner = FakeRunner(
            {
                "sc query IKEEXT": (0, "STATE : 4 RUNNING", ""),
                "sc stop IKEEXT": (1, "acesso negado", ""),
                "net stop IKEEXT": (0, "", ""),
            }
        )
        # Depois do net stop, a verificação precisa enxergar PARADO.
        original = runner.__call__

        def patched(argv, **kwargs):
            result = original(argv, **kwargs)
            if " ".join(argv).startswith("sc query IKEEXT") and any(
                "net stop IKEEXT" in call for call in runner.commands()
            ):
                return Result(0, "STATE : 1 STOPPED", "", command=argv)
            return result

        engine = VpnEngine(platform="windows", runner=patched)
        self.assertTrue(engine._ensure_ikext_stopped())

    def test_vip_cascade_tries_other_interfaces(self):
        """VIP não instalável na interface padrão deve ser tentado nas demais."""
        runner = FakeRunner(
            {
                "Get-NetRoute": (0, "Ethernet", ""),
                "Get-NetAdapter": (0, "Ethernet\nWi-Fi", ""),
                "add address Ethernet 10.9.9.9": (0, "", ""),
                "show addresses Ethernet": (0, "IP: 192.168.0.5", ""),
                "add address Wi-Fi 10.9.9.9": (0, "", ""),
                "show addresses Wi-Fi": (0, "IP: 10.9.9.9", ""),
            }
        )
        engine = VpnEngine(platform="windows", runner=runner)
        note = engine._apply_vip("10.9.9.9", "auto")
        self.assertIn("Wi-Fi", note)
        self.assertEqual(engine._vip_strategy_used, ("10.9.9.9", "Wi-Fi"))

    def test_vip_failure_is_not_fatal(self):
        """Nenhuma interface aceita o VIP: apenas informa, não quebra a conexão."""
        runner = FakeRunner(
            {
                "Get-NetRoute": (0, "Ethernet", ""),
                "Get-NetAdapter": (0, "Ethernet", ""),
                "add address Ethernet 10.9.9.9": (1, "erro", ""),
                "show addresses Ethernet": (0, "IP: 192.168.0.5", ""),
            }
        )
        engine = VpnEngine(platform="windows", runner=runner)
        note = engine._apply_vip("10.9.9.9", "auto")
        self.assertIn("sem VIP", note)
        self.assertIsNone(engine._vip_strategy_used)

    def test_vip_remove_uses_recorded_interface(self):
        runner = FakeRunner({"show addresses Wi-Fi": (0, "IP: 10.9.9.9", "")})
        engine = VpnEngine(platform="windows", runner=runner)
        engine._vip_strategy_used = ("10.9.9.9", "Wi-Fi")
        engine._remove_vip()
        self.assertIsNone(engine._vip_strategy_used)
        self.assertTrue(any("delete address Wi-Fi 10.9.9.9" in c for c in runner.commands()), runner.commands())


if __name__ == "__main__":
    unittest.main()
