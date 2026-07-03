"""
SQLite local storage for the Agent.

Two tables:
  - policies: cached policy rules (YAML content, version, checksum)
  - audit_logs: offline audit log buffer (max 10000 records, FIFO eviction)

Thread-safe via sqlite3 WAL mode + single connection with lock.
"""

import json
import sqlite3
import threading
import time
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.logger import get_logger

logger = get_logger("db")


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS policies (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    version     INTEGER NOT NULL,
    content_yaml TEXT NOT NULL,
    checksum    TEXT NOT NULL,
    enabled     INTEGER NOT NULL DEFAULT 1,
    created_at  REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_id     TEXT,
    action      TEXT NOT NULL,
    detail      TEXT,
    result      TEXT,
    timestamp   REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_policies_version ON policies(version);
CREATE INDEX IF NOT EXISTS idx_audit_logs_ts   ON audit_logs(timestamp);
"""


class LocalDB:
    """SQLite-backed local store (thread-safe with single-writer lock)."""

    def __init__(self, db_path: Path):
        self._lock = threading.Lock()
        self._conn: Optional[sqlite3.Connection] = None
        self._db_path = db_path
        self._max_audit_logs = 10000

    # ═══════════════════════════════════════════════════════════════════
    # Lifecycle
    # ═══════════════════════════════════════════════════════════════════

    def open(self):
        """Open (or create) the database and apply schema."""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            self._conn = sqlite3.connect(
                str(self._db_path),
                timeout=5,
                check_same_thread=False,
            )
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
            self._conn.executescript(SCHEMA_SQL)
            self._conn.commit()
        logger.info("Local DB opened at %s", self._db_path)

    def close(self):
        with self._lock:
            if self._conn:
                self._conn.close()
                self._conn = None

    @property
    def is_open(self) -> bool:
        return self._conn is not None

    # ═══════════════════════════════════════════════════════════════════
    # Policy cache
    # ═══════════════════════════════════════════════════════════════════

    def get_current_policy(self) -> Optional[Dict[str, Any]]:
        """Return the latest enabled policy, or None."""
        with self._lock:
            cur = self._conn.execute(
                "SELECT version, content_yaml, checksum, enabled "
                "FROM policies ORDER BY version DESC LIMIT 1"
            )
            row = cur.fetchone()
        if row is None:
            return None
        return {
            "version": row[0],
            "content_yaml": row[1],
            "checksum": row[2],
            "enabled": bool(row[3]),
        }

    def save_policy(self, version: int, content_yaml: str, checksum: str):
        """Insert or replace a policy entry."""
        now = time.time()
        with self._lock:
            # Mark previous policies as disabled
            self._conn.execute("UPDATE policies SET enabled=0 WHERE enabled=1")
            self._conn.execute(
                "INSERT INTO policies (version, content_yaml, checksum, enabled, created_at) "
                "VALUES (?, ?, ?, 1, ?)",
                (version, content_yaml, checksum, now),
            )
            self._conn.commit()
        logger.info("Policy v%d saved (checksum=%s)", version, checksum)

    def get_policy_version_checksum(self) -> Tuple[Optional[int], Optional[str]]:
        """Return (version, checksum) of current active policy."""
        pol = self.get_current_policy()
        if pol:
            return pol["version"], pol["checksum"]
        return None, None

    # ═══════════════════════════════════════════════════════════════════
    # Audit log buffer
    # ═══════════════════════════════════════════════════════════════════

    def append_audit_log(self, action: str, rule_id: str = "",
                         detail: str = "", result: str = ""):
        """Append a single audit log entry. Evict oldest if at capacity."""
        now = time.time()
        with self._lock:
            # Count current rows
            (count,) = self._conn.execute("SELECT COUNT(*) FROM audit_logs").fetchone()
            if count >= self._max_audit_logs:
                # Delete oldest 10% to avoid thrashing
                delete_count = max(1, self._max_audit_logs // 10)
                self._conn.execute(
                    "DELETE FROM audit_logs WHERE id IN ("
                    "  SELECT id FROM audit_logs ORDER BY timestamp ASC LIMIT ?"
                    ")",
                    (delete_count,),
                )
            self._conn.execute(
                "INSERT INTO audit_logs (rule_id, action, detail, result, timestamp) "
                "VALUES (?, ?, ?, ?, ?)",
                (rule_id, action, detail, result, now),
            )
            self._conn.commit()

    def get_audit_logs(self, limit: int = 1000, offset: int = 0) -> List[Dict]:
        """Fetch buffered audit logs ordered by timestamp ascending."""
        with self._lock:
            cur = self._conn.execute(
                "SELECT rule_id, action, detail, result, timestamp "
                "FROM audit_logs ORDER BY timestamp ASC LIMIT ? OFFSET ?",
                (limit, offset),
            )
            rows = cur.fetchall()
        return [
            {
                "rule_id": r[0],
                "action": r[1],
                "detail": r[2],
                "result": r[3],
                "timestamp": r[4],
            }
            for r in rows
        ]

    def count_audit_logs(self) -> int:
        with self._lock:
            (cnt,) = self._conn.execute("SELECT COUNT(*) FROM audit_logs").fetchone()
            return cnt

    def clear_audit_logs(self, before_ts: Optional[float] = None):
        """Clear audit logs (optionally only those older than a timestamp)."""
        with self._lock:
            if before_ts is not None:
                self._conn.execute(
                    "DELETE FROM audit_logs WHERE timestamp < ?", (before_ts,)
                )
            else:
                self._conn.execute("DELETE FROM audit_logs")
            self._conn.commit()

    # ═══════════════════════════════════════════════════════════════════
    # Integrity
    # ═══════════════════════════════════════════════════════════════════

    def verify_checksum(self) -> Tuple[bool, Optional[str]]:
        """Verify stored policy integrity by re-hashing content."""
        pol = self.get_current_policy()
        if pol is None:
            return True, None
        expected = pol["checksum"]
        actual = "sha256:" + hashlib.sha256(
            pol["content_yaml"].encode("utf-8")
        ).hexdigest()
        ok = actual == expected
        if not ok:
            logger.error("Policy checksum mismatch: expected=%s actual=%s", expected, actual)
        return ok, actual
