#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gera `build_info.py` e mantém a versão sincronizada em todo o empacotamento.

O executável do Windows é GUI (console=False) e sem versão gravada é impossível
saber o que o usuário está rodando. No Linux, o mesmo dado aparece no log e no
`--diagnose`. Por isso a versão vive em UM lugar só — o arquivo `VERSION` na raiz
— e é propagada para:

  * `build_info.py`      → constante VERSION gravada no executável;
  * `build/FortiClient-VPN-Setup.iss` → AppVersion do instalador;
  * `debian/control`     → Version do pacote .deb.

Sem isso, a janela de 1.0.0 (Linux) contra 2.1.2 (Windows) que existia no
histórico quebra o suporte: o usuário não sabe qual versão tem instalada.

Uso:
    python3 build/gen_build_info.py            # lê ./VERSION
    FCT_VERSION=2.2.0 python3 build/gen_build_info.py   # força a versão

URL do Painel Web FortiOS (opcional, apenas para builds internos):
    FCT_WEB_URL=https://10.0.0.1:10443 python3 build/gen_build_info.py
Somente quem define FCT_WEB_URL tem o atalho "Abrir Painel Web" habilitado no
build. O padrão é vazio — os artefatos públicos não embutem endereço interno.
Endereços internos reais nunca devem entrar no código-fonte.
"""

import os
import re
import subprocess
import sys

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VERSION_FILE = os.path.join(ROOT_DIR, "VERSION")
FALLBACK_VERSION = "0.0.0"

# URL do Painel Web FortiOS. Só entra no build se FCT_WEB_URL for definida em
# tempo de compilação (padrão: vazio = sem atalho de painel no app).
WEB_URL_DEFAULT = ""


def resolve_web_url():
    """URL do painel embutida no build; vazio para builds públicos."""
    return os.environ.get("FCT_WEB_URL", "").strip() or WEB_URL_DEFAULT

# Alvos que recebem a versão, e o padrão de linha a reescrever em cada um.
SYNC_TARGETS = (
    (os.path.join(ROOT_DIR, "build", "FortiClient-VPN-Setup.iss"), r"(?m)^AppVersion=.*$", "AppVersion=%s"),
    (os.path.join(ROOT_DIR, "debian", "control"), r"(?m)^Version:.*$", "Version: %s"),
)

# `debian/control` também é lido por ferramentas que exigem versão estrita.
VERSION_RE = re.compile(r"^\d+(\.\d+)*([.-]?(a|b|rc|alpha|beta|dev)\d*)?$", re.IGNORECASE)


def read_version_file():
    """Versão declarada em ./VERSION, ou string vazia se o arquivo não existir."""
    try:
        with open(VERSION_FILE, encoding="utf-8") as handle:
            return handle.read().strip()
    except OSError:
        return ""


def resolve_version():
    """FCT_VERSION > ./VERSION > fallback, validando o formato."""
    version = os.environ.get("FCT_VERSION", "").strip() or read_version_file()
    if not version:
        print("[aviso] %s ausente; usando %s" % (VERSION_FILE, FALLBACK_VERSION), file=sys.stderr)
        return FALLBACK_VERSION
    if not VERSION_RE.match(version):
        print("[erro] versão inválida em VERSION: %r" % version, file=sys.stderr)
        return FALLBACK_VERSION
    return version


def _commit():
    try:
        result = subprocess.run(
            ["git", "-C", ROOT_DIR, "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return ""


def write_build_info(version, commit, web_url):
    target = os.path.join(ROOT_DIR, "build_info.py")
    content = (
        '"""Gerado automaticamente por build/gen_build_info.py. Não edite."""\n'
        'VERSION = "%s"\n'
        'COMMIT = "%s"\n'
        'WEB_URL = "%s"\n' % (version, commit, web_url)
    )
    with open(target, "w", encoding="utf-8") as handle:
        handle.write(content)
    return target


def sync_targets(version):
    """Alinha AppVersion (Inno Setup) e Version (debian/control) com ./VERSION.

    Só escreve quando o valor difere, para não sujar a árvore de trabalho à toa.
    """
    changed = []
    for path, pattern, template in SYNC_TARGETS:
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as handle:
            original = handle.read()
        updated = re.sub(pattern, template % version, original, count=1)
        if updated != original:
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(updated)
            changed.append(os.path.relpath(path, ROOT_DIR))
    return changed


def main():
    version = resolve_version()
    commit = _commit()
    web_url = resolve_web_url()
    write_build_info(version, commit, web_url)
    print("build_info.py: VERSION=%s COMMIT=%s WEB_URL=%r" % (version, commit or "-", web_url))
    for path in sync_targets(version):
        print("sincronizado para %s: %s" % (path, version))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
