"""Alert management routes."""

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_pagination, get_request_id
from app.core.database import get_db
from app.core.permissions import Permission, require_permission
from app.schemas.alert import (
    AlertDetail,
    AlertStats,
    AlertStatusChange,
    AlertSummary,
    AssignAlertRequest,
    BatchStatusRequest,
    BatchStatusResult,
    MitreMatrixItem,
    SuppressAlertRequest,
    SuppressRule,
    TimelineData,
    UpdateAlertStatusRequest,
)
from app.schemas.common import ApiResponse, Page
from app.services import alert_service
import uuid

router = APIRouter(prefix="/alerts", tags=["告警管理"])


@router.get("", response_model=ApiResponse[Page[AlertSummary]])
async def list_alerts(
    page: dict = Depends(get_pagination),
    status: str = Query(None),
    severity: str = Query(None),
    alert_type: str = Query(None),
    agent_id: str = Query(None),
    start_time: str = Query(None),
    end_time: str = Query(None),
    mitre_technique: str = Query(None),
    keyword: str = Query(None),
    assignee_id: str = Query(None),
    sort_by: str = Query("created_at"),
    sort_order: str = Query("desc"),
    current_user: dict = Depends(require_permission(Permission.ALERT_READ)),
    db: AsyncSession = Depends(get_db),
):
    """告警列表（分页+筛选）."""
    result = await alert_service.list_alerts(
        db, page=page["page"], size=page["size"],
        status=status, severity=severity, alert_type=alert_type,
        agent_id=agent_id, start_time=start_time, end_time=end_time,
        mitre_technique=mitre_technique, keyword=keyword,
        assignee_id=assignee_id, sort_by=sort_by, sort_order=sort_order,
    )
    return ApiResponse(data=result)


@router.get("/stats", response_model=ApiResponse[AlertStats])
async def alert_stats(
    time_range: str = Query(None),
    current_user: dict = Depends(require_permission(Permission.ALERT_READ)),
    db: AsyncSession = Depends(get_db),
):
    """告警统计概览."""
    result = await alert_service.get_stats(db, time_range)
    return ApiResponse(data=result)


@router.get("/mitre-matrix", response_model=ApiResponse[list[MitreMatrixItem]])
async def mitre_matrix(
    current_user: dict = Depends(require_permission(Permission.ALERT_READ)),
    db: AsyncSession = Depends(get_db),
):
    """获取MITRE ATT&CK矩阵."""
    result = await alert_service.get_mitre_matrix(db)
    return ApiResponse(data=result)


@router.get("/timeline", response_model=ApiResponse[TimelineData])
async def alert_timeline(
    start_time: str = Query(None),
    end_time: str = Query(None),
    interval: str = Query("1h"),
    current_user: dict = Depends(require_permission(Permission.ALERT_READ)),
    db: AsyncSession = Depends(get_db),
):
    """告警时间线视图."""
    result = await alert_service.get_timeline(db, start_time, end_time, interval)
    return ApiResponse(data=result)


@router.get("/export")
async def export_alerts(
    format: str = Query("csv"),
    start_time: str = Query(None),
    end_time: str = Query(None),
    severity: str = Query(None),
    status: str = Query(None),
    current_user: dict = Depends(require_permission(Permission.ALERT_EXPORT)),
    db: AsyncSession = Depends(get_db),
):
    """导出告警数据."""
    return await alert_service.export_alerts(
        db, format=format, start_time=start_time,
        end_time=end_time, severity=severity, status=status,
    )


@router.get("/{alert_id}", response_model=ApiResponse[AlertDetail])
async def get_alert(
    alert_id: uuid.UUID,
    current_user: dict = Depends(require_permission(Permission.ALERT_READ)),
    db: AsyncSession = Depends(get_db),
):
    """告警详情."""
    result = await alert_service.get_alert_detail(db, alert_id)
    return ApiResponse(data=result)


@router.put("/{alert_id}/status", response_model=ApiResponse[AlertDetail])
async def update_alert_status(
    alert_id: uuid.UUID,
    req: UpdateAlertStatusRequest,
    current_user: dict = Depends(require_permission(Permission.ALERT_WRITE)),
    db: AsyncSession = Depends(get_db),
):
    """更新告警状态."""
    result = await alert_service.update_status(
        db, alert_id, req.status, req.comment, operator=current_user,
    )
    return ApiResponse(data=result)


@router.post("/batch/status", response_model=ApiResponse[BatchStatusResult])
async def batch_update_status(
    req: BatchStatusRequest,
    current_user: dict = Depends(require_permission(Permission.ALERT_WRITE)),
    db: AsyncSession = Depends(get_db),
):
    """批量处置告警."""
    result = await alert_service.batch_update_status(
        db, req.alert_ids, req.status, req.comment,
        operator=current_user, notify=req.notify_assignee,
    )
    return ApiResponse(data=result)


@router.post("/{alert_id}/assign", response_model=ApiResponse[AlertDetail])
async def assign_alert(
    alert_id: uuid.UUID,
    req: AssignAlertRequest,
    current_user: dict = Depends(require_permission(Permission.ALERT_ASSIGN)),
    db: AsyncSession = Depends(get_db),
):
    """指派告警处理人."""
    result = await alert_service.assign_alert(
        db, alert_id, req.assignee_id, operator=current_user,
    )
    return ApiResponse(data=result)


@router.get("/{alert_id}/history", response_model=ApiResponse[list[AlertStatusChange]])
async def get_alert_history(
    alert_id: uuid.UUID,
    current_user: dict = Depends(require_permission(Permission.ALERT_READ)),
    db: AsyncSession = Depends(get_db),
):
    """告警状态流转历史."""
    result = await alert_service.get_status_history(db, alert_id)
    return ApiResponse(data=result)


@router.get("/{alert_id}/related", response_model=ApiResponse[list[AlertSummary]])
async def get_related_alerts(
    alert_id: uuid.UUID,
    current_user: dict = Depends(require_permission(Permission.ALERT_READ)),
    db: AsyncSession = Depends(get_db),
):
    """关联告警查询."""
    result = await alert_service.get_related_alerts(db, alert_id)
    return ApiResponse(data=result)


@router.post("/{alert_id}/suppress", response_model=ApiResponse[SuppressRule])
async def suppress_alert(
    alert_id: uuid.UUID,
    req: SuppressAlertRequest,
    current_user: dict = Depends(require_permission(Permission.ALERT_SUPPRESS)),
    db: AsyncSession = Depends(get_db),
):
    """添加告警抑制规则."""
    result = await alert_service.suppress_alert(
        db, alert_id, req.rule_config, req.expire_time, operator=current_user,
    )
    return ApiResponse(data=result)