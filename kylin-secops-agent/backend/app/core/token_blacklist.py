"""Refresh token blacklist and rotation support.

Maintains a rotating blacklist of revoked refresh tokens to prevent
stolen tokens from being reused. Uses an LRU-style in-memory cache
for desktop deployments (Redis-free) and can optionally integrate with
Redis when available.
"""

import logging
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, Set

from app.core.config import settings

logger = logging.getLogger(__name__)


class TokenBlacklist:
    """In-memory token blacklist with expiry-based cleanup.

    Desktop-first: uses a simple dict with TTL tracking.
    Redis integration is a future enhancement (no current dependency).
    """

    def __init__(self, max_size: int = 10000, cleanup_interval_seconds: int = 300):
        self._tokens: dict[str, float] = {}  # token_hash -> expiry_timestamp
        self._max_size = max_size
        self._last_cleanup = time.monotonic()
        self._cleanup_interval = cleanup_interval_seconds

    def blacklist(self, token_jti: str, expires_at: Optional[datetime] = None) -> None:
        """Add a refresh token to the blacklist.

        Args:
            token_jti: Unique token identifier (JWT 'jti' claim).
            expires_at: When the blacklist entry expires (defaults to token expiry).
        """
        if expires_at is None:
            expires_at = datetime.now(timezone.utc) + timedelta(
                hours=settings.REFRESH_TOKEN_EXPIRE_HOURS
            )
        expiry_ts = expires_at.timestamp()
        self._tokens[token_jti] = expiry_ts
        self._maybe_cleanup()

    def is_blacklisted(self, token_jti: str) -> bool:
        """Check if a token JTI is blacklisted (and entry not expired)."""
        now = time.time()
        if token_jti not in self._tokens:
            return False
        if self._tokens[token_jti] <= now:
            del self._tokens[token_jti]  # Expired blacklist entry, remove it
            return False
        return True

    def _maybe_cleanup(self) -> None:
        """Remove expired entries and enforce max size."""
        now = time.monotonic()
        if now - self._last_cleanup < self._cleanup_interval:
            return
        self._last_cleanup = now

        # Remove expired entries
        current_time = time.time()
        expired = [k for k, v in self._tokens.items() if v <= current_time]
        for k in expired:
            del self._tokens[k]

        # Enforce max size (remove oldest entries)
        if len(self._tokens) > self._max_size:
            sorted_by_expiry = sorted(self._tokens.items(), key=lambda x: x[1])
            overflow = len(sorted_by_expiry) - self._max_size
            for k, _ in sorted_by_expiry[:overflow]:
                del self._tokens[k]

    def size(self) -> int:
        return len(self._tokens)


# Global singleton
token_blacklist = TokenBlacklist()
