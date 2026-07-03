"""
麒麟OS 安全运维桌面版 - PyInstaller 打包启动器
把 desktop_launcher.py 打包成单个 exe
"""

import os
import sys
import subprocess
import shutil

DESKTOP_DIR = os.path.dirname(os.path.abspath(__file__))


def build_launcher():
    """Build the desktop launcher into a standalone exe."""
    print('🏗️  打包桌面启动器...')

    launcher = os.path.join(DESKTOP_DIR, 'desktop_launcher.py')
    if not os.path.exists(launcher):
        print(f'  ✗ 找不到 {launcher}')
        return False

    # Ensure PyInstaller is installed
    try:
        import PyInstaller
        print('  ✓ PyInstaller 就绪')
    except ImportError:
        print('  ▶ 安装 PyInstaller...')
        subprocess.run([sys.executable, '-m', 'pip', 'install', 'pyinstaller'],
                      cwd=DESKTOP_DIR)
        print('  ✓ 已安装')

    # Clean old build
    for d in ['build', 'dist']:
        p = os.path.join(DESKTOP_DIR, d)
        if os.path.exists(p):
            shutil.rmtree(p)

    # Build
    cmd = [
        sys.executable, '-m', 'PyInstaller',
        '--onefile',           # Single exe
        '--console',           # Console window (shows log)
        '--name', 'KylinSecOps',
        '--clean',
        '--add-data', f'{DESKTOP_DIR}/icon.png{os.pathsep}desktop/',
        '--distpath', os.path.join(DESKTOP_DIR, 'dist'),
        '--workpath', os.path.join(DESKTOP_DIR, 'build'),
        '--specpath', DESKTOP_DIR,
        launcher,
    ]

    result = subprocess.run(cmd, cwd=DESKTOP_DIR)
    if result.returncode != 0:
        print(f'  ✗ 打包失败 (exit code {result.returncode})')
        return False

    exe_path = os.path.join(DESKTOP_DIR, 'dist', 'KylinSecOps.exe')
    if os.path.exists(exe_path):
        size = os.path.getsize(exe_path)
        print(f'  ✓ 打包成功!')
        print(f'  📦 {exe_path}')
        print(f'  📏 {size:,} bytes ({size/1024/1024:.1f} MB)')
        return True
    else:
        print(f'  ✗ 未找到输出 exe')
        return False


def build_all():
    """Full build: backend + frontend + launcher."""
    print('=' * 60)
    print('  麒麟OS 桌面版 - 完整构建')
    print('=' * 60)
    print()

    # Step 1: Build frontend
    frontend_dir = os.path.join(DESKTOP_DIR, '..', 'frontend')
    print('[1/3] 构建前端...')
    result = subprocess.run(['npm', 'run', 'build'], cwd=frontend_dir,
                          capture_output=True, text=True)
    if result.returncode != 0:
        print(f'  ✗ 前端构建失败')
        print(result.stderr[:500])
        return False
    print('  ✓ 前端构建完成')

    # Step 2: Copy frontend to desktop
    print('[2/3] 复制前端产物...')
    dest = os.path.join(DESKTOP_DIR, 'frontend')
    if os.path.exists(dest):
        shutil.rmtree(dest)
    shutil.copytree(os.path.join(frontend_dir, 'dist'), dest)
    print(f'  ✓ 已复制到 {dest}')

    # Step 3: Build launcher
    print('[3/3] 打包启动器...')
    if not build_launcher():
        return False

    print()
    print('=' * 60)
    print('  ✅ 完整构建完成!')
    print()
    print('  📂 输出目录:')
    print(f'     Frontend: {dest}')
    print(f'     Launcher: {os.path.join(DESKTOP_DIR, "dist", "KylinSecOps.exe")}')
    print()
    print('  🚀 运行方式:')
    print('     1. 双击 desktop/启动桌面版.bat')
    print('     2. 或运行 dist/KylinSecOps.exe')
    print('=' * 60)

    return True


if __name__ == '__main__':
    import sys
    if '--launcher' in sys.argv:
        build_launcher()
    else:
        build_all()
