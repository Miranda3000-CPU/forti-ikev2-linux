# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec para FortiClient VPN Manager.
Gera executável único multiplataforma (.exe no Windows, binário no Linux).
"""

import sys
import os

# Detectar assets disponíveis dinamicamente
datas_list = []
assets_dir = os.path.join(SPECPATH, 'assets')

for asset_name in ['dtic-logo-whasapp.jpeg', 'icon.png', 'icon.ico']:
    asset_path = os.path.join(assets_dir, asset_name)
    if os.path.exists(asset_path):
        datas_list.append((asset_path, 'assets'))

# Ícone do executável (apenas .ico no Windows, .png no Linux)
icon_file = None
if sys.platform == 'win32':
    ico_path = os.path.join(assets_dir, 'icon.ico')
    if os.path.exists(ico_path):
        icon_file = ico_path
else:
    png_path = os.path.join(assets_dir, 'icon.png')
    if os.path.exists(png_path):
        icon_file = png_path

a = Analysis(
    ['vpn-gui.py'],
    pathex=[],
    binaries=[],
    datas=datas_list,
    hiddenimports=[
        'PIL',
        'PIL.Image',
        'PIL.ImageTk',
        'PIL.ImageDraw',
        'PIL.ImageOps',
        'PIL._tkinter_finder',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib',
        'numpy',
        'scipy',
        'pandas',
        'pytest',
        'unittest',
    ],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

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
    strip=True,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_file,
)
