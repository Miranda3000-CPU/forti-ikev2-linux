#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gera `build_info.py` com a versão e o commit usados no pacote.

O executável é GUI (console=False) e sem versão gravada é impossível saber
o que o usuário está rodando. Rode este script antes do PyInstaller.
"""

import os
import subprocess

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_VERSION = "2.1.2"


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


def main():
    version = os.environ.get("FCT_VERSION", DEFAULT_VERSION)
    commit = _commit()
    target = os.path.join(ROOT_DIR, "build_info.py")
    with open(target, "w", encoding="utf-8") as handle:
        handle.write('"""Gerado automaticamente por build/gen_build_info.py."""\n')
        handle.write('VERSION = "%s"\n' % version)
        handle.write('COMMIT = "%s"\n' % commit)
    print("build_info.py: VERSION=%s COMMIT=%s" % (version, commit or "-"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
