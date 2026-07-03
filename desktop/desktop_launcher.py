"""
KylinOS SecOps Agent — Desktop Launcher

Double-click to run. Auto:
1. Start backend API server
2. Open browser to frontend
3. Ctrl+C or close window = graceful shutdown
"""

import subprocess
import sys
import os
import signal
import time
import webbrowser
import threading
import urllib.request
import json
import atexit
import io

# ═══════════════════════════════════
# Path Resolution
# ═══════════════════════════════════

if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
    # PyInstaller onefile mode: backend/ was bundled into _MEIPASS
    meipass = sys._MEIPASS
    if os.path.isdir(os.path.join(meipass, 'backend')):
        # backend/ at _MEIPASS root
        PROJECT_DIR = meipass
    elif os.path.isdir(os.path.join(meipass, 'kylin-secops-agent', 'backend')):
        # backend/ nested under kylin-secops-agent/
        PROJECT_DIR = os.path.join(meipass, 'kylin-secops-agent')
    else:
        # Fallback: try WORKSPACE_ROOT env var
        ws = os.environ.get('WORKSPACE_ROOT', '').strip()
        if ws and os.path.isdir(ws):
            PROJECT_DIR = ws
        else:
            # Hardcoded fallback
            PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(sys.executable)))
    # Data directory: where config.json and db live (next to exe)
    data_dir = os.path.dirname(os.path.abspath(sys.executable))
else:
    # Source mode: desktop/ sits inside project root
    base_dir = os.path.dirname(os.path.abspath(__file__))
    PROJECT_DIR = os.path.dirname(base_dir)
    data_dir = os.path.join(PROJECT_DIR, 'desktop')

BACKEND_DIR = os.path.join(PROJECT_DIR, 'backend')
# Fallback: if backend/ doesn't exist at PROJECT_DIR, check kylin-secops-agent/backend/
if not os.path.isdir(BACKEND_DIR):
    alt = os.path.join(PROJECT_DIR, 'kylin-secops-agent', 'backend')
    if os.path.isdir(alt):
        BACKEND_DIR = alt
BASE_DIR = os.path.join(PROJECT_DIR, 'desktop')
FRONTEND_DIR = os.path.join(BASE_DIR, 'frontend')

BACKEND_PORT = 8000
BACKEND_URL = f'http://127.0.0.1:{BACKEND_PORT}'
backend_process = None
running = True


# ═══════════════════════════════════
# Console UI
# ═══════════════════════════════════

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')


def print_banner():
    clear_screen()
    print()
    print(f'  +{"=" * 56}+')
    print(f'  |  KylinOS SecOps Agent — Desktop Launcher')
    print(f'  |{"=" * 56}|')
    print(f'  |  Q = Quit  |  R = Restart Backend  |  O = Open Browser')
    print(f'  +{"=" * 56}+')
    print()


# ═══════════════════════════════════
# Backend Management
# ═══════════════════════════════════

def find_python():
    """Find a usable Python interpreter."""
    if getattr(sys, 'frozen', False):
        # In bundled mode, just use 'python' (it should be on PATH)
        return 'python'
    candidates = [
        sys.executable,
        'python',
        'python3',
        os.path.join(PROJECT_DIR, 'venv', 'Scripts', 'python.exe'),
    ]
    for py in candidates:
        if py and os.path.exists(py):
            return py
    return sys.executable


def start_backend():
    """Start the backend server."""
    global backend_process

    desktop_server = os.path.join(BACKEND_DIR, 'desktop_server.py')
    if not os.path.exists(desktop_server):
        print(f'  [ERROR] Cannot find backend: {desktop_server}')
        print(f'  Project dir: {PROJECT_DIR}')
        return False

    python_path = find_python()
    print(f'  [START] Launching backend server...')
    print(f'  Python:  {python_path}')
    print(f'  Script:  {desktop_server}')

    try:
        env = os.environ.copy()
        env['WORKSPACE_ROOT'] = PROJECT_DIR

        backend_process = subprocess.Popen(
            [python_path, desktop_server],
            cwd=BACKEND_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=1,
            universal_newlines=True,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
            env=env,
        )
        return True
    except Exception as e:
        print(f'  [ERROR] Start failed: {e}')
        return False


def stop_backend():
    """Stop the backend server."""
    global backend_process
    if backend_process:
        print('  [STOP] Stopping backend server...')
        try:
            if os.name == 'nt':
                subprocess.run(['taskkill', '/F', '/T', '/PID', str(backend_process.pid)],
                              capture_output=True)
            else:
                backend_process.terminate()
                backend_process.wait(timeout=5)
        except Exception:
            pass
        backend_process = None
        print('  [OK] Stopped')


def restart_backend():
    """Restart the backend server."""
    print('  [RESTART] Restarting backend...')
    stop_backend()
    time.sleep(1)
    if start_backend():
        print('  [OK] Restart succeeded')
    else:
        print('  [ERROR] Restart failed')


# ═══════════════════════════════════
# Health Check
# ═══════════════════════════════════

def wait_for_backend(timeout=30):
    """Wait for the backend to become healthy."""
    print(f'  [WAIT] Waiting for backend ({timeout}s timeout)...')
    for i in range(timeout):
        if not running:
            return False
        try:
            resp = urllib.request.urlopen(f'{BACKEND_URL}/health', timeout=2)
            if resp.status == 200:
                data = json.loads(resp.read().decode())
                print(f'  [OK] Backend ready: {data.get("status", "ok")}')
                print(f'  API: {BACKEND_URL}')
                print(f'  Docs: {BACKEND_URL}/docs')
                return True
        except Exception:
            pass
        time.sleep(1)
    print(f'  [WARN] Backend not ready within timeout')
    return False


# ═══════════════════════════════════
# Frontend
# ═══════════════════════════════════

def get_frontend_url():
    """Get the frontend URL to open."""
    # Check if dev server is running
    try:
        resp = urllib.request.urlopen('http://127.0.0.1:5173', timeout=2)
        if resp.status == 200:
            return 'http://localhost:5173'
    except Exception:
        pass

    # Check if we have built frontend
    index_path = os.path.join(FRONTEND_DIR, 'index.html')
    if os.path.exists(index_path):
        return f'file:///{os.path.normpath(FRONTEND_DIR)}/index.html'

    # Fallback to backend API
    return f'{BACKEND_URL}/docs'


def open_browser():
    """Open the frontend in the default browser."""
    url = get_frontend_url()
    print(f'  [BROWSER] Opening: {url}')
    webbrowser.open(url)


# ═══════════════════════════════════
# Console Input Thread
# ═══════════════════════════════════

def input_thread():
    global running
    while running:
        try:
            if sys.stdin:
                cmd = sys.stdin.read(1)
                if cmd:
                    cmd = cmd.lower()
                    if cmd == 'q':
                        print('\n  [EXIT] Shutting down...')
                        running = False
                        break
                    elif cmd == 'r':
                        restart_backend()
                    elif cmd == 'o':
                        open_browser()
        except Exception:
            break


# ═══════════════════════════════════
# Output Thread
# ═══════════════════════════════════

def output_thread():
    """Print backend output to console."""
    while running:
        if backend_process and backend_process.stdout:
            try:
                line = backend_process.stdout.readline()
                if line:
                    clean = line.strip()
                    if clean:
                        print(f'  {clean}')
            except Exception:
                break
        else:
            time.sleep(0.5)


# ═══════════════════════════════════
# Main
# ═══════════════════════════════════

def main():
    global running

    # Fix stdout/stderr for bundled mode
    if getattr(sys, 'frozen', False):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='ascii', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='ascii', errors='replace')

    print_banner()
    atexit.register(stop_backend)

    # ── Start backend ──
    if not start_backend():
        print()
        input('  Press Enter to exit...')
        return

    # ── Wait for backend ──
    wait_for_backend()

    # ── Login info ──
    print()
    print(f'  {"-" * 40}')
    print(f'  Login Credentials')
    print(f'  {"-" * 40}')
    print(f'  Admin:    admin / admin123')
    print(f'  Operator: operator / operator123')
    print(f'  Viewer:   viewer / viewer123')
    print(f'  {"-" * 40}')
    print()

    # ── Open browser ──
    open_browser()

    # ── Start IO threads ──
    inp_thread = threading.Thread(target=input_thread, daemon=True)
    out_thread = threading.Thread(target=output_thread, daemon=True)
    inp_thread.start()
    out_thread.start()

    # ── Main loop ──
    try:
        while running:
            time.sleep(0.5)
    except KeyboardInterrupt:
        print('\n  [INTERRUPT] User interrupted')
    finally:
        running = False
        stop_backend()
        print()
        print('  [OK] Safe exit')
        time.sleep(1)


if __name__ == '__main__':
    main()
