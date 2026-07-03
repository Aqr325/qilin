"""
Policy execution engine.

Maintains a local cache of policy rules (SQLite) and executes them
both online and offline. Simple YAML-based rule matching with
per-minute count threshold detection.

State machine:
  online → WS timeout 30s → offline → network restored → sync → online
"""

import asyncio
import hashlib
import time
from typing import Any, Callable, Coroutine, Dict, List, Optional, Tuple

import yaml

from src.db import LocalDB
from src.logger import get_logger

logger = get_logger("engine")


class PolicyEngine:
    """Policy rule loading, execution, and offline auditing."""

    def __init__(
        self,
        db: LocalDB,
        on_alert: Optional[Callable[..., Coroutine]] = None,
        on_sync_needed: Optional[Callable[..., Coroutine]] = None,
    ):
        self._db = db
        self._on_alert = on_alert
        self._on_sync_needed = on_sync_needed
        self._parsed_rules: Dict = {}       # Parsed YAML rules
        self._match_counters: Dict[str, int] = {}  # rule_id -> per-minute count
        self._last_reset = time.time()
        self._state = "online"

    # ═══════════════════════════════════════════════════════════════════
    # Policy loading
    # ═══════════════════════════════════════════════════════════════════

    def load_policy(self, content_yaml: str) -> Tuple[bool, Optional[str]]:
        """Parse and load a YAML policy into the engine.

        Returns:
            (success, error_message)
        """
        try:
            rules = yaml.safe_load(content_yaml)
            if not isinstance(rules, dict):
                return False, "Policy must be a YAML mapping"
            self._parsed_rules = rules
            logger.info("Policy loaded: %d top-level keys", len(rules))
            return True, None
        except yaml.YAMLError as exc:
            logger.error("Failed to parse policy YAML: %s", exc)
            return False, str(exc)

    def get_parsed_rules(self) -> Dict:
        """Return currently loaded rules."""
        return self._parsed_rules

    def set_state(self, state: str):
        """Update engine state (online/offline)."""
        old = self._state
        self._state = state
        if old != state:
            logger.info("Engine state: %s → %s", old, state)

    @property
    def state(self) -> str:
        return self._state

    @property
    def is_offline(self) -> bool:
        return self._state == "offline"

    # ═══════════════════════════════════════════════════════════════════
    # Event evaluation
    # ═══════════════════════════════════════════════════════════════════

    def evaluate(self, event: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Evaluate a single event against loaded rules.

        Simple rule model:
          rules:
            ssh_brute_force:
              type: log_anomaly
              pattern: ssh_brute_force
              threshold: 10
              action: alert
              severity: high

        Returns list of triggered alerts.
        """
        alerts = []
        now = time.time()

        # Reset counters every 60 seconds
        if now - self._last_reset >= 60:
            self._match_counters.clear()
            self._last_reset = now

        event_type = event.get("type", "")
        event_events = event.get("events", [])

        for rule_id, rule_def in self._parsed_rules.get("rules", {}).items():
            if not isinstance(rule_def, dict):
                continue
            rule_type = rule_def.get("type", "")
            rule_pattern = rule_def.get("pattern", "")
            threshold = rule_def.get("threshold", 1)
            action = rule_def.get("action", "alert")
            severity = rule_def.get("severity", "medium")

            # Match type + pattern
            if event_type != rule_type:
                continue

            # For events with multiple sub-events, check each
            match_count = 0
            if event_events:
                for sub in event_events:
                    if isinstance(sub, dict):
                        sub_pattern = sub.get("pattern", sub.get("type", ""))
                        if rule_pattern and rule_pattern == sub_pattern:
                            match_count += 1
                        elif not rule_pattern:
                            match_count += 1

            if match_count == 0:
                # Try matching the event itself
                if rule_pattern:
                    ev_pattern = event.get("pattern", "")
                    if ev_pattern == rule_pattern:
                        match_count = 1
                else:
                    match_count = 1

            if match_count == 0:
                continue

            # Update counter
            self._match_counters[rule_id] = self._match_counters.get(rule_id, 0) + match_count

            if self._match_counters[rule_id] >= threshold:
                alert = {
                    "rule_id": rule_id,
                    "action": action,
                    "severity": severity,
                    "event": event,
                    "match_count": self._match_counters[rule_id],
                    "threshold": threshold,
                    "timestamp": now,
                }
                alerts.append(alert)

                # Execute action
                if action == "block":
                    logger.warning("Block action triggered for rule %s", rule_id)
                elif action == "isolate":
                    logger.warning("Isolate action triggered for rule %s", rule_id)

                # Record audit
                self._db.append_audit_log(
                    action=action,
                    rule_id=rule_id,
                    detail=f"Rule {rule_id} triggered (count={self._match_counters[rule_id]}",
                    result="triggered",
                )

                # Reset counter for this rule after firing
                self._match_counters[rule_id] = 0

        return alerts

    # ═══════════════════════════════════════════════════════════════════
    # Offline audit buffer
    # ═══════════════════════════════════════════════════════════════════

    def log_audit(self, action: str, rule_id: str = "",
                  detail: str = "", result: str = ""):
        """Write an audit log entry (thread-safe via LocalDB)."""
        self._db.append_audit_log(action, rule_id, detail, result)

    def get_buffered_audit_logs(self, limit: int = 1000) -> List[Dict]:
        """Retrieve buffered offline audit logs."""
        return self._db.get_audit_logs(limit=limit)

    # ═══════════════════════════════════════════════════════════════════
    # Event processing task
    # ═══════════════════════════════════════════════════════════════════

    async def process_event(self, event: Dict[str, Any]):
        """Process an incoming event through the rule engine."""
        alerts = self.evaluate(event)
        for alert in alerts:
            logger.info("Alert triggered: rule=%s severity=%s action=%s",
                        alert["rule_id"], alert["severity"], alert["action"])
            if self._on_alert:
                await self._on_alert(alert)

    # ═══════════════════════════════════════════════════════════════════
    # Policy version management
    # ═══════════════════════════════════════════════════════════════════

    async def apply_policy_push(self, version: int, content_yaml: str,
                                 checksum: str) -> bool:
        """Apply a policy push from the platform.

        Steps:
          1. Verify checksum
          2. Save to SQLite
          3. Load into engine
          4. Return success/failure

        Returns True on success.
        """
        # Verify checksum
        expected = "sha256:" + hashlib.sha256(
            content_yaml.encode("utf-8")
        ).hexdigest()
        if checksum != expected:
            logger.error("Policy push checksum mismatch: expected=%s got=%s",
                         expected, checksum)
            return False

        # Save to SQLite
        self._db.save_policy(version, content_yaml, checksum)

        # Load into engine
        ok, err = self.load_policy(content_yaml)
        if not ok:
            logger.error("Failed to load pushed policy: %s", err)
            return False

        logger.info("Policy v%d applied successfully (checksum=%s)", version, checksum)
        return True
