"""Local system status endpoint - uses only Python standard library.

Windows: uses ctypes kernel32 calls for disk/uptime, and simple powershell for CPU/memory.
Linux: uses /proc filesystem.
"""

import ctypes
import logging
import platform
import shutil
import socket
import subprocess
import time
from pathlib import Path

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/system", tags=["系统状态"])

# ── Windows kernel32 helpers ──────────────────────────────────────────────
kernel32 = ctypes.windll.kernel32 if platform.system() == "Windows" else None


def _get_uptime() -> int:
    """System uptime in seconds."""
    try:
        if kernel32:
            return int(kernel32.GetTickCount64() // 1000)
        return int(float(Path("/proc/uptime").read_text().split()[0]))
    except Exception:
        return 0


def _get_disks() -> list:
    """Disk usage info."""
    disks = []
    try:
        if kernel32:
            n = kernel32.GetLogicalDriveStringsW(0, None)
            if n > 0:
                buf = ctypes.create_unicode_buffer(n + 1)
                kernel32.GetLogicalDriveStringsW(n, buf)
                for drive in buf.value.split("\x00"):
                    if not drive or not drive.endswith(":\\"):
                        continue
                    lp_total = ctypes.c_ulonglong()
                    lp_free = ctypes.c_ulonglong()
                    if kernel32.GetDiskFreeSpaceExW(drive, None, ctypes.byref(lp_total), ctypes.byref(lp_free)):
                        total = lp_total.value
                        free = lp_free.value
                        used = total - free
                        pct = round(used / total * 100, 1) if total > 0 else 0
                        disks.append({
                            "mount": drive,
                            "total_gb": round(total / (1024 ** 3), 1),
                            "used_gb": round(used / (1024 ** 3), 1),
                            "free_gb": round(free / (1024 ** 3), 1),
                            "percent": pct,
                        })
        else:
            for line in Path("/proc/mounts").read_text().splitlines():
                parts = line.split()
                if len(parts) >= 2:
                    mp = parts[1]
                    try:
                        st = Path(mp).statvfs()
                        total = st.f_blocks * st.f_frsize
                        free = st.f_bfree * st.f_frsize
                        used = total - free
                        pct = round(used / total * 100, 1) if total > 0 else 0
                        disks.append({
                            "mount": mp,
                            "total_gb": round(total / (1024 ** 3), 1),
                            "used_gb": round(used / (1024 ** 3), 1),
                            "free_gb": round(free / (1024 ** 3), 1),
                            "percent": pct,
                        })
                    except Exception:
                        continue
    except Exception:
        pass
    return disks


def _get_cpu_percent() -> float:
    """CPU percent. Linux from /proc/stat; Windows from wmic."""
    try:
        if kernel32:
            r = subprocess.run(
                ["wmic", "cpu", "get", "LoadPercentage", "/format:list"],
                capture_output=True, text=True, timeout=5,
            )
            if r.returncode == 0:
                for line in r.stdout.splitlines():
                    if line.startswith("LoadPercentage="):
                        return float(line.split("=")[1])
            return 0.0
        else:
            lines = Path("/proc/stat").read_text().splitlines()
            if lines and lines[0].startswith("cpu "):
                vals = list(map(int, lines[0].split()[1:]))
                total = sum(vals)
                idle = vals[3] if len(vals) > 3 else 0
                return round((total - idle) / total * 100, 1) if total > 0 else 0
            return 0.0
    except Exception:
        return 0.0


def _get_cpu_count() -> int:
    try:
        return shutil.cpu_count() or 1
    except Exception:
        return 1


def _get_memory() -> dict:
    """Memory info. Linux from /proc/meminfo; Windows from GetPerformanceInfo."""
    try:
        if kernel32:
            # Use GetPerformanceInfo (available on Windows 8+)
            # Structure: PERFORMANCE_INFORMATION
            class PERFORM_INFO(ctypes.Structure):
                _fields_ = [
                    ("cb", ctypes.c_ulong),
                    ("PageSize", ctypes.c_size_t),
                    ("PhysicalTotal", ctypes.c_size_t),
                    ("PhysicalAvailable", ctypes.c_size_t),
                    ("SystemCache", ctypes.c_size_t),
                    ("KernelTotal", ctypes.c_size_t),
                    ("KernelPaged", ctypes.c_size_t),
                    ("KernelNonPaged", ctypes.c_size_t),
                    ("SystemTotal", ctypes.c_size_t),
                    ("SystemPaged", ctypes.c_size_t),
                    ("SystemNonPaged", ctypes.c_size_t),
                    ("HandleCount", ctypes.c_ulong),
                    ("ProcessCount", ctypes.c_ulong),
                    ("ThreadCount", ctypes.c_ulong),
                ]

            info = PERFORM_INFO()
            info.cb = ctypes.sizeof(PERFORM_INFO)
            # Load NtQuerySystemInformation from ntdll
            ntdll = ctypes.WinDLL("ntdll", use_last_error=True)
            status = ntdll.NtQuerySystemInformation(2, ctypes.byref(info), ctypes.sizeof(info), None)
            if status == 0:
                total = info.PhysicalTotal
                free = info.PhysicalAvailable
                used = total - free
                pct = round(used / total * 100, 1) if total > 0 else 0
                return {"total": total, "used": used, "percent": pct}

            # Fallback: powershell one-liner
            r = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "$os=Get-CimInstance Win32_OperatingSystem;"
                 "echo $os.TotalVisibleMemorySize, $os.FreePhysicalMemory"],
                capture_output=True, text=True, timeout=5,
            )
            if r.returncode == 0:
                parts = r.stdout.strip().split()
                if len(parts) >= 2:
                    total = int(parts[0]) * 1024
                    free = int(parts[1]) * 1024
                    used = total - free
                    pct = round(used / total * 100, 1) if total > 0 else 0
                    return {"total": total, "used": used, "percent": pct}
            return {"total": 0, "used": 0, "percent": 0}
        else:
            info = {}
            for line in Path("/proc/meminfo").read_text().splitlines():
                parts = line.split()
                if len(parts) >= 2:
                    info[parts[0].rstrip(":")] = int(parts[1]) * 1024
            total = info.get("MemTotal", 0)
            avail = info.get("MemAvailable", info.get("MemFree", 0))
            used = total - avail
            pct = round(used / total * 100, 1) if total > 0 else 0
            return {"total": total, "used": used, "percent": pct}
    except Exception:
        return {"total": 0, "used": 0, "percent": 0}


@router.get("/local-status")
async def get_local_status(
    current_user: dict = Depends(get_current_user),
):
    """管理本机（运行此后台的机器）的系统状态。"""
    mem = _get_memory()
    return {
        "hostname": socket.gethostname(),
        "os": f"{platform.system()} {platform.release()}",
        "uptime_seconds": _get_uptime(),
        "cpu_percent": _get_cpu_percent(),
        "cpu_count": _get_cpu_count(),
        "memory": {
            "total_mb": round(mem["total"] / (1024 * 1024), 1),
            "used_mb": round(mem["used"] / (1024 * 1024), 1),
            "percent": mem["percent"],
        },
        "disks": _get_disks(),
        "backend_version": settings.VERSION,
    }
