"""
Security event collector for the Agent.

Four monitors:
  1. Process creation monitor  — reads /proc periodically
  2. Network connection monitor — reads /proc/net/tcp + /proc/net/udp
  3. File change monitor       — pyinotify on critical paths
  4. Log anomaly monitor       — tail + regex on /var/log/secure etc.

All monitors are optional and can be disabled via config.
"""

import asyncio
import os
import re
import time
from pathlib import Path
from typing import Any, Callable, Coroutine, Dict, List, Optional, Set

from src.logger import get_logger

logger = get_logger("collector")

# ── Known whitelist process prefixes (Kylin OS) ───────────────────────────
_KYLIN_WHITELIST_PREFIXES = ("kylin-", "kysec-", "ukui-")

# ── High-risk command patterns (for log monitor) ──────────────────────────
_SSH_BRUTE_FORCE_RE = re.compile(
    r"Failed password for .* from (\S+) port \d+ ssh2"
)
_SUDO_ESCALATION_RE = re.compile(
    r"sudo:\s+\S+\s+:\s+command not allowed|"
    r"sudo:\s+\S+\s+:\s+TTY unknown"
)
_USER_CREATE_RE = re.compile(
    r"useradd|userdel|groupadd|passwd:\s+password changed"
)
_SELINUX_ALERT_RE = re.compile(
    r"SELinux:\s+(denied|avc:)"
)

# ── Kylin-specific security patterns ─────────────────────────────────────
_KYSEC_DENIAL_RE = re.compile(
    r"kysec:\s+denied|kysec:\s+avc:|kysec_audit:.*denied"
)
_KYLIN_AUDIT_CMD_RE = re.compile(
    r"kylin-audit:.*(command=|exe=).*"
)
_KYLIN_PKG_CHANGE_RE = re.compile(
    r"Installed|Updated|Erased.*\.(rpm|deb)"
)
_KYLIN_SECURITY_CONF_RE = re.compile(
    r"/etc/kysec|/etc/kylin/|kylin-security-config"
)
_KYLIN_SERVICE_CRASH_RE = re.compile(
    r"kysec|kylin-.*(failed|crash|error|oom)"
)


class ProcessMonitor:
    """Periodic process table scanner (reads /proc)."""

    def __init__(self, scan_interval: int = 10):
        self._interval = scan_interval
        self._known_pids: Set[int] = set()

    def _scan_proc(self) -> List[Dict[str, Any]]:
        """Read /proc and return list of new processes since last scan."""
        new_procs = []
        current_pids = set()

        try:
            for entry in os.listdir("/proc"):
                if not entry.isdigit():
                    continue
                pid = int(entry)
                current_pids.add(pid)

                if pid in self._known_pids:
                    continue

                # Collect process info
                info = self._read_proc_info(pid)
                if info:
                    new_procs.append(info)

            self._known_pids = current_pids
        except PermissionError:
            logger.warning("Permission denied reading /proc (try running as root)")

        return new_procs

    @staticmethod
    def _read_proc_info(pid: int) -> Optional[Dict[str, Any]]:
        """Read /proc/<pid>/status and /proc/<pid>/cmdline."""
        try:
            status_path = f"/proc/{pid}/status"
            cmdline_path = f"/proc/{pid}/cmdline"

            if not os.path.exists(status_path):
                return None

            uid = None
            name = ""
            ppid = None
            with open(status_path, "r") as fh:
                for line in fh:
                    if line.startswith("Name:"):
                        name = line.split(":", 1)[1].strip()
                    elif line.startswith("Uid:"):
                        uid = int(line.split()[1])
                    elif line.startswith("PPid:"):
                        ppid = int(line.split()[1])

            # Skip Kylin whitelist processes
            if name.startswith(_KYLIN_WHITELIST_PREFIXES):
                return None

            cmdline = ""
            if os.path.exists(cmdline_path):
                try:
                    with open(cmdline_path, "rb") as fh:
                        raw = fh.read()
                    cmdline = raw.replace(b"\x00", b" ").decode("utf-8", errors="replace").strip()
                except Exception:
                    pass

            return {
                "pid": pid,
                "ppid": ppid,
                "name": name,
                "cmdline": cmdline,
                "uid": uid,
                "timestamp": time.time(),
            }
        except (IOError, OSError, ValueError):
            return None

    def get_all_procs(self) -> List[int]:
        """Return current PIDs for baseline."""
        pids = []
        try:
            for entry in os.listdir("/proc"):
                if entry.isdigit():
                    pids.append(int(entry))
        except PermissionError:
            pass
        self._known_pids = set(pids)
        return pids

    async def run(self, on_event: Callable[..., Coroutine]):
        """Run periodic process scan."""
        # Establish baseline
        self.get_all_procs()
        logger.info("Process monitor started (interval=%ds)", self._interval)

        while True:
            try:
                new_procs = self._scan_proc()
                if new_procs:
                    await on_event({
                        "type": "process_create",
                        "events": new_procs,
                    })
                await asyncio.sleep(self._interval)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.exception("Process scan error: %s", exc)
                await asyncio.sleep(self._interval)


class NetworkMonitor:
    """Periodic network connection scanner (reads /proc/net/tcp and udp)."""

    # TCP states as defined in /proc/net/tcp
    _TCP_STATES = {
        "01": "ESTABLISHED", "02": "SYN_SENT", "03": "SYN_RECV",
        "04": "FIN_WAIT1", "05": "FIN_WAIT2", "06": "TIME_WAIT",
        "07": "CLOSE", "08": "CLOSE_WAIT", "09": "LAST_ACK",
        "0A": "LISTEN", "0B": "CLOSING",
    }

    def __init__(self, scan_interval: int = 30):
        self._interval = scan_interval
        self._known_conns: Set[str] = set()

    def _parse_proc_net(self, proto: str) -> List[Dict]:
        """Read /proc/net/{tcp,udp} and return parsed connections."""
        path = f"/proc/net/{proto}"
        connections = []
        try:
            with open(path, "r") as fh:
                lines = fh.readlines()
        except (IOError, OSError):
            return connections

        for line in lines[1:]:  # Skip header
            parts = line.strip().split()
            if len(parts) < 10:
                continue

            try:
                local_addr, local_port = parts[1].split(":")
                remote_addr, remote_port = parts[2].split(":")

                local_ip = ".".join(
                    str(int(local_addr[i:i + 2], 16))
                    for i in range(0, min(8, len(local_addr)), 2)
                )
                remote_ip = ".".join(
                    str(int(remote_addr[i:i + 2], 16))
                    for i in range(0, min(8, len(remote_addr)), 2)
                )

                state = self._TCP_STATES.get(parts[3], "UNKNOWN")
                # PID from /proc/net/tcp is in the last column after inode
                # Format: ... inode uid fd sk ... -> uid uid inode
                uid_str = parts[7] if len(parts) > 7 else "0"
                inode_str = parts[9] if len(parts) > 9 else "0"

                conn_key = f"{proto}:{local_ip}:{local_port}-{remote_ip}:{remote_port}"
                connections.append({
                    "proto": proto.upper(),
                    "local": f"{local_ip}:{int(local_port, 16)}",
                    "remote": f"{remote_ip}:{int(remote_port, 16)}",
                    "state": state,
                    "uid": int(uid_str),
                    "inode": inode_str,
                    "conn_key": conn_key,
                })
            except (ValueError, IndexError):
                continue

        return connections

    def scan(self) -> List[Dict]:
        """Scan both TCP and UDP connections; return new (previously unseen) ones."""
        current_keys: Set[str] = set()
        all_conns = []

        for proto in ("tcp", "udp"):
            conns = self._parse_proc_net(proto)
            for conn in conns:
                current_keys.add(conn["conn_key"])
                if conn["conn_key"] not in self._known_conns:
                    all_conns.append(conn)

        self._known_conns = current_keys
        return all_conns

    async def run(self, on_event: Callable[..., Coroutine]):
        """Run periodic network scan."""
        # Baseline
        self.scan()
        logger.info("Network monitor started (interval=%ds)", self._interval)

        while True:
            try:
                new_conns = self.scan()
                if new_conns:
                    await on_event({
                        "type": "network_connect",
                        "events": new_conns,
                    })
                await asyncio.sleep(self._interval)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.exception("Network scan error: %s", exc)
                await asyncio.sleep(self._interval)


class FileMonitor:
    """File change monitor using pyinotify.

    Watches critical configuration files for modifications, creation,
    deletion, and attribute changes.
    """

    def __init__(self, watch_paths: List[str]):
        self._paths = watch_paths
        self._running = False

    async def run(self, on_event: Callable[..., Coroutine]):
        """Start pyinotify watch loop. Falls back gracefully if not on Linux."""
        try:
            import pyinotify
        except ImportError:
            logger.warning("pyinotify not available; file monitor disabled")
            return

        self._running = True
        logger.info("File monitor started, watching %d paths", len(self._paths))

        mask = (
            pyinotify.IN_MODIFY |
            pyinotify.IN_CREATE |
            pyinotify.IN_DELETE |
            pyinotify.IN_ATTRIB
        )

        wm = pyinotify.WatchManager()

        for path in self._paths:
            p = Path(path)
            if p.exists():
                wm.add_watch(str(p), mask)
                logger.debug("Watching: %s", path)
            else:
                logger.warning("Watch path does not exist: %s", path)

        loop = asyncio.get_event_loop()

        class EventHandler(pyinotify.ProcessEvent):
            def my_init(inner_self, callback):
                inner_self.callback = callback

            def process_IN_MODIFY(inner_self, event):
                asyncio.run_coroutine_threadsafe(
                    callback({"type": "file_modify", "path": event.pathname, "mask": event.maskname}),
                    loop,
                )

            def process_IN_CREATE(inner_self, event):
                asyncio.run_coroutine_threadsafe(
                    callback({"type": "file_create", "path": event.pathname, "mask": event.maskname}),
                    loop,
                )

            def process_IN_DELETE(inner_self, event):
                asyncio.run_coroutine_threadsafe(
                    callback({"type": "file_delete", "path": event.pathname, "mask": event.maskname}),
                    loop,
                )

            def process_IN_ATTRIB(inner_self, event):
                asyncio.run_coroutine_threadsafe(
                    callback({"type": "file_attrib", "path": event.pathname, "mask": event.maskname}),
                    loop,
                )

        handler = EventHandler(callback=on_event)
        notifier = pyinotify.AsyncioNotifier(wm, loop, callback=handler)

        try:
            while self._running:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass
        finally:
            notifier.stop()

    def stop(self):
        self._running = False


class LogMonitor:
    """Log anomaly monitor — tail + regex on security log files.

    Reads log files line by line (like tail -f), matches against known
    anomalous patterns, and emits events when match counts exceed threshold.
    """

    # Pattern groups: (name, regex, threshold_per_minute)
    PATTERNS = [
        ("ssh_brute_force", _SSH_BRUTE_FORCE_RE, 10),
        ("sudo_escalation", _SUDO_ESCALATION_RE, 1),
        ("user_management", _USER_CREATE_RE, 1),
        ("selinux_alert", _SELINUX_ALERT_RE, 1),
        # Kylin-specific patterns
        ("kysec_denial", _KYSEC_DENIAL_RE, 1),
        ("kylin_audit_cmd", _KYLIN_AUDIT_CMD_RE, 10),
        ("kylin_pkg_change", _KYLIN_PKG_CHANGE_RE, 5),
        ("kylin_security_conf", _KYLIN_SECURITY_CONF_RE, 1),
        ("kylin_service_crash", _KYLIN_SERVICE_CRASH_RE, 1),
    ]

    def __init__(self, log_files: List[str]):
        self._log_files = [p for p in log_files if Path(p).exists()]
        self._positions: Dict[str, int] = {}  # file -> last read position
        self._match_counts: Dict[str, Dict[str, int]] = {}  # file -> pattern -> count
        self._last_reset = time.time()

    def _tail_file(self, path: str) -> List[str]:
        """Read new lines from a log file since last read."""
        try:
            with open(path, "r", errors="replace") as fh:
                fh.seek(self._positions.get(path, 0))
                lines = fh.readlines()
                self._positions[path] = fh.tell()
            return lines
        except (IOError, OSError) as exc:
            logger.debug("Cannot read %s: %s", path, exc)
            return []

    def _check_thresholds(self) -> List[Dict]:
        """Check if any pattern has exceeded its threshold in the current window."""
        events = []
        now = time.time()
        elapsed = now - self._last_reset

        if elapsed < 60:
            return events  # Not yet a full minute

        for file_path, patterns in self._match_counts.items():
            for pattern_name, count in patterns.items():
                if count == 0:
                    continue
                # Find threshold
                threshold = 0
                for pname, _, thr in self.PATTERNS:
                    if pname == pattern_name:
                        threshold = thr
                        break
                if count >= threshold:
                    events.append({
                        "type": "log_anomaly",
                        "pattern": pattern_name,
                        "source": file_path,
                        "count": count,
                        "threshold": threshold,
                        "timestamp": now,
                    })

        # Reset counters
        self._match_counts.clear()
        self._last_reset = now
        return events

    def scan(self) -> List[Dict]:
        """Scan all log files and return matched anomaly events."""
        events = []

        for file_path in self._log_files:
            lines = self._tail_file(file_path)
            if not lines:
                continue

            if file_path not in self._match_counts:
                self._match_counts[file_path] = {}

            for line in lines:
                for pattern_name, pattern_re, _ in self.PATTERNS:
                    if pattern_re.search(line):
                        self._match_counts[file_path][pattern_name] = \
                            self._match_counts[file_path].get(pattern_name, 0) + 1

        # Check thresholds
        events.extend(self._check_thresholds())
        return events

    async def run(self, on_event: Callable[..., Coroutine]):
        """Run periodic log scan."""
        if not self._log_files:
            logger.warning("No log files found; log monitor disabled")
            return

        logger.info("Log monitor started, watching %d files", len(self._log_files))
        for f in self._log_files:
            logger.debug("  Watching: %s", f)

        try:
            while True:
                events = self.scan()
                if events:
                    await on_event({"type": "log_anomaly", "events": events})
                await asyncio.sleep(10)
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            logger.exception("Log monitor error: %s", exc)


class SecurityCollector:
    """Orchestrates all four security monitors."""

    def __init__(self, config, on_event: Callable[..., Coroutine]):
        self._config = config
        self._on_event = on_event
        self._monitors: List[asyncio.Task] = []
        self._enabled = config.get("collector", "enabled", default=True)

    async def start(self):
        """Start all enabled monitors."""
        if not self._enabled:
            logger.info("Security collector disabled by config")
            return

        c = self._config.get("collector", default={})
        logger.info("Starting security collectors...")

        tasks = []

        if c.get("process_monitor", True):
            interval = c.get("proc_scan_interval", 10)
            pm = ProcessMonitor(interval)
            tasks.append(asyncio.create_task(pm.run(self._on_event)))

        if c.get("network_monitor", True):
            interval = c.get("net_scan_interval", 30)
            nm = NetworkMonitor(interval)
            tasks.append(asyncio.create_task(nm.run(self._on_event)))

        if c.get("file_monitor", True):
            paths = c.get("file_watch_paths", [])
            if paths:
                fm = FileMonitor(paths)
                tasks.append(asyncio.create_task(fm.run(self._on_event)))

        if c.get("log_monitor", True):
            log_files = c.get("log_files", [])
            if log_files:
                lm = LogMonitor(log_files)
                tasks.append(asyncio.create_task(lm.run(self._on_event)))

        self._monitors = tasks
        logger.info("Started %d security monitor tasks", len(tasks))

    async def stop(self):
        """Stop all monitors."""
        for t in self._monitors:
            t.cancel()
        if self._monitors:
            await asyncio.gather(*self._monitors, return_exceptions=True)
        self._monitors.clear()
