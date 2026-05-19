# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

hiddenimports = []
hiddenimports += collect_submodules('fitz')
hiddenimports += collect_submodules('PIL')
try:
    hiddenimports += collect_submodules('tkinterdnd2')
except Exception:
    pass

datas = []
datas += collect_data_files('fitz', include_py_files=True)
datas += collect_data_files('PIL', include_py_files=True)
try:
    datas += collect_data_files('tkinterdnd2', include_py_files=True)
except Exception:
    pass

block_cipher = None

a = Analysis(
    ['artboard_cutter_gui_advanced.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='ArtboardCutter',
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
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='ArtboardCutter'
)

