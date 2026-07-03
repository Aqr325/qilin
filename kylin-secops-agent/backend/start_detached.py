"""Start the backend server as a truly detached process (Windows)."""
import subprocess
import sys
import os

backend_dir = os.path.dirname(os.path.abspath(__file__))
python_exe = sys.executable

# Use DETACHED_PROCESS flag to create a process that survives this process
DETACHED_PROCESS = 0x00000008
CREATE_NEW_PROCESS_GROUP = 0x00000200
CREATE_NO_WINDOW = 0x08000000

proc = subprocess.Popen(
    [python_exe, "dev_run.py"],
    cwd=backend_dir,
    creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW,
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
    stdin=subprocess.DEVNULL,
    env={**os.environ, "PYTHONIOENCODING": "utf-8"}
)

print(f"Backend started with PID: {proc.pid}")
print(f"Check port 8000 after a few seconds...")

# Also write PID to a file for later cleanup
with open(os.path.join(backend_dir, "backend.pid"), "w") as f:
    f.write(str(proc.pid))

sys.exit(0)
