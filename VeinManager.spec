# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files
from PyInstaller.utils.hooks import collect_submodules

datas = []
hiddenimports = []
datas += collect_data_files('ruamel')
datas += collect_data_files('ruamel.yaml')
hiddenimports += collect_submodules('GUI')
hiddenimports += collect_submodules('ruamel')
hiddenimports += collect_submodules('ruamel.yaml')


a = Analysis(
    ['G:\\Servers\\VeinServer\\VeinServerManagement\\Controller\\vein_manager.py'],
    pathex=['G:\\Servers\\VeinServer\\VeinServerManagement\\Controller'],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='VeinManager',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['G:\\Servers\\VeinServer\\VeinServerManagement\\Installer\\assets\\VeinServerManager.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='VeinManager',
)
