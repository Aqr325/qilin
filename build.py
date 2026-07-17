#!/usr/bin/env python3
"""
麒麟OS安全运维 — 统一跨平台构建脚本
====================================
自动检测当前操作系统 (Windows / Linux)，构建对应平台的可执行包。

用法:
  python build.py                      # 构建当前平台完整包
  python build.py --backend-only       # 仅构建后端
  python build.py --frontend-only     # 仅构建前端
  python build.py --electron-only     # 仅构建 Electron 桌面包
  python build.py --sync-only         # 仅同步产出到交付目录
  python build.py --platform linux     # 指定构建平台 (默认自动检测)
  python build.py --help              # 查看帮助
"""
import os, sys, subprocess, shutil, json, platform
from pathlib import Path

# ═══════════════════════════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════════════════════════
ROOT = Path(__file__).resolve().parent

# 源码目录
BACKEND_DIR  = ROOT / 'kylin-secops-agent' / 'backend'
FRONTEND_DIR = ROOT / 'frontend'
DESKTOP_DIR  = ROOT / 'desktop'
ELECTRON_DIR = ROOT / 'electron-app'
OBSERV_DIR   = ROOT / 'observability'

# 交付目录
MAIN_DELIVERY  = ROOT / '麒麟OS安全运维_桌面程序'
AGENT_DELIVERY = ROOT / '麒麟OS安全智能运维Agent_桌面版交付'
RESOURCES      = ROOT / 'desktop' / 'resources'

# Windows 构建环境
WIN_BUILD_ENV = ROOT / 'desktop-build-env'
WIN_BACKEND_EXE = BACKEND_DIR / 'dist' / 'backend.exe'
LIN_BACKEND_EXE = BACKEND_DIR / 'dist' / 'backend'

# ═══════════════════════════════════════════════════════════════
# Platform detection
# ═══════════════════════════════════════════════════════════════
IS_WINDOWS = platform.system() == 'Windows'
IS_LINUX   = platform.system() == 'Linux'

def get_python():
    """获取当前平台合适的 Python 解释器路径"""
    if IS_WINDOWS:
        py = WIN_BUILD_ENV / 'Scripts' / 'python.exe'
        if py.exists():
            return str(py)
    # fallback: 系统 Python
    py = shutil.which('python3') or shutil.which('python')
    if py:
        return py
    print('[ERROR] No Python interpreter found')
    sys.exit(1)

def get_backend_dist():
    """获取后端编译输出路径"""
    if IS_WINDOWS:
        return WIN_BACKEND_EXE
    return LIN_BACKEND_EXE

# ═══════════════════════════════════════════════════════════════
# Build Steps
# ═══════════════════════════════════════════════════════════════

def build_backend():
    """用 PyInstaller 打包后端"""
    print(f'[1/4] Building backend for {platform.system()}...')
    os.chdir(str(BACKEND_DIR))

    python = get_python()
    print(f'  Python: {python}')
    print(f'  CWD:    {BACKEND_DIR}')

    # 清理旧的 dist
    dist_path = BACKEND_DIR / 'dist'
    build_path = BACKEND_DIR / 'build'
    if dist_path.exists():
        shutil.rmtree(str(dist_path))
    if build_path.exists():
        shutil.rmtree(str(build_path))

    # 检查 PyInstaller
    try:
        subprocess.run([python, '-m', 'PyInstaller', '--version'],
                       capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print('  Installing PyInstaller...')
        subprocess.run([python, '-m', 'pip', 'install', 'pyinstaller'],
                       check=True)

    # 执行 PyInstaller 打包
    result = subprocess.run(
        [python, '-m', 'PyInstaller', 'backend.spec', '--noconfirm'],
        capture_output=True, text=True)

    if result.returncode != 0:
        print(f'  [ERROR] PyInstaller failed:')
        print(result.stderr[-2000:] if result.stderr else result.stdout[-2000:])
        sys.exit(1)

    out = get_backend_dist()
    if out.exists():
        size_mb = out.stat().st_size / (1024 * 1024)
        print(f'  [OK] Backend built: {out.name} ({size_mb:.0f} MB)')
    else:
        print(f'  [WARN] Expected output not found: {out}')
        # Fallback: 尝试找 dist/ 里任何可执行文件
        dist_contents = list(BACKEND_DIR.glob('dist/*'))
        if dist_contents:
            print(f'  Found: {dist_contents}')
        else:
            print('  [ERROR] No build output found in dist/')
            sys.exit(1)

    os.chdir(str(ROOT))


def build_frontend():
    """用 Vite 构建前端"""
    print(f'[2/4] Building frontend...')
    os.chdir(str(FRONTEND_DIR))

    # 检查 node_modules
    nm = FRONTEND_DIR / 'node_modules'
    if not nm.exists():
        print('  Installing npm dependencies...')
        subprocess.run(['npm', 'install'], check=True)

    # 清理旧的 dist
    dist_path = FRONTEND_DIR / 'dist'
    if dist_path.exists():
        shutil.rmtree(str(dist_path))

    result = subprocess.run(['npx', 'vite', 'build'], capture_output=True, text=True)

    if result.returncode != 0:
        print(f'  [ERROR] Vite build failed:')
        print(result.stderr[-2000:] if result.stderr else result.stdout[-2000:])
        sys.exit(1)

    if (FRONTEND_DIR / 'dist' / 'index.html').exists():
        print(f'  [OK] Frontend built: frontend/dist/index.html')
    else:
        print(f'  [WARN] Frontend dist may be incomplete')

    os.chdir(str(ROOT))


def sync_deliveries():
    """同步构建产物到各交付目录"""
    print(f'[3/4] Syncing to delivery directories...')

    backend_exe = get_backend_dist()
    frontend_dist = FRONTEND_DIR / 'dist'

    if not frontend_dist.exists():
        print('  [SKIP] Frontend dist not found, skip sync')
        return

    # 目标目录列表
    targets = [
        MAIN_DELIVERY,
        AGENT_DELIVERY,
        RESOURCES,
    ]

    # 如果 AGENT_DELIVERY 还有嵌套目录
    nested = AGENT_DELIVERY / 'kylin-secops-agent' / '麒麟OS安全智能运维Agent_桌面版交付'
    if nested.exists():
        targets.append(nested)
    # 检查 electron-app release 里的嵌套交付
    for p in ELECTRON_DIR.rglob('麒麟OS安全智能运维Agent_桌面版交付'):
        if p.is_dir():
            targets.append(p)

    for tgt in targets:
        if not tgt.exists():
            print(f'  [SKIP] {tgt.name} — not found')
            continue

        tgt_resources = tgt / 'resources'
        if tgt_resources.exists():
            # 同步 backend 二进制
            if backend_exe.exists():
                # 目标文件名：Windows 用 .exe, Linux 用无后缀
                if IS_WINDOWS:
                    dst = tgt_resources / 'backend.exe'
                else:
                    dst = tgt_resources / 'backend'
                    # 也留一份 .exe 版本做向后兼容
                    dst_exe = tgt_resources / 'backend.exe'
                    shutil.copy2(str(backend_exe), str(dst_exe))
                shutil.copy2(str(backend_exe), str(dst))
                print(f'  {tgt.name}: backend → resources/backend ({(backend_exe.stat().st_size/1024/1024):.0f} MB)')

            # 同步前端
            tgt_frontend = tgt_resources / 'frontend'
            if tgt_frontend.exists():
                shutil.rmtree(str(tgt_frontend))
            shutil.copytree(str(frontend_dist), str(tgt_frontend))
            print(f'  {tgt.name}: frontend/dist/ → resources/frontend/')

            # 同步 config.json（保留版本号）
            src_cfg = ROOT / 'desktop' / 'resources' / 'config.json'
            if src_cfg.exists():
                shutil.copy2(str(src_cfg), str(tgt_resources / 'config.json'))
                print(f'  {tgt.name}: config.json synced')
        else:
            print(f'  [SKIP] {tgt.name} — no resources/ dir')

    print(f'  [OK] Synced to {len(targets)} delivery directories')


def build_electron():
    """用 electron-builder 打当前平台的桌面包"""
    print(f'[4/4] Building Electron package for {platform.system()}...')

    # 先确保前端和后端已同步
    sync_deliveries()

    os.chdir(str(DESKTOP_DIR))

    # 检查 node_modules
    nm = DESKTOP_DIR / 'node_modules'
    if not nm.exists():
        print('  Installing npm dependencies...')
        subprocess.run(['npm', 'install'], check=True)

    if IS_WINDOWS:
        cmd = ['npm', 'run', 'build:win']
    else:
        cmd = ['npm', 'run', 'build:linux']

    print(f'  Running: {" ".join(cmd)}')
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print(f'  [ERROR] Electron build failed:')
        print(result.stderr[-3000:] if result.stderr else result.stdout[-3000:])
        sys.exit(1)

    # 检查输出
    release_dir = DESKTOP_DIR / 'release'
    if release_dir.exists():
        items = [p.name for p in release_dir.iterdir()]
        print(f'  [OK] Electron build output ({len(items)} items)')
        for item in items:
            print(f'    - {item}')

    os.chdir(str(ROOT))


def full_build():
    """完整构建流水线"""
    build_backend()
    build_frontend()
    sync_deliveries()
    build_electron()
    print(f'\n{"="*55}')
    print(f'  [DONE] 全平台构建完成!')
    print(f'  平台: {platform.system()} {platform.machine()}')
    print(f'  后端: {get_backend_dist().name or "N/A"}')
    print(f'  前端: frontend/dist/index.html')
    print(f'  Electron: desktop/release/')
    print(f'{"="*55}')


def print_help():
    print(__doc__)


# ═══════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════
if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('--platform')]
    platform_override = None
    for i, a in enumerate(sys.argv[1:]):
        if a == '--platform' and i + 2 < len(sys.argv):
            platform_override = sys.argv[i + 2]
            # Remove platform arg from processing
            args = [a for a in sys.argv[1:] if a != sys.argv[i + 1]]

    mode = args[0] if args else 'all'

    if mode in ('--help', '-h'):
        print_help()
    elif mode == '--backend-only':
        build_backend()
    elif mode == '--frontend-only':
        build_frontend()
    elif mode == '--sync-only':
        sync_deliveries()
    elif mode == '--electron-only':
        build_electron()
    else:
        full_build()