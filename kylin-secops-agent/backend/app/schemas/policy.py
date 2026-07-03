"""Policy schemas."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ── Request ──

class PolicyCreate(BaseModel):
    """创建策略请求."""

    name: str = Field(..., min_length=1, max_length=128)
    description: Optional[str] = None
    policy_type: str = Field(..., description="策略类型")
    rules: Dict[str, Any] = Field(..., description="策略规则集")
    target_type: str = Field(default="all")
    target_value: List[str] = Field(default_factory=list)
    priority: int = Field(default=100, ge=1, le=1000)
    effective_start: Optional[datetime] = None
    effective_end: Optional[datetime] = None


class PolicyUpdate(BaseModel):
    """更新策略请求."""

    name: Optional[str] = Field(None, min_length=1, max_length=128)
    description: Optional[str] = None
    rules: Optional[Dict[str, Any]] = None
    target_type: Optional[str] = None
    target_value: Optional[List[str]] = None
    priority: Optional[int] = Field(None, ge=1, le=1000)
    effective_start: Optional[datetime] = None
    effective_end: Optional[datetime] = None
    changelog: Optional[str] = None


class PolicyDeployRequest(BaseModel):
    """策略下发请求."""

    agent_ids: Optional[List[str]] = None
    force: bool = False


class PolicyToggleRequest(BaseModel):
    """策略启用/禁用请求."""

    enabled: bool


class PolicyRollbackRequest(BaseModel):
    """策略回滚请求."""

    version_number: int = Field(..., ge=1)


class PolicyValidateRequest(BaseModel):
    """策略校验请求."""

    rules: Dict[str, Any]


class PolicyPreviewTargetsRequest(BaseModel):
    """预览策略目标请求."""

    target_expression: str


# ── Response ──

class PolicySummary(BaseModel):
    """策略列表摘要."""

    id: str
    name: str
    description: Optional[str] = None
    policy_type: str
    policy_type_label: Optional[str] = None
    version: int = 1
    status: str
    status_label: Optional[str] = None
    target_type: str
    target_value: Optional[List[str]] = None
    priority: int = 100
    enabled: bool = True
    effective_start: Optional[datetime] = None
    effective_end: Optional[datetime] = None
    created_by_name: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class PolicyDetail(BaseModel):
    """策略详情."""

    id: str
    name: str
    description: Optional[str] = None
    policy_type: str
    policy_type_label: Optional[str] = None
    version: int = 1
    rules: Optional[Dict[str, Any]] = None
    status: str
    status_label: Optional[str] = None
    target_type: str
    target_value: Optional[List[str]] = None
    priority: int = 100
    effective_start: Optional[datetime] = None
    effective_end: Optional[datetime] = None
    is_template: bool = False
    created_by: Optional[Dict[str, Any]] = None
    updated_by: Optional[Dict[str, Any]] = None
    deployed_version: int = 0
    last_deployed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class PolicyVersion(BaseModel):
    """策略版本."""

    id: str
    policy_id: str
    version: int
    rules: Optional[Dict[str, Any]] = None
    changelog: Optional[str] = None
    created_by_name: Optional[str] = None
    created_at: Optional[datetime] = None


class DeployStatusMap(BaseModel):
    """下发状态映射."""

    deployed: int = 0
    pending: int = 0
    failed: int = 0
    total: int = 0
    details: List[Dict[str, Any]] = Field(default_factory=list)


class PolicyValidationResult(BaseModel):
    """策略校验结果."""

    valid: bool
    errors: List[str] = Field(default_factory=list)


class PolicyPreviewTargets(BaseModel):
    """策略目标预览."""

    agent_count: int = 0
    sample_list: List[str] = Field(default_factory=list)


class PolicyFilterParams(BaseModel):
    """策略筛选参数."""

    page: int = Field(default=1, ge=1)
    size: int = Field(default=20, ge=1, le=100)
    status: Optional[str] = None
    policy_type: Optional[str] = None
    keyword: Optional[str] = None