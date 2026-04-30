# -*- mode: python ; coding: utf-8 -*-

import os
import sys

def get_certifi_path():
    import certifi
    return certifi.where()

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('splash.jpeg', '.'),
        (get_certifi_path(), 'certifi'),
    ],
    hiddenimports=[
        'duckdb', 'polars', 'requests', 'pandas', 'pyarrow', 'PySide6', 'matplotlib',
        'certifi', 'urllib3', 'charset_normalizer', 'idna',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter', '_tkinter',
    ],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='ZapOrion_VDA_Analyzer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='ZapOrion_VDA_Analyzer',
)

if sys.platform == 'darwin':
    app = BUNDLE(
        coll,
        name='ZapOrion_VDA_Analyzer.app',
        icon=None,
        bundle_identifier='com.zaporion.vda',
        info_plist={
            'NSHighResolutionCapable': True,
            'LSBackgroundOnly': False,
            'CFBundleShortVersionString': '1.0.0',
        },
    )
