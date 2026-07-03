"""
Logging configuration for kylin-secops-agent.
Supports daily-rotating file logging (30-day retention) and optional debug console output.
"""

import logging
import sys
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from typing import Optional

from src.config import LOG_DIR


_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
_LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


class AgentLogger:
    """Logging manager for the agent."""

    def __init__(self, name: str = "kylin-secops-agent"):
        self._name = name
        self._logger: Optional[logging.Logger] = None

    def setup(
        self,
        level: str = "INFO",
        log_dir: Optional[Path] = None,
        debug_console: bool = False,
        backup_days: int = 30,
    ) -> logging.Logger:
        """Configure and return the root agent logger.

        Args:
            level: Log level string (DEBUG, INFO, WARNING, ERROR).
            log_dir: Directory for log files. Defaults to LOG_DIR.
            debug_console: If True, also emit to stderr.
            backup_days: Number of days to retain log files.

        """
        log_dir = log_dir or LOG_DIR
        log_dir.mkdir(parents=True, exist_ok=True)

        logger = logging.getLogger(self._name)
        logger.setLevel(getattr(logging, level.upper(), logging.INFO))

        # Remove existing handlers so setup is idempotent
        logger.handlers.clear()

        # File handler (daily rolling, keep backup_days)
        log_file = log_dir / "agent.log"
        fh = TimedRotatingFileHandler(
            filename=str(log_file),
            when="midnight",
            interval=1,
            backupCount=backup_days,
            encoding="utf-8",
        )
        fh.setFormatter(logging.Formatter(_LOG_FORMAT, _LOG_DATE_FORMAT))
        logger.addHandler(fh)

        # Optional console handler (debug mode)
        if debug_console:
            ch = logging.StreamHandler(sys.stderr)
            ch.setFormatter(logging.Formatter(_LOG_FORMAT, _LOG_DATE_FORMAT))
            logger.addHandler(ch)

        self._logger = logger
        return logger

    @property
    def logger(self) -> logging.Logger:
        if self._logger is None:
            return self.setup()
        return self._logger


# Module-level singleton
_agent_logger = AgentLogger()


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Get a child logger of the agent logging hierarchy."""
    if name:
        return logging.getLogger(f"kylin-secops-agent.{name}")
    return logging.getLogger("kylin-secops-agent")
