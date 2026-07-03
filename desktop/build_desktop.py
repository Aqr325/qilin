#!/usr/bin/env python3
"""
麒麟OS 安全运维桌面版 - 一键构建脚本

Usage:
    python build_desktop.py            # 完整构建
    python build_desktop.py --backend  # 仅构建后端
    python build_desktop.py --frontend # 仅构建前端
    python build_desktop.py --installer # 构建安装包
"""

import os
import sys
import subprocess
import shutil
import urllib.request
import json
import re

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(ROOT_DIR, '..', 'frontend')
BACKEND_DIR = os.path.join(ROOT_DIR, '..', 'kylin-secops-agent', 'backend')
DESKTOP_DIR = ROOT_DIR
DIST_DIR = os.path.join(FRONTEND_DIR, 'dist')
DESKTOP_FRONTEND_DIR = os.path.join(DESKTOP_DIR, 'frontend')
BACKEND_OUTPUT_DIR = os.path.join(BACKEND_DIR, 'dist', 'kylin-secops-backend')

CHART_JS_URL = 'https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js'
CHART_JS_DEST = 'lib/chart.umd.min.js'


def run(cmd, cwd=None, description=None):
    """Run a command and print output."""
    if description:
        print(f'\n{"=" * 60}')
        print(f"  ▶ {description}")
        print(f'{"=" * 60}')

    print(f"  $ {cmd if isinstance(cmd, str) else ' '.join(cmd)}")
    result = subprocess.run(
        cmd, cwd=cwd, shell=isinstance(cmd, str),
        capture_output=True, text=True
    )

    if result.stdout:
        for line in result.stdout.strip().split('\n'):
            print(f"  {line}")

    if result.stderr and result.returncode != 0:
        for line in result.stderr.strip().split('\n')[-5:]:
            print(f"  ! {line}")

    if result.returncode != 0:
        print(f"  ✗ FAILED (exit code {result.returncode})")
    else:
        print(f"  ✓ Done")

    return result.returncode == 0


def build_frontend():
    """Build Vue frontend to dist/."""
    print('\n📦 Building Frontend...')

    # Install dependencies if needed
    node_modules = os.path.join(FRONTEND_DIR, 'node_modules')
    if not os.path.exists(node_modules):
        if not run('npm install', cwd=FRONTEND_DIR, description='Installing frontend dependencies'):
            return False

    # Build
    if not run('npm run build', cwd=FRONTEND_DIR, description='Building frontend (vite build)'):
        return False

    print(f'  ✓ Frontend built: {DIST_DIR}')
    return True


def patch_dist_chartjs():
    """Download Chart.js locally and update index.html to use local copy."""
    print('\n📦 Patching dist/ for offline Chart.js...')

    lib_dir = os.path.join(DIST_DIR, 'lib')
    os.makedirs(lib_dir, exist_ok=True)
    chart_dest = os.path.join(lib_dir, 'chart.umd.min.js')

    if not os.path.exists(chart_dest):
        print(f'  Downloading Chart.js from CDN...')
        try:
            urllib.request.urlretrieve(CHART_JS_URL, chart_dest)
            size = os.path.getsize(chart_dest)
            print(f'  ✓ Downloaded ({size:,} bytes)')
        except Exception as e:
            print(f'  ⚠ Failed to download: {e}')
            return False
    else:
        print(f'  ✓ Chart.js already cached ({os.path.getsize(chart_dest):,} bytes)')

    # Update index.html to use local path
    index_path = os.path.join(DIST_DIR, 'index.html')
    with open(index_path, 'r', encoding='utf-8') as f:
        content = f.read()

    old_cdn = '<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>'
    new_local = '<script src="lib/chart.umd.min.js"></script>'

    if old_cdn in content:
        content = content.replace(old_cdn, new_local)
        with open(index_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f'  ✓ index.html updated: CDN → local reference')
    else:
        print(f'  ✓ CDN reference already patched')

    return True


def copy_frontend_to_desktop():
    """Copy dist/ to desktop/frontend/ for Electron packaging."""
    print('\n📦 Copying frontend to desktop/...')

    # Remove old
    if os.path.exists(DESKTOP_FRONTEND_DIR):
        shutil.rmtree(DESKTOP_FRONTEND_DIR)

    # Copy new
    shutil.copytree(DIST_DIR, DESKTOP_FRONTEND_DIR)
    total_size = sum(os.path.getsize(os.path.join(dp, f))
                     for dp, _, fn in os.walk(DESKTOP_FRONTEND_DIR) for f in fn)
    print(f'  ✓ Copied {total_size:,} bytes to {DESKTOP_FRONTEND_DIR}')
    return True


def build_backend():
    """Build backend with PyInstaller."""
    print('\n🏗️  Building Backend with PyInstaller...')

    # Check PyInstaller
    result = subprocess.run(['pip', 'show', 'pyinstaller'], capture_output=True, text=True)
    if result.returncode != 0:
        print('  Installing PyInstaller...')
        run('pip install pyinstaller', description='Installing PyInstaller')

    # Clean old build
    dist_dir = os.path.join(BACKEND_DIR, 'dist')
    if os.path.exists(dist_dir):
        shutil.rmtree(dist_dir)
    build_dir = os.path.join(BACKEND_DIR, 'build')
    if os.path.exists(build_dir):
        shutil.rmtree(build_dir)

    # Build
    spec_file = os.path.join(BACKEND_DIR, 'desktop.spec')
    if not run(f'pyinstaller "{spec_file}"', cwd=BACKEND_DIR, description='Running PyInstaller'):
        return False

    backend_exe = os.path.join(BACKEND_OUTPUT_DIR, 'kylin-secops-backend.exe')
    if os.path.exists(backend_exe):
        size = os.path.getsize(backend_exe)
        total = sum(os.path.getsize(os.path.join(dp, f))
                    for dp, _, fn in os.walk(BACKEND_OUTPUT_DIR) for f in fn)
        print(f'  ✓ Backend exe: {backend_exe} ({size:,} bytes)')
        print(f'  ✓ Total bundle: {total:,} bytes')
        return True
    else:
        print(f'  ✗ Backend exe not found at {backend_exe}')
        return False


def build_electron_installer():
    """Build Electron installer with electron-builder."""
    print('\n📀 Building Electron Installer...')

    # Install electron dependencies if needed
    node_modules = os.path.join(DESKTOP_DIR, 'node_modules')
    if not os.path.exists(node_modules):
        if not run('npm install', cwd=DESKTOP_DIR, description='Installing Electron dependencies'):
            return False

    # Build
    if not run('npm run build:win', cwd=DESKTOP_DIR, description='Building Electron installer (electron-builder)'):
        return False

    # Find the installer
    release_dir = os.path.join(DESKTOP_DIR, 'release')
    if os.path.exists(release_dir):
        for root, dirs, files in os.walk(release_dir):
            for f in files:
                if f.endswith('.exe') or f.endswith('.msi'):
                    print(f'  ✓ Installer: {os.path.join(root, f)}')
    return True


def check_prerequisites():
    """Check all prerequisites."""
    print('🔍 Checking prerequisites...')
    all_ok = True

    # Python
    py_ver = sys.version
    print(f'  ✓ Python: {py_ver}')

    # Node
    result = subprocess.run(['node', '--version'], capture_output=True, text=True)
    if result.returncode == 0:
        print(f'  ✓ Node: {result.stdout.strip()}')
    else:
        print(f'  ✗ Node.js not found')
        all_ok = False

    # npm
    result = subprocess.run(['npm', '--version'], capture_output=True, text=True)
    if result.returncode == 0:
        print(f'  ✓ npm: {result.stdout.strip()}')
    else:
        print(f'  ✗ npm not found')
        all_ok = False

    # Frontend
    if not os.path.exists(os.path.join(FRONTEND_DIR, 'package.json')):
        print(f'  ✗ Frontend package.json not found at {FRONTEND_DIR}')
        all_ok = False
    else:
        print(f'  ✓ Frontend: {FRONTEND_DIR}')

    # Backend
    if not os.path.exists(os.path.join(BACKEND_DIR, 'desktop_server.py')):
        print(f'  ✗ desktop_server.py not found at {BACKEND_DIR}')
        all_ok = False
    else:
        print(f'  ✓ Backend: {BACKEND_DIR}')

    return all_ok


def main():
    print()
    print(f'╔{"═" * 58}╗')
    print(f'║  麒麟OS 安全智能运维 - 桌面版构建工具')
    print(f'║  Kylin SecOps Agent Desktop Builder')
    print(f'╚{"═" * 58}╝')
    print()

    # Parse args
    args = set(sys.argv[1:]) if len(sys.argv) > 1 else {'all'}
    do_all = 'all' in args or len(args & {'--backend', '--frontend', '--installer'}) == 0

    if not check_prerequisites():
        print('\n✗ Prerequisites check failed. Please fix the issues above.')
        sys.exit(1)

    success = True

    if do_all or '--frontend' in args:
        success &= build_frontend()
        success &= patch_dist_chartjs()
        success &= copy_frontend_to_desktop()

    if do_all or '--backend' in args:
        success &= build_backend()

    if do_all or '--installer' in args:
        success &= build_electron_installer()

    print()
    print(f'╔{"═" * 58}╗')
    if success:
        print(f'║  ✅ 构建完成！Desktop build complete!')
        print(f'║')
        print(f'║  📂 桌面版资源:')
        print(f'║     Frontend: {DESKTOP_FRONTEND_DIR}')
        print(f'║     Backend:  {BACKEND_OUTPUT_DIR}')
        print(f'║')
        print(f'║  🚀 开发调试:')
        print(f'║     cd desktop && npm start')
        print(f'╚{"═" * 58}╝')
    else:
        print(f'║  ❌ 构建过程中有失败步骤, 请检查上方日志')
        print(f'╚{"═" * 58}╝')

    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
