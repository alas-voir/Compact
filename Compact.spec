# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

from PyInstaller.utils.hooks import collect_all


def _existing_entries(entries):
    filtered = []
    for entry in entries:
        source = entry[0]
        if isinstance(source, (list, tuple)):
            source = source[0]
        if Path(source).exists():
            filtered.append(entry)
    return filtered


datas = [('assets', 'assets'), ('bin', 'bin')]
binaries = []
hiddenimports = []
tmp_ret = collect_all('yt_dlp')
datas += _existing_entries(tmp_ret[0])
binaries += _existing_entries(tmp_ret[1])
hiddenimports += tmp_ret[2]


a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=binaries,
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
    name='Compact',
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
    icon=['assets/icons/Compact.icns'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Compact',
)
app = BUNDLE(
    coll,
    name='Compact.app',
    icon='assets/icons/Compact.icns',
    bundle_identifier='app.compact.player',
    info_plist={
        'CFBundleShortVersionString': '0.8.0',
        'CFBundleVersion': '0.8.0',
    },
)
