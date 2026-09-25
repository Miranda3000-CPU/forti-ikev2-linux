# -*- mode: python ; coding: utf-8 -*-
import sys
import os

SPEC_DIR = os.path.dirname(os.path.abspath(SPEC))
ROOT_DIR = os.path.abspath(os.path.join(SPEC_DIR, '..'))

block_cipher = None

a = Analysis(
    [os.path.join(ROOT_DIR, 'vpn-gui.py')],
    pathex=[ROOT_DIR],
    binaries=[],
    datas=[
        (os.path.join(ROOT_DIR, 'assets', 'icon.png'), 'assets'),
        (os.path.join(ROOT_DIR, 'assets', 'icon.ico'), 'assets'),
        (os.path.join(ROOT_DIR, 'assets', 'dtic-logo-whasapp.jpeg'), 'assets')
    ],
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
