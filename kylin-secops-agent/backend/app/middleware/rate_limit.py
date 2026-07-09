"""Rate limiting middleware using a sliding window counter.

Desktop-first: in-memory sliding window per IP. No Redis dependency.
Configuration comes from app.core.config settings.

Supported endpoints:
  - POST /api/v1/auth/login  → RATE_LIMIT_LOGIN per minute
  - Other endpoints          → RATE_LIMIT_DEFAULT per minute (when enabled)

Implementation note: this middleware returns a 429 Response directly rather
than raising HTTPException, because as the outermost middleware its exceptions
would bypass Starlette's exception handler and surface as 500.
"""

import time
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from starlette.requests import Request
from starlette.responses import JSONResponse

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class _SlidingWindow:
    """Fixed-window counter with window start timestamp."""
    count: int = 0
    window_start: float = field(default_factory=time.monotonic)


# Global stores: IP -> _SlidingWindow
_login_counter: dict[str, _SlidingWindow] = defaultdict(_SlidingWindow)
_default_counter: dict[str, _SlidingWindow] = defaultdict(_SlidingWindow)


def _get_client_ip(request: Request) -> str:
    """Extract client IP, honouring X-Forwarded-For."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    client = request.client
    return client.host if client else "unknown"


def _check_rate_limit(
    ip: str,
    counter: dict[str, _SlidingWindow],
    limit: int,
    window_seconds: int = 60,
) -> bool:
    """Return True if under limit, False if rate-limited."""
    now = time.monotonic()
    win = counter.setdefault(ip, _SlidingWindow())

    # Reset if window expired
    if now - win.window_start >= window_seconds:
        win.count = 0
        win.window_start = now

    if win.count >= limit:
        return False
    win.count += 1
    return True


def _build_response(message: str, limit: int, remaining: int) -> JSONResponse:
    """Build a 429 JSON response with rate-limit headers."""
    return JSONResponse(
        status_code=429,
        content={
            "error": "rate_limit_exceeded",
            "message": message,
        },
        headers={
            "X-RateLimit-Limit": str(limit),
            "X-RateLimit-Remaining": str(max(0, remaining)),
            "Retry-After": "60",
        },
    )


async def _handle_request(request: Request) -> Optional[JSONResponse]:
    """Execute rate-limit checks. Returns a 429 Response to block, or None to pass through."""
    if not settings.RATE_LIMIT_ENABLED:
        return None

    path = request.url.path
    method = request.method
    ip = _get_client_ip(request)

    # Login rate limit
    if method == "POST" and path.rstrip("/").endswith("/auth/login"):
        allowed = _check_rate_limit(ip, _login_counter, settings.RATE_LIMIT_LOGIN)
        if not allowed:
            logger.warning(
                "Rate limit exceeded for login from %s (limit=%d/min)",
                ip, settings.RATE_LIMIT_LOGIN,
            )
            return _build_response(
                f"登录请求过于频繁，请稍后再试（限制：{settings.RATE_LIMIT_LOGIN} 次/分钟）",
                settings.RATE_LIMIT_LOGIN,
                0,
            )

    # Default rate limit for other write operations
    if method in ("POST", "PUT", "PATCH", "DELETE") and path != "/health":
        allowed = _check_rate_limit(ip, _default_counter, settings.RATE_LIMIT_DEFAULT)
        if not allowed:
            logger.warning(
                "Default rate limit exceeded for %s %s from %s (limit=%d/min)",
                method, path, ip, settings.RATE_LIMIT_DEFAULT,
            )
            return _build_response(
                f"请求过于频繁，请稍后再试（限制：{settings.RATE_LIMIT_DEFAULT} 次/分钟）",
                settings.RATE_LIMIT_DEFAULT,
                0,
            )

    return None


class RateLimitMiddleware:
    """ASGI middleware wrapper for rate limiting (app.add_middleware compatible)."""

    def __init__(self, app: Callable[..., Any]):
        self.app = app

    async def __call__(self, scope: dict, receive: Callable[..., Any], send: Callable[..., Any]) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive)
        block_response = await _handle_request(request)
        if block_response is not None:
            await block_response(scope, receive, send)
            return

        await self.app(scope, receive, send)


# Export as class for app.add_middleware()
rate_limit_middleware = RateLimitMiddleware
