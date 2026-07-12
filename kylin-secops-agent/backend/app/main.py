"""Kylin SecOps Agent - Backend Main Application Entry."""

import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html
from fastapi.responses import PlainTextResponse
from starlette.middleware.base import BaseHTTPMiddleware

# ── Observability state (Prometheus-style, pure stdlib exposition) ──
_START_TIME = time.time()
_REQUEST_COUNT = 0


class _MetricsMiddleware(BaseHTTPMiddleware):
    """Count every HTTP request that reaches the app (excluding /metrics itself)."""

    async def dispatch(self, request, call_next):
        global _REQUEST_COUNT
        if request.url.path != "/metrics":
            _REQUEST_COUNT += 1
        return await call_next(request)

from app.api.v1 import api_router
from app.core.config import settings
from app.core.database import engine
from app.middleware.request_id import RequestIDMiddleware
from app.middleware.rate_limit import rate_limit_middleware


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """Application lifespan: startup/shutdown events."""
    # Startup
    from app.core.database import init_db
    from app.services.websocket_service import ws_manager
    
    # Initialize database (create tables if not exists)
    await init_db()
    
    await ws_manager.start_redis_listener()
    yield
    # Shutdown
    await ws_manager.stop_redis_listener()
    await engine.dispose()


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="麒麟OS安全智能运维Agent - 后端API服务",
    version=settings.VERSION,
    docs_url=None,
    redoc_url=None,
    lifespan=lifespan,
    openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
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