# -*- mode: python ; coding: utf-8 -*-
import sys
import os

SPEC_DIR = os.path.dirname(os.path.abspath(SPEC))
ROOT_DIR = os.path.abspath(os.path.join(SPEC_DIR, '..'))

block_cipher = None

# Motor strongSwan para Windows (charon-svc.exe, swanctl.exe, DLLs, conf).
#
# Vem como `datas` e não como `binaries`: são executáveis standalone do MinGW
# com as próprias DLLs ao lado, e o PyInstaller não deve tentar analisar suas
# dependências — ele as resolveria contra as libs do build e quebraria o
# pacote. Como `datas`, a pasta sai inteira e o aplicativo a descompacta num
# diretório estável na primeira execução (ver materialize_bundled_engine).
#
# Só entra no build de Windows: no Linux o motor é o strongSwan do sistema e
# estes .exe seriam ~12 MB de peso morto dentro do binário.
ENGINE_DIR = os.path.join(ROOT_DIR, 'vendor', 'windows')
engine_datas = []
if sys.platform == 'win32' and os.path.isdir(ENGINE_DIR):
    for _nome in sorted(os.listdir(ENGINE_DIR)):
        _caminho = os.path.join(ENGINE_DIR, _nome)
        if os.path.isfile(_caminho):
            engine_datas.append((_caminho, os.path.join('vendor', 'windows')))

a = Analysis(
    [os.path.join(ROOT_DIR, 'vpn-gui.py')],
    pathex=[ROOT_DIR],
    binaries=[],
    datas=[
        (os.path.join(ROOT_DIR, 'assets', 'icon.png'), 'assets'),
        (os.path.join(ROOT_DIR, 'assets', 'icon.ico'), 'assets'),
        (os.path.join(ROOT_DIR, 'assets', 'dtic-logo-whasapp.jpeg'), 'assets')
    ] + engine_datas,
    hiddenimports=['PIL', 'PIL._tkinter_finder'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='FortiClient-VPN',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(ROOT_DIR, 'assets', 'icon.ico'),
    # Não elevar a GUI inteira: o executável roda como usuário normal e só as
    # operações que exigem admin (serviço charon-svc, IKEEXT, VIP) pedem UAC.
    # A elevação forçada causava conflito de contexto (perfil/DPAPI/serviços).
)
