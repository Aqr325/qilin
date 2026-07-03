"""Start the backend as a detached process using subprocess DETACHED_PROCESS."""
import subprocess
import sys
import os

backend_dir = os.path.dirname(os.path.abspath(__file__))
python_exe = sys.executable
dev_script = os.path.join(backend_dir, "dev_run.py")
log_file = os.path.join(backend_dir, "uvicorn.log")
err_file = os.path.join(backend_dir, "uvicorn.err")

log_fh = open(log_file, "w", encoding="utf-8")
err_fh = open(err_file, "w", encoding="utf-8")

proc = subprocess.Popen(
    [python_exe, dev_script],
    cwd=backend_dir,
    stdout=log_fh,
    stderr=err_fh,
    creationflags=subprocess.DETACHED_PROCESS,
    env={**os.environ, "PYTHONIOENCODING": "utf-8"}
)

pid_file = os.path.join(backend_dir, "backend.pid")
with open(pid_file, "w") as f:
    f.write(str(proc.pid))

print(f"Started backend server (PID: {proc.pid})")
print(f"Log: {log_file}")
print(f"PID file: {pid_file}")
