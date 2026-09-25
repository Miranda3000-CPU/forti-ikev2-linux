#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FortiClient VPN Manager - Configuração, segredos e diagnóstico.

Módulo sem dependência de Tkinter (testável de forma isolada).
Responsável por:
  * localizar os diretórios de configuração/estado por sistema operacional;
  * ler/gravar o arquivo de credenciais (com DPAPI no Windows);
  * prover logging em arquivo (essencial no Windows, onde o app é GUI-only);
  * montar o pacote de diagnóstico exportável.
"""

from __future__ import annotations

import json
import logging
import logging.handlers
import os
import platform
import sys
import time
import zipfile

IS_WINDOWS = sys.platform == "win32"
IS_LINUX = sys.platform.startswith("linux")

APP_DIR_NAME = "FortiClientVPN"
LOGGER_NAME = "forticlient"
DEFAULT_GATEWAY = "198.51.100.100"
SECRET_KEYS = ("password", "psk")


# ─────────────────────────────────────────────────────────────── diretórios

def _home():
    return os.path.expanduser("~")


def config_dir():
    """Diretório de configuração persistente (credenciais)."""
    if IS_WINDOWS:
        base = os.environ.get("APPDATA") or _home()
        return os.path.join(base, APP_DIR_NAME)
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(_home(), ".config")
    return os.path.join(base, "forticlient-vpn")


def state_dir():
    """Diretório de estado (logs e diagnóstico), sem credenciais."""
    if IS_WINDOWS:
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") or _home()
        return os.path.join(base, APP_DIR_NAME)
    base = os.environ.get("XDG_STATE_HOME") or os.path.join(_home(), ".local", "state")
    return os.path.join(base, "forticlient-vpn")


def log_dir():
    return os.path.join(state_dir(), "logs")


def log_path():
    return os.path.join(log_dir(), "app.log")


def ensure_dir(path):
    if path:
        try:
            os.makedirs(path, exist_ok=True)
        except OSError:
            pass
    return path


# ─────────────────────────────────────────────────────────────── versão

def app_version():
    """Versão do build (gerada em build/build_info.py) ou 'dev'."""
    try:
        import build_info  # noqa: WPS433 (gerado no empacotamento)

        version = getattr(build_info, "VERSION", "dev")
        commit = getattr(build_info, "COMMIT", "")
        if commit:
            return f"{version}+{commit}"
        return str(version)
    except Exception:
        return "dev"


# ─────────────────────────────────────────────────────── Windows DPAPI

def dpapi_encrypt(plaintext):
    """Criptografa com Windows DPAPI (escopo do usuário). No-op fora do Windows."""
    if not IS_WINDOWS or not plaintext:
        return plaintext
    try:
        import base64
        import ctypes
        from ctypes import wintypes

        class DATA_BLOB(ctypes.Structure):
            _fields_ = [
                ("cbData", wintypes.DWORD),
                ("pbData", ctypes.POINTER(ctypes.c_byte)),
            ]

        data_bytes = plaintext.encode("utf-8")
        blob_in = DATA_BLOB(
            len(data_bytes),
            ctypes.cast(ctypes.create_string_buffer(data_bytes), ctypes.POINTER(ctypes.c_byte)),
        )
        blob_out = DATA_BLOB()

        # CRYPTPROTECT_UI_FORBIDDEN = 0x1
        if ctypes.windll.crypt32.CryptProtectData(
            ctypes.byref(blob_in), "FortiClientVPN", None, None, None, 0x1, ctypes.byref(blob_out)
        ):
            encrypted_bytes = ctypes.string_at(blob_out.pbData, blob_out.cbData)
            ctypes.windll.kernel32.LocalFree(blob_out.pbData)
            return "DPAPI:" + base64.b64encode(encrypted_bytes).decode("ascii")
    except Exception:
        pass
    return plaintext


def dpapi_decrypt(ciphertext):
    """Descriptografa string produzida por dpapi_encrypt. No-op fora do Windows."""
    if not IS_WINDOWS or not ciphertext or not ciphertext.startswith("DPAPI:"):
        return ciphertext
    try:
        import base64
        import ctypes
        from ctypes import wintypes

        class DATA_BLOB(ctypes.Structure):
            _fields_ = [
                ("cbData", wintypes.DWORD),
                ("pbData", ctypes.POINTER(ctypes.c_byte)),
            ]

        encrypted_bytes = base64.b64decode(ciphertext[6:])
        blob_in = DATA_BLOB(
            len(encrypted_bytes),
            ctypes.cast(ctypes.create_string_buffer(encrypted_bytes), ctypes.POINTER(ctypes.c_byte)),
        )
        blob_out = DATA_BLOB()

        if ctypes.windll.crypt32.CryptUnprotectData(
            ctypes.byref(blob_in), None, None, None, None, 0x1, ctypes.byref(blob_out)
        ):
            decrypted_bytes = ctypes.string_at(blob_out.pbData, blob_out.cbData)
            ctypes.windll.kernel32.LocalFree(blob_out.pbData)
            return decrypted_bytes.decode("utf-8")
    except Exception:
        pass
    return ciphertext


def protect_secret(value):
    """Cifra um segredo para persistência, quando o SO oferece suporte."""
    if not value:
        return value
    return dpapi_encrypt(value)


def unprotect_secret(value):
    """Decifra um segredo persistido, quando necessário."""
    if not value:
        return value
    return dpapi_decrypt(value)


def redact(data):
    """Cópia de um dicionário com os segredos substituídos (para diagnóstico)."""
    out = dict(data or {})
    for key in SECRET_KEYS:
        if out.get(key):
            out[key] = "***REDACTED***"
    return out


# ─────────────────────────────────────────────────────── ConfigStore

DEFAULT_CONFIG = {
    "gateway": DEFAULT_GATEWAY,
    "user": "",
    "password": "",
    "psk": "",
    "save_credentials": True,
    "custom_local_ip": "",
    "engine": "auto",
    "vip_strategy": "auto",
    "restore_ikext_on_exit": True,
}


class ConfigStore:
    """Leitura/gravação atômica do config.json com segredos protegidos."""

    def __init__(self, path=None):
        self.path = path or os.path.join(config_dir(), "config.json")

    def load(self):
        data = {}
        if os.path.exists(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as handle:
                    loaded = json.load(handle)
                if isinstance(loaded, dict):
                    data = loaded
            except (OSError, ValueError):
                data = {}
        merged = dict(DEFAULT_CONFIG)
        merged.update(data)
        return merged

    def load_plain(self):
        """Igual a load(), porém com senha/PSK já decifrados."""
        cfg = self.load()
        cfg["password"] = unprotect_secret(cfg.get("password", ""))
        cfg["psk"] = unprotect_secret(cfg.get("psk", ""))
        return cfg

    def save(self, cfg):
        data = dict(DEFAULT_CONFIG)
        data.update(cfg or {})
        data["password"] = protect_secret(data.get("password", ""))
        data["psk"] = protect_secret(data.get("psk", ""))
        ensure_dir(os.path.dirname(self.path))
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2)
        os.replace(tmp, self.path)
        if IS_LINUX:
            try:
                os.chmod(self.path, 0o600)
            except OSError:
                pass
        return self.path

    def delete(self):
        for candidate in (self.path, self.path + ".tmp"):
            if os.path.exists(candidate):
                try:
                    os.remove(candidate)
                except OSError:
                    pass


# ─────────────────────────────────────────────────────── logging

def setup_logging(level=logging.INFO, path=None):
    """
    Cria o logger em arquivo (com rotação). Idempotente.

    No Windows o executável é GUI (console=False), então o arquivo é a única
    forma de investigar falhas.
    """
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(level)
    logger.propagate = False
    has_file_handler = any(
        isinstance(handler, logging.handlers.RotatingFileHandler)
        for handler in logger.handlers
    )
    if not has_file_handler:
        target = path or log_path()
        ensure_dir(os.path.dirname(target))
        try:
            handler = logging.handlers.RotatingFileHandler(
                target, maxBytes=1_000_000, backupCount=3, encoding="utf-8"
            )
            handler.setFormatter(
                logging.Formatter("%(asctime)s %(levelname)-7s %(message)s", "%Y-%m-%d %H:%M:%S")
            )
            logger.addHandler(handler)
        except OSError:
            pass
    return logger


def get_logger():
    return logging.getLogger(LOGGER_NAME)


# ─────────────────────────────────────────────────────── diagnóstico

def _system_summary():
    lines = [
        f"FortiClient VPN Manager - diagnostico",
        f"data: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"versao: {app_version()}",
        f"python: {sys.version.split()[0]} ({sys.executable})",
        f"plataforma: {platform.platform()}",
        f"sys.platform: {sys.platform}",
        f"config: {os.path.join(config_dir(), 'config.json')}",
        f"logs: {log_path()}",
        f"congelado (PyInstaller): {bool(getattr(sys, 'frozen', False))}",
    ]
    return "\n".join(lines) + "\n"


def build_diagnostics(dest=None, cfg=None, extra_text=None, extra_files=None, log_file=None):
    """
    Gera um .zip com tudo o que é preciso para investigar uma falha.

    Nunca inclui senha/PSK em claro: o config é sempre redigido.
    """
    ensure_dir(state_dir())
    if not dest:
        stamp = time.strftime("%Y%m%d-%H%M%S")
        dest = os.path.join(state_dir(), f"diagnostico-{stamp}.zip")

    resumo = _system_summary()
    for name, text in (extra_text or {}).items():
        resumo += f"\n--- {name} ---\n{text}\n"

    active_log = log_file or log_path()
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as bundle:
        bundle.writestr("resumo.txt", resumo)
        if cfg is not None:
            bundle.writestr("config-redigido.json", json.dumps(redact(cfg), indent=2))
        if os.path.exists(active_log):
            try:
                bundle.write(active_log, "app.log")
            except OSError:
                pass
        for path in extra_files or []:
            if path and os.path.isfile(path):
                try:
                    bundle.write(path, os.path.basename(path))
                except OSError:
                    pass
    return dest
