# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['D:/workbuddy workspace/2026-06-23-20-22-53/desktop/desktop_launcher.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('D:/workbuddy workspace/2026-06-23-20-22-53/desktop/icon.png', 'desktop/'),
        ('D:/workbuddy workspace/2026-06-23-20-22-53/kylin-secops-agent/backend', 'backend/'),
    ],
    hiddenimports=[],
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
    a.binaries,
    a.datas,
    [],
    name='KylinSecOps',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
