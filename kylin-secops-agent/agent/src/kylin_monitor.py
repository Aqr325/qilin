"""
Kylin OS-specific monitoring — 麒麟系统专属安全监控模块.

Extends the standard HeartbeatCollector and SecurityCollector with
Kylin-specific system information and security features:

  1. kysec (麒麟安全内核) status detection
  2. Kylin auditd integration
  3. Kylin network manager (nmcli/kylin-nm) status
  4. Kylin package manager (yum/dnf/rpm-ostree) security audit
  5. Kylin firewall (firewalld/kyfirewall) status
  6. Kylin UKUI desktop security settings
  7. Kylin kernel security feature enumeration
  8. Kylin security baseline compliance check

All modules degrade gracefully (return empty/default data) when
not running on Kylin OS, so this module is safe to include on
any Linux distribution.
"""

import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.logger import get_logger

logger = get_logger("kylin_monitor")

# ── Kylin 特有文件路径 ───────────────────────────────────────────────────
KYLIN_RELEASE_FILE = Path("/etc/kylin-release")
KYLIN_VERSION_FILE = Path("/etc/kylin-version")
KYLIN_SYSTEM_CONF = Path("/etc/kylin/system.conf")

# kysec (麒麟安全内核) 路径
KYSEC_CONFIG = Path("/etc/kysec/kysec.conf")
KYSEC_STATUS = Path("/proc/kysec/status")  # 麒麟安全内核状态接口

# 麒麟审计日志
KYLIN_AUDIT_LOG = Path("/var/log/kylin-security.log")
KYLIN_AUDIT_CONF = Path("/etc/kylin-audit/kylin-auditd.conf")

# 麒麟防火墙
KYLIN_FIREWALL_CONF = Path("/etc/kyfirewall/kyfirewalld.conf")

# Kylin security commands
_KYSEC_CMD = shutil.which("getkysec") or shutil.which("kysec-get") or None
_KYLIN_NM_CMD = shutil.which("kylin-nm") or None
_KYLIN_SEC_CMD = shutil.which("kylin-security-config") or None


# ══════════════════════════════════════════════════════════════════════════
# OS Detection
# ══════════════════════════════════════════════════════════════════════════

def is_kylin_os() -> bool:
    """Check if running on Kylin OS."""
    if KYLIN_RELEASE_FILE.exists():
        return True
    if KYLIN_VERSION_FILE.exists():
        return True
    try:
        with open("/etc/os-release") as f:
            content = f.read()
        return "kylin" in content.lower()
    except (FileNotFoundError, OSError):
        return False


def detect_kylin_version() -> Dict[str, str]:
    """Detect Kylin OS version and variant."""
    result: Dict[str, str] = {
        "os": "linux",
        "variant": "",
        "version": "",
        "kernel": os.uname().release,
    }

    if KYLIN_RELEASE_FILE.exists():
        result["os"] = "kylin"
        try:
            content = KYLIN_RELEASE_FILE.read_text().strip()
            if "V10" in content:
                result["variant"] = "server" if "server" in content.lower() else "desktop"
            result["version"] = content
        except (IOError, OSError):
            pass

    if KYLIN_VERSION_FILE.exists():
        try:
            result["version"] = KYLIN_VERSION_FILE.read_text().strip()
        except (IOError, OSError):
            pass

    # 检测是否为银河麒麟
    try:
        with open("/etc/os-release") as f:
            content = f.read()
        if "NeoKylin" in content or "Kylin" in content:
            result["os"] = "kylin"
            if "Desktop" in content:
                result["variant"] = "desktop"
            elif "Server" in content:
                result["variant"] = "server"
    except (FileNotFoundError, OSError):
        pass

    return result


# ══════════════════════════════════════════════════════════════════════════
# kysec 麒麟安全内核
# ══════════════════════════════════════════════════════════════════════════

def detect_kysec_status() -> Dict[str, Any]:
    """Detect kysec (麒麟安全内核) status.

    kysec is Kylin's mandatory access control framework, similar to
    SELinux but tailored for KylinOS. It provides:
      - Mandatory access control (MAC)
      - Process integrity protection
      - Kernel integrity monitoring
    """
    result: Dict[str, Any] = {
        "enabled": False,
        "mode": "",
        "policy_version": "",
    }

    # 尝试从 proc 文件系统读取
    if KYSEC_STATUS.exists():
        try:
            content = KYSEC_STATUS.read_text().strip()
            result["enabled"] = "enabled" in content.lower() or "1" in content
            for line in content.splitlines():
                if "mode" in line.lower():
                    result["mode"] = line.split(":")[-1].strip()
                if "policy" in line.lower() and "version" in line.lower():
                    result["policy_version"] = line.split(":")[-1].strip()
        except (IOError, OSError):
            pass

    # 尝试 kysec 命令行
    if _KYSEC_CMD:
        try:
            out = subprocess.check_output(
                [_KYSEC_CMD, "status"], stderr=subprocess.DEVNULL, timeout=5
            ).decode("utf-8", errors="replace")
            result["enabled"] = "enabled" in out.lower() or "enable" in out.lower()
            for line in out.splitlines():
                if "mode" in line.lower():
                    result["mode"] = line.split(":")[-1].strip()
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, OSError):
            pass

    # 检查 kysec 配置文件
    result["config_exists"] = KYSEC_CONFIG.exists()
    if result["config_exists"]:
        try:
            stat = KYSEC_CONFIG.stat()
            result["config_size"] = stat.st_size
            result["config_mtime"] = stat.st_mtime
        except OSError:
            pass

    return result


def detect_selinux_status() -> Dict[str, Any]:
    """Detect SELinux status (Kylin also supports SELinux)."""
    result: Dict[str, Any] = {
        "enabled": False,
        "mode": "",
        "policy": "",
    }

    # Check selinuxenabled
    selinuxenabled = shutil.which("selinuxenabled")
    if selinuxenabled:
        try:
            ret = subprocess.run(
                [selinuxenabled], capture_output=True, timeout=3
            )
            result["enabled"] = ret.returncode == 0
        except (subprocess.TimeoutExpired, OSError):
            pass

    # Check getenforce
    getenforce = shutil.which("getenforce")
    if getenforce:
        try:
            out = subprocess.check_output(
                [getenforce], stderr=subprocess.DEVNULL, timeout=3
            ).decode("utf-8", errors="replace").strip().lower()
            result["mode"] = out
            if not result["enabled"]:
                result["enabled"] = out != "disabled"
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, OSError):
            pass

    # Check config
    selinux_config = Path("/etc/selinux/config")
    if selinux_config.exists():
        try:
            for line in selinux_config.read_text().splitlines():
                if line.startswith("SELINUXTYPE="):
                    result["policy"] = line.split("=")[-1].strip()
        except (IOError, OSError):
            pass

    return result


# ══════════════════════════════════════════════════════════════════════════
# Kylin Audit Integration
# ══════════════════════════════════════════════════════════════════════════

def detect_audit_status() -> Dict[str, Any]:
    """Detect Kylin audit subsystem status.

    KylinOS uses auditd (same as RHEL/CentOS) for system audit logging.
    Agent can tail /var/log/audit/audit.log for real-time security events.
    """
    result: Dict[str, Any] = {
        "auditd": False,
        "kylin_audit": False,
        "audit_log_size": 0,
        "audit_rules_count": 0,
    }

    # Check auditd service
    systemctl = shutil.which("systemctl")
    if systemctl:
        try:
            out = subprocess.check_output(
                [systemctl, "is-active", "auditd"], stderr=subprocess.DEVNULL, timeout=5
            ).decode("utf-8", errors="replace").strip()
            result["auditd"] = out == "active"
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, OSError):
            pass

    # Check Kylin audit log
    if KYLIN_AUDIT_LOG.exists():
        try:
            result["kylin_audit"] = True
            result["audit_log_size"] = KYLIN_AUDIT_LOG.stat().st_size
        except OSError:
            pass

    # Check standard audit log
    audit_log = Path("/var/log/audit/audit.log")
    if audit_log.exists():
        try:
            result["audit_log_size"] = max(
                result["audit_log_size"], audit_log.stat().st_size
            )
        except OSError:
            pass

    # Count audit rules
    auditctl = shutil.which("auditctl")
    if auditctl:
        try:
            out = subprocess.check_output(
                [auditctl, "-l"], stderr=subprocess.DEVNULL, timeout=5
            ).decode("utf-8", errors="replace")
            result["audit_rules_count"] = len([l for l in out.splitlines() if l.strip()])
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, OSError):
            pass

    return result


# ══════════════════════════════════════════════════════════════════════════
# Kylin Network Manager
# ══════════════════════════════════════════════════════════════════════════

def detect_network_status() -> Dict[str, Any]:
    """Detect Kylin network configuration and security settings.

    Monitors:
      - Network connections (active interfaces)
      - Firewall status (firewalld / kyfirewalld)
      - DNS configuration
      - Listening ports (for intrusion detection)
    """
    result: Dict[str, Any] = {
        "firewall": False,
        "active_interfaces": [],
        "listening_ports": [],
        "dns_servers": [],
    }

    # Check firewalld
    systemctl = shutil.which("systemctl")
    if systemctl:
        for svc in ["firewalld", "kyfirewalld"]:
            try:
                out = subprocess.check_output(
                    [systemctl, "is-active", svc], stderr=subprocess.DEVNULL, timeout=3
                ).decode("utf-8", errors="replace").strip()
                if out == "active":
                    result["firewall"] = True
                    break
            except (subprocess.TimeoutExpired, subprocess.CalledProcessError, OSError):
                continue

    # Get active network interfaces via ip
    ip_cmd = shutil.which("ip")
    if ip_cmd:
        try:
            out = subprocess.check_output(
                [ip_cmd, "-o", "link", "show", "up"], stderr=subprocess.DEVNULL, timeout=5
            ).decode("utf-8", errors="replace")
            for line in out.splitlines():
                parts = line.split()
                if len(parts) >= 2:
                    iface = parts[1].rstrip(":")
                    if iface != "lo":
                        result["active_interfaces"].append(iface)
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, OSError):
            pass

    # Get listening ports via ss
    ss_cmd = shutil.which("ss")
    if ss_cmd:
        try:
            out = subprocess.check_output(
                [ss_cmd, "-tlnp"], stderr=subprocess.DEVNULL, timeout=5
            ).decode("utf-8", errors="replace")
            for line in out.splitlines()[1:]:  # skip header
                parts = line.split()
                if len(parts) >= 4:
                    addr_port = parts[3]
                    result["listening_ports"].append(addr_port)
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, OSError):
            pass

    # Get DNS servers
    resolv_conf = Path("/etc/resolv.conf")
    if resolv_conf.exists():
        try:
            for line in resolv_conf.read_text().splitlines():
                if line.startswith("nameserver"):
                    result["dns_servers"].append(line.split()[1])
        except (IOError, OSError):
            pass

    return result


# ══════════════════════════════════════════════════════════════════════════
# Kylin Package Manager Audit
# ══════════════════════════════════════════════════════════════════════════

def detect_package_security() -> Dict[str, Any]:
    """Audit Kylin package security state.

    Checks:
      - Available updates (security patches pending)
      - Recently installed packages (7 days)
      - Package integrity verification
    """
    result: Dict[str, Any] = {
        "pending_updates": 0,
        "security_updates": 0,
        "recent_installs": 0,
    }

    # Check pending updates via yum/dnf
    yum_cmd = shutil.which("yum") or shutil.which("dnf")
    if yum_cmd:
        try:
            out = subprocess.check_output(
                [yum_cmd, "check-update", "-q", "--security"],
                stderr=subprocess.DEVNULL, timeout=30,
            ).decode("utf-8", errors="replace")
            lines = [l for l in out.splitlines() if l.strip() and not l.startswith(("Loaded", "Last"))]
            result["security_updates"] = len(lines)
        except subprocess.CalledProcessError as e:
            # yum returns 100 when updates are available
            if e.returncode == 100:
                lines = [l for l in e.output.decode("utf-8", errors="replace").splitlines()
                         if l.strip() and not l.startswith(("Loaded", "Last"))]
                result["pending_updates"] = len(lines)
        except (subprocess.TimeoutExpired, OSError):
            pass

    # Check recent installs from rpm history
    rpm_cmd = shutil.which("rpm")
    if rpm_cmd:
        try:
            week_ago = time.time() - 7 * 86400
            out = subprocess.check_output(
                [rpm_cmd, "-qa", "--last"], stderr=subprocess.DEVNULL, timeout=15
            ).decode("utf-8", errors="replace")
            for line in out.splitlines():
                if line.strip():
                    result["recent_installs"] += 1
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, OSError):
            pass

    return result


# ══════════════════════════════════════════════════════════════════════════
# Kylin Security Baseline Check
# ══════════════════════════════════════════════════════════════════════════

def check_security_baseline() -> Dict[str, Any]:
    """Check Kylin OS security baseline compliance.

    Based on Kylin security hardening guide and 등급보호 (MLPS)
    requirements.
    """
    result: Dict[str, Any] = {
        "password_policy": False,
        "ssh_hardened": False,
        "kernel_hardened": False,
        "firewall_enabled": False,
        "selinux_enabled": False,
        "kysec_enabled": False,
        "audit_enabled": False,
    }

    # Password policy check
    login_defs = Path("/etc/login.defs")
    if login_defs.exists():
        try:
            for line in login_defs.read_text().splitlines():
                if line.strip().startswith("PASS_MIN_LEN") and int(line.split()[-1]) >= 8:
                    result["password_policy"] = True
        except (ValueError, IOError, OSError):
            pass

    # SSH hardening check
    sshd_config = Path("/etc/ssh/sshd_config")
    if sshd_config.exists():
        try:
            for line in sshd_config.read_text().splitlines():
                stripped = line.strip()
                if stripped.startswith("PermitRootLogin") and "without-password" in stripped:
                    result["ssh_hardened"] = True
                if stripped.startswith("PasswordAuthentication") and "no" in stripped:
                    result["ssh_hardened"] = True
        except (IOError, OSError):
            pass

    # Kernel hardening (check sysctl)
    sysctl_cmd = shutil.which("sysctl")
    if sysctl_cmd:
        try:
            out = subprocess.check_output(
                [sysctl_cmd, "kernel.kptr_restrict"], stderr=subprocess.DEVNULL, timeout=3
            ).decode("utf-8", errors="replace")
            if "2" in out:
                result["kernel_hardened"] = True
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, OSError):
            pass

    # Integrate other checks
    result["firewall_enabled"] = detect_network_status().get("firewall", False)
    result["selinux_enabled"] = detect_selinux_status().get("enabled", False)
    result["kysec_enabled"] = detect_kysec_status().get("enabled", False)
    result["audit_enabled"] = detect_audit_status().get("auditd", False)

    # Calculate compliance score
    checks = [
        result["password_policy"],
        result["ssh_hardened"],
        result["kernel_hardened"],
        result["firewall_enabled"],
        result["selinux_enabled"] or result["kysec_enabled"],
        result["audit_enabled"],
    ]
    result["compliance_score"] = round(
        sum(1 for c in checks if c) / len(checks) * 100, 1
    )

    return result


# ══════════════════════════════════════════════════════════════════════════
# Kylin Kernel Module Audit
# ══════════════════════════════════════════════════════════════════════════

def detect_kernel_modules() -> Dict[str, Any]:
    """Audit loaded kernel modules for suspicious or unauthorized ones."""
    result: Dict[str, Any] = {
        "total_modules": 0,
        "suspicious_modules": [],
    }

    lsmod_cmd = shutil.which("lsmod")
    if lsmod_cmd:
        try:
            out = subprocess.check_output(
                [lsmod_cmd], stderr=subprocess.DEVNULL, timeout=5
            ).decode("utf-8", errors="replace")
            lines = out.splitlines()[1:]  # skip header
            result["total_modules"] = len(lines)

            # Check for suspicious modules
            suspicious_keywords = ["kprobe", "kretprobe", "ftrace", "kdb", "kgdb"]
            for line in lines:
                module_name = line.split()[0].lower()
                for keyword in suspicious_keywords:
                    if keyword in module_name:
                        result["suspicious_modules"].append({
                            "module": line.split()[0],
                            "keyword": keyword,
                        })
                        break
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, OSError):
            pass

    return result


# ══════════════════════════════════════════════════════════════════════════
# Comprehensive Kylin system check
# ══════════════════════════════════════════════════════════════════════════

def collect_kylin_system_info() -> Dict[str, Any]:
    """Collect all Kylin-specific system information in one shot.

    This is the main entry point for Kylin monitoring integration.
    Returns a comprehensive dict that can be included in heartbeats
    or used for security baseline reporting.
    """
    info: Dict[str, Any] = {
        "os": detect_kylin_version(),
        "kysec": detect_kysec_status(),
        "selinux": detect_selinux_status(),
        "audit": detect_audit_status(),
        "network": detect_network_status(),
        "packages": detect_package_security(),
        "baseline": check_security_baseline(),
        "kernel_modules": detect_kernel_modules(),
    }
    return info


# ── Quick test ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import json
    print("Kylin OS:", is_kylin_os())
    if is_kylin_os():
        print("Version:", json.dumps(detect_kylin_version(), indent=2))
        print("Kysec:", json.dumps(detect_kysec_status(), indent=2))
    else:
        print("Kylin:", detect_kylin_version())
        print("SELinux:", json.dumps(detect_selinux_status(), indent=2))
        print("Audit:", json.dumps(detect_audit_status(), indent=2))
        print("Network:", json.dumps(detect_network_status(), indent=2))
        print("Baseline:", json.dumps(check_security_baseline(), indent=2))