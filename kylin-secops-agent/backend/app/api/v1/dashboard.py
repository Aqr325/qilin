"""Dashboard routes."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.permissions import Permission, require_permission
from app.schemas.ai import DashboardOverview, HeatmapData, TopAlertType, TrendData
from app.schemas.common import ApiResponse
from app.services import dashboard_service

router = APIRouter(prefix="/dashboard", tags=["仪表盘"])


@router.get("/overview", response_model=ApiResponse[DashboardOverview])
async def dashboard_overview(
    current_user: dict = Depends(require_permission(Permission.DASHBOARD_READ)),
    db: AsyncSession = Depends(get_db),
):
    """全局安全概览."""
    result = await dashboard_service.get_overview(db)
    return ApiResponse(data=result)


@router.get("/alert-trend", response_model=ApiResponse[TrendData])
async def alert_trend(
    days: int = Query(default=7, ge=1, le=90),
    current_user: dict = Depends(require_permission(Permission.DASHBOARD_READ)),
    db: AsyncSession = Depends(get_db),
):
    """告警趋势图数据."""
    result = await dashboard_service.get_alert_trend(db, days)
    return ApiResponse(data=result)


@router.get("/agent-heatmap", response_model=ApiResponse[HeatmapData])
async def agent_heatmap(
    hours: int = Query(default=24, ge=1, le=168),
    current_user: dict = Depends(require_permission(Permission.DASHBOARD_READ)),
    db: AsyncSession = Depends(get_db),
):
    """Agent健康热力图."""
    result = await dashboard_service.get_agent_heatmap(db, hours)
    return ApiResponse(data=result)


@router.get("/top-alerts", response_model=ApiResponse[list[TopAlertType]])
async def top_alerts(
    limit: int = Query(default=10, ge=1, le=50),
    time_range: str = Query(default="24h"),
    current_user: dict = Depends(require_permission(Permission.DASHBOARD_READ)),
    db: AsyncSession = Depends(get_db),
):
    """Top N告警类型."""
    result = await dashboard_service.get_top_alerts(db, limit, time_range)
    return ApiResponse(data=result)