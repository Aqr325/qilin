# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for Kylin SecOps Agent (Windows lightweight).
PyInstaller runs this from the spec file's directory, so os.getcwd() == spec dir.
"""
import os

spec_dir = os.getcwd()
src_dir = os.path.join(spec_dir, "src")
main_script = os.path.join(src_dir, "__main__.py")

hidden_imports = ["psutil", "requests", "yaml"]

datas = []
for root, dirs, files in os.walk(src_dir):
    for f in files:
        if f == "__init__.py":
            fp = os.path.join(root, f)
            rel = os.path.relpath(fp, src_dir)
            datas.append((fp, rel))

config_json = os.path.join(spec_dir, "config.json")
if os.path.exists(config_json):
    datas.append((config_json, "."))

a = Analysis(
    [main_script],
    pathex=[src_dir],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        "tkinter", "matplotlib", "numpy", "PIL", "PILLOW",
        "gi", "pygments", "sphinx", "docutils",
    ],
    noarchive=False,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="kylin-agent-win",
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
