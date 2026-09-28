import json
import logging
import os
import sys
import tempfile
import unittest
import zipfile

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

import vpn_config  # noqa: E402


class TestConfigStore(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.path = os.path.join(self.tmp, "config.json")
        self.store = vpn_config.ConfigStore(self.path)

    def test_roundtrip_and_defaults(self):
        self.store.save({"gateway": "10.0.0.1", "user": "u", "password": "s3cr3t", "psk": "psk1"})
        cfg = self.store.load()
        self.assertEqual(cfg["gateway"], "10.0.0.1")
        self.assertEqual(cfg["engine"], "auto")  # default preenchido
        plain = self.store.load_plain()
        self.assertEqual(plain["password"], "s3cr3t")
        self.assertEqual(plain["psk"], "psk1")

    def test_delete(self):
        self.store.save({"user": "u"})
        self.store.delete()
        self.assertFalse(os.path.exists(self.path))
        self.assertEqual(self.store.load()["user"], "")

    def test_corrupt_file_does_not_raise(self):
        with open(self.path, "w", encoding="utf-8") as handle:
            handle.write("{ isso nao e json")
        self.assertEqual(self.store.load()["gateway"], vpn_config.DEFAULT_GATEWAY)

    def test_redact(self):
        red = vpn_config.redact({"user": "u", "password": "p", "psk": "k"})
        self.assertEqual(red["password"], "***REDACTED***")
        self.assertEqual(red["psk"], "***REDACTED***")
        self.assertEqual(red["user"], "u")

    def test_secrets_are_protected_helpers_exist(self):
        self.assertEqual(vpn_config.unprotect_secret(vpn_config.protect_secret("abc")), "abc")


class TestLogging(unittest.TestCase):
    def test_setup_is_idempotent_and_writes(self):
        tmp = tempfile.mkdtemp()
        target = os.path.join(tmp, "app.log")
        logger = vpn_config.setup_logging(path=target)
        first = len(logger.handlers)
        vpn_config.setup_logging(path=target)
        self.assertEqual(len(logger.handlers), first)

        logger.info("mensagem de teste")
        for handler in logger.handlers:
            handler.flush()
        with open(target, encoding="utf-8") as handle:
            self.assertIn("mensagem de teste", handle.read())


class TestDiagnostics(unittest.TestCase):
    def test_bundle_contents_and_redaction(self):
        tmp = tempfile.mkdtemp()
        log_file = os.path.join(tmp, "app.log")
        with open(log_file, "w", encoding="utf-8") as handle:
            handle.write("linha de log\n")

        cfg = {"user": "usuario", "password": "s3cr3t", "psk": "psk1"}
        dest = os.path.join(tmp, "diag.zip")
        path = vpn_config.build_diagnostics(
            dest=dest, cfg=cfg, extra_text={"sc query": "RUNNING"}, log_file=log_file
        )
        self.assertEqual(path, dest)

        with zipfile.ZipFile(path) as bundle:
            names = bundle.namelist()
            self.assertIn("resumo.txt", names)
            self.assertIn("config-redigido.json", names)
            self.assertIn("app.log", names)

            resumo = bundle.read("resumo.txt").decode("utf-8")
            self.assertIn("sc query", resumo)
            self.assertIn("versao:", resumo)

            redigido = json.loads(bundle.read("config-redigido.json").decode("utf-8"))
            self.assertEqual(redigido["password"], "***REDACTED***")
            self.assertEqual(redigido["psk"], "***REDACTED***")

            with bundle.open("app.log") as handle:
                self.assertIn("linha de log", handle.read().decode("utf-8"))

    def test_app_version_is_a_string(self):
        self.assertIsInstance(vpn_config.app_version(), str)


if __name__ == "__main__":
    unittest.main()
