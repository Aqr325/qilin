"""Kylin SecOps Agent - Backend Main Application Entry."""

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html
from fastapi.responses import PlainTextResponse, JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.middleware.base import BaseHTTPMiddleware

# ── Observability state (Prometheus-style, pure stdlib exposition) ──
_START_TIME = time.time()
_REQUEST_COUNT = 0

logger = logging.getLogger(__name__)


class _MetricsMiddleware(BaseHTTPMiddleware):
    """Count every HTTP request that reaches the app (excluding /metrics itself)."""

    async def dispatch(self, request, call_next):
        global _REQUEST_COUNT
        if request.url.path != "/metrics":
            _REQUEST_COUNT += 1
        return await call_next(request)

from app.api.v1 import api_router
from app.core.config import settings
from app.core.database import engine, async_session_factory
from app.middleware.request_id import RequestIDMiddleware
from app.middleware.rate_limit import rate_limit_middleware
from app.models.agent import Agent
from app.services.websocket_service import ws_manager


# ── Background: Offline Timeout Detection ──

_OFFLINE_TASK: asyncio.Task | None = None


async def _offline_timeout_detector() -> None:
    """后台任务：每 60 秒检查一次超时未心跳的 Agent，标记为 offline 并广播。"""
    from sqlalchemy import select
    logger.info("Offline timeout detector started (interval=60s)")
    while True:
        try:
            await asyncio.sleep(60)
            async with async_session_factory() as db:
                now = datetime.now(timezone.utc)
                cutoff = now - timedelta(seconds=30)
                result = await db.execute(
                    select(Agent)
                    .where(
                        Agent.status == "online",
                        Agent.last_heartbeat.isnot(None),
                        Agent.last_heartbeat < cutoff,
                        Agent.is_deleted == False,
                    )
                )
                stale_agents = result.scalars().all()
                if stale_agents:
                    for agent in stale_agents:
                        agent.status = "offline"
                        agent.last_status_change = now
                    await db.commit()
                    logger.info(
                        "Marked %d agent(s) as offline (timeout > 30s): %s",
                        len(stale_agents),
                        [a.agent_id for a in stale_agents],
                    )
                    # 广播每个 Agent 的状态变更
                    for agent in stale_agents:
                        try:
                            await ws_manager.broadcast("agent.status", {
                                "agent_id": agent.agent_id,
                                "old_status": "online",
                                "new_status": "offline",
                                "timestamp": now.isoformat(),
                            })
                        except Exception:
                            logger.warning(
                                "Failed to broadcast offline status for %s", agent.agent_id, exc_info=True
                            )
        except asyncio.CancelledError:
            logger.info("Offline timeout detector cancelled")
            break
        except Exception:
            logger.exception("Offline timeout detector error")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """Application lifespan: startup/shutdown events."""
    # Startup
    from app.core.database import init_db
    from app.services.websocket_service import ws_manager

    # Initialize database (create tables if not exists)
    await init_db()

    await ws_manager.start_redis_listener()

    # 启动离线超时检测后台任务
    global _OFFLINE_TASK
    _OFFLINE_TASK = asyncio.create_task(_offline_timeout_detector(), name="offline_timeout_detector")
    logger.info("Background task 'offline_timeout_detector' started")

    yield

    # Shutdown: 优雅停止后台任务
    if _OFFLINE_TASK is not None:
        _OFFLINE_TASK.cancel()
        try:
            await _OFFLINE_TASK
        except asyncio.CancelledError:
            pass
        logger.info("Background task 'offline_timeout_detector' stopped")

    await ws_manager.stop_redis_listener()
    await engine.dispose()


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="麒麟OS安全智能运维Agent - 后端API服务",
    version=settings.VERSION,
    docs_url=None,
    redoc_url=None,
    lifespan=lifespan,
    # M3 (P0): never expose the full API schema in production. openapi.json is
    # mounted only when DEBUG is on (local dev). In prod it is None → no route.
    openapi_url=(
        f"{settings.API_V1_PREFIX}/openapi.json" if settings.DEBUG else None
    ),
)

# ── Middleware Chain ──
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID", "X-Agent-Token"],
)
app.add_middleware(RequestIDMiddleware)
app.add_middleware(rate_limit_middleware)
app.add_middleware(_MetricsMiddleware)


# ── Mount Routers ──
app.include_router(api_router, prefix=settings.API_V1_PREFIX)


# ── Global exception handlers (security: never leak internals) ──
import logging as _app_log

_APP_LOGGER = _app_log.getLogger("kylin.errors")


@app.exception_handler(ValueError)
async def _value_error_handler(request: Request, exc: ValueError):
    # Covers malformed UUID/path params etc. → clean 400 instead of leaking 500.
    return JSONResponse(
        status_code=400, content={"detail": "请求参数格式无效。"}
    )


@app.exception_handler(Exception)
async def _unhandled_exception_handler(request: Request, exc: Exception):
    _APP_LOGGER.exception(
        "Unhandled exception: %s %s", request.method, request.url.path
    )
    return JSONResponse(
        status_code=500,
        content={
            "detail": "服务器内部错误，请联系管理员。",
            "request_id": request.headers.get("X-Request-ID", ""),
        },
    )


# ── Custom Doc Endpoints (only in debug/dev mode) ──
@app.get("/docs", include_in_schema=False)
async def swagger_ui():
    """Swagger UI — only available when DEBUG is enabled."""
    if not settings.DEBUG:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="API documentation is disabled in production",
        )
    return get_swagger_ui_html(
        openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
        title=f"{settings.PROJECT_NAME} - Swagger UI",
    )


@app.get("/redoc", include_in_schema=False)
async def redoc_ui():
    """ReDoc UI — only available when DEBUG is enabled."""
    if not settings.DEBUG:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="API documentation is disabled in production",
        )
    return get_redoc_html(
        openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
        title=f"{settings.PROJECT_NAME} - ReDoc",
    )


@app.get("/health", tags=["system"])
async def health_check():
    """健康检查端点."""
    return {
        "status": "ok",
        "version": settings.VERSION,
        "service": settings.PROJECT_NAME,
    }


@app.get("/metrics", tags=["system"])
async def metrics():
    """Prometheus 指标端点（纯标准库 text 格式，无第三方依赖）.

    暴露：
      - kylin_agent_info            构建静态信息（版本/服务名），值恒为 1
      - kylin_agent_uptime_seconds  进程已运行秒数
      - kylin_agent_requests_total  后端累计处理的 HTTP 请求数
      - kylin_agent_health_status   /health 正常为 1，异常为 0
    """
    uptime = time.time() - _START_TIME
    health_status = 1
    try:
        hc = await health_check()
        health_status = 1 if hc.get("status") == "ok" else 0
    except Exception:
        health_status = 0

    payload = "\n".join([
        "# HELP kylin_agent_info Static build info for this Agent instance.",
        "# TYPE kylin_agent_info gauge",
        f'kylin_agent_info{{version="{settings.VERSION}",service="{settings.PROJECT_NAME}"}} 1',
        "# HELP kylin_agent_uptime_seconds Process uptime in seconds.",
        "# TYPE kylin_agent_uptime_seconds gauge",
        f"kylin_agent_uptime_seconds {uptime:.2f}",
        "# HELP kylin_agent_requests_total Total HTTP requests handled by the backend.",
        "# TYPE kylin_agent_requests_total counter",
        f"kylin_agent_requests_total {_REQUEST_COUNT}",
        "# HELP kylin_agent_health_status 1 if /health reports ok, else 0.",
        "# TYPE kylin_agent_health_status gauge",
        f"kylin_agent_health_status {health_status}",
    ])
    return PlainTextResponse(payload + "\n")