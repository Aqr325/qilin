"""Policy service: CRUD, version management, deploy, validate."""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import HTTPException, status
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import Agent
from app.models.policy import Policy, PolicyTarget, PolicyVersion
from app.repositories.agent_repo import AgentRepository
from app.repositories.policy_repo import (
    PolicyRepository,
    PolicyTargetRepository,
    PolicyVersionRepository,
)
from app.schemas.common import Page
from app.schemas.policy import (
    DeployStatusMap,
    PolicyCreate,
    PolicyDetail,
    PolicyPreviewTargets,
    PolicySummary,
    PolicyUpdate,
    PolicyValidationResult,
    PolicyVersion as PolicyVersionSchema,
)
from app.services.websocket_service import ws_manager


POLICY_TYPE_LABELS = {
    "file_integrity": "文件完整性监控",
    "process_whitelist": "进程白名单",
    "network_firewall": "网络访问控制",
    "login_policy": "登录安全策略",
    "vulnerability_scan": "漏洞扫描策略",
    "log_audit": "日志审计规则",
}

STATUS_LABELS = {
    "draft": "草稿",
    "enabled": "已启用",
    "disabled": "已禁用",
    "archived": "已归档",
}


async def create_policy(
    db: AsyncSession,
    req: PolicyCreate,
    operator: dict,
) -> PolicyDetail:
    """Create a new policy."""
    repo = PolicyRepository(db)
    policy = Policy(
        name=req.name,
        description=req.description,
        policy_type=req.policy_type,
        version=1,
        rules=req.rules,
        status="draft",
        target_type=req.target_type,
        target_value=req.target_value,
        priority=req.priority,
        effective_start=req.effective_start,
        effective_end=req.effective_end,
        created_by=uuid.UUID(operator["id"]),
        updated_by=uuid.UUID(operator["id"]),
    )
    db.add(policy)
    await db.flush()

    # Create initial version
    version = PolicyVersion(
        policy_id=policy.id,
        version=1,
        rules=req.rules,
        changelog="初始版本",
        created_by=uuid.UUID(operator["id"]),
    )
    db.add(version)
    await db.flush()
    await db.refresh(policy)

    return await _policy_to_detail(policy)


async def list_policies(
    db: AsyncSession,
    page: int = 1,
    size: int = 20,
    status: Optional[str] = None,
    policy_type: Optional[str] = None,
    keyword: Optional[str] = None,
) -> Page[PolicySummary]:
    """List policies with pagination."""
    repo = PolicyRepository(db)
    skip = (page - 1) * size
    policies, total = await repo.list_paginated(
        skip=skip, limit=size,
        status=status, policy_type=policy_type, keyword=keyword,
    )
    items = [
        PolicySummary(
            id=str(p.id),
            name=p.name,
            description=p.description,
            policy_type=p.policy_type,
            policy_type_label=POLICY_TYPE_LABELS.get(p.policy_type),
            version=p.version,
            status=p.status,
            status_label=STATUS_LABELS.get(p.status),
            target_type=p.target_type,
            target_value=p.target_value,
            priority=p.priority,
            enabled=p.status == "enabled",
            effective_start=p.effective_start,
            effective_end=p.effective_end,
            created_at=p.created_at,
            updated_at=p.updated_at,
        )
        for p in policies
    ]
    return Page.create(items, total, page, size)


async def get_policy_detail(
    db: AsyncSession,
    policy_id: str,
) -> PolicyDetail:
    """Get policy detail."""
    repo = PolicyRepository(db)
    policy = await repo.get(uuid.UUID(policy_id))
    if not policy or policy.is_deleted:
        raise HTTPException(status_code=404, detail="策略不存在")
    return await _policy_to_detail(policy)


async def update_policy(
    db: AsyncSession,
    policy_id: str,
    req: PolicyUpdate,
    operator: dict,
) -> PolicyDetail:
    """Update policy (creates new version)."""
    repo = PolicyRepository(db)
    policy = await repo.get(uuid.UUID(policy_id))
    if not policy or policy.is_deleted:
        raise HTTPException(status_code=404, detail="策略不存在")

    # Increment version and save current rules as version history
    old_rules = policy.rules
    policy.version += 1
    policy.updated_by = uuid.UUID(operator["id"])

    update_data = req.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if field != "changelog" and hasattr(policy, field):
            setattr(policy, field, value)

    await db.flush()

    # Create version record
    version = PolicyVersion(
        policy_id=policy.id,
        version=policy.version,
        rules=policy.rules,
        changelog=req.changelog or "更新策略",
        created_by=uuid.UUID(operator["id"]),
    )
    db.add(version)
    await db.flush()
    await db.refresh(policy)

    return await _policy_to_detail(policy)


async def delete_policy(db: AsyncSession, policy_id: str, operator: dict):
    """Soft delete policy."""
    try:
        pid = uuid.UUID(policy_id)
    except (ValueError, AttributeError):
        raise HTTPException(status_code=404, detail="策略不存在")
    repo = PolicyRepository(db)
    await repo.soft_delete(pid)


async def deploy_policy(
    db: AsyncSession,
    policy_id: str,
    agent_ids: Optional[List[str]] = None,
    force: bool = False,
    operator: Optional[dict] = None,
) -> dict:
    """Deploy policy to agents.

    真实落库：为每个目标Agent写入/更新 PolicyTarget 下发记录（可追溯下发关系），
    并提升对应Agent的 config_version，触发其下次心跳拉取最新策略。
    """
    repo = PolicyRepository(db)
    policy = await repo.get(uuid.UUID(policy_id))
    if not policy:
        raise HTTPException(status_code=404, detail="策略不存在")

    # 解析目标Agent：显式指定则使用指定列表，否则下发到全部在线Agent
    agent_repo = AgentRepository(db)
    if agent_ids:
        targets = [a for a in agent_ids if a]
    else:
        online_agents, _ = await agent_repo.list_paginated(limit=5000, status="online")
        targets = [a.agent_id for a in online_agents]

    now = datetime.now(timezone.utc)
    deployed: List[str] = []
    for aid in targets:
        # 幂等：先清理该策略下此Agent的旧下发记录，再写入最新一条
        await db.execute(
            delete(PolicyTarget).where(
                PolicyTarget.policy_id == policy.id,
                PolicyTarget.agent_id == aid,
            )
        )
        db.add(PolicyTarget(
            policy_id=policy.id,
            agent_id=aid,
            status="deployed",
            deployed_version=policy.version,
            deployed_at=now,
        ))
        deployed.append(aid)

        # 提升Agent配置版本，触发其下次心跳拉取最新策略
        agent = await agent_repo.get_by_agent_id(aid)
        if agent:
            agent.config_version = (agent.config_version or 0) + 1

    policy.deployed_version = policy.version
    policy.last_deployed_at = now
    await db.flush()

    # Broadcast via WebSocket
    await ws_manager.broadcast("policy.deployed", {
        "policy_id": str(policy.id),
        "version": policy.version,
        "agent_count": len(deployed),
        "agent_ids": deployed,
    })

    return {
        "task_id": str(uuid.uuid4()),
        "deploy_count": len(deployed),
        "agent_ids": deployed,
    }


async def toggle_policy(
    db: AsyncSession,
    policy_id: str,
    enabled: bool,
    operator: dict,
) -> PolicyDetail:
    """Toggle policy enabled/disabled."""
    repo = PolicyRepository(db)
    policy = await repo.get(uuid.UUID(policy_id))
    if not policy:
        raise HTTPException(status_code=404, detail="策略不存在")

    policy.status = "enabled" if enabled else "disabled"
    policy.updated_by = uuid.UUID(operator["id"])
    await db.flush()
    await db.refresh(policy)

    return await _policy_to_detail(policy)


async def rollback_policy(
    db: AsyncSession,
    policy_id: str,
    version_number: int,
    operator: dict,
) -> PolicyDetail:
    """Rollback policy to a specific version."""
    repo = PolicyRepository(db)
    version_repo = PolicyVersionRepository(db)

    policy = await repo.get(uuid.UUID(policy_id))
    if not policy:
        raise HTTPException(status_code=404, detail="策略不存在")

    old_version = await version_repo.get_version(uuid.UUID(policy_id), version_number)
    if not old_version:
        raise HTTPException(status_code=404, detail=f"版本 {version_number} 不存在")

    policy.version += 1
    policy.rules = old_version.rules
    policy.updated_by = uuid.UUID(operator["id"])
    await db.flush()

    # Create rollback version
    new_version = PolicyVersion(
        policy_id=policy.id,
        version=policy.version,
        rules=policy.rules,
        changelog=f"回滚到版本 {version_number}",
        created_by=uuid.UUID(operator["id"]),
    )
    db.add(new_version)
    await db.flush()
    await db.refresh(policy)

    return await _policy_to_detail(policy)


async def get_versions(
    db: AsyncSession,
    policy_id: str,
) -> List[PolicyVersionSchema]:
    """Get policy version history."""
    version_repo = PolicyVersionRepository(db)
    versions = await version_repo.list_by_policy(uuid.UUID(policy_id))
    return [
        PolicyVersionSchema(
            id=str(v.id),
            policy_id=str(v.policy_id),
            version=v.version,
            rules=v.rules,
            changelog=v.changelog,
            created_at=v.created_at,
        )
        for v in versions
    ]


async def get_deploy_status(
    db: AsyncSession,
    policy_id: str,
) -> DeployStatusMap:
    """Get policy deploy status."""
    target_repo = PolicyTargetRepository(db)
    status = await target_repo.get_deploy_status(uuid.UUID(policy_id))
    return DeployStatusMap(**status)


async def validate_policy(rules: Dict[str, Any]) -> PolicyValidationResult:
    """Validate policy rules syntax."""
    errors = []
    if not isinstance(rules, dict):
        errors.append("策略规则必须为JSON对象")
    if "paths" in rules and not isinstance(rules["paths"], list):
        errors.append("paths 字段必须为数组")

    return PolicyValidationResult(valid=len(errors) == 0, errors=errors)


async def preview_targets(
    db: AsyncSession,
    target_expression: str,
) -> PolicyPreviewTargets:
    """Preview policy target agents based on target expression."""
    from sqlalchemy import select, func
    from app.models.agent import Agent

    if target_expression == "all":
        stmt = select(Agent).where(Agent.is_deleted == 0)
        results = await db.execute(stmt)
        agents = results.scalars().all()
    elif target_expression.startswith("tag:"):
        tag = target_expression[4:]
        stmt = select(Agent).where(
            Agent.is_deleted == 0,
            Agent.tags.contains([tag]),
        )
        results = await db.execute(stmt)
        agents = results.scalars().all()
    elif target_expression.startswith("ip:"):
        ip_prefix = target_expression[3:]
        stmt = select(Agent).where(
            Agent.is_deleted == 0,
            Agent.ip_address.startswith(ip_prefix),
        )
        results = await db.execute(stmt)
        agents = results.scalars().all()
    else:
        agent_ids = [a.strip() for a in target_expression.split(",") if a.strip()]
        if not agent_ids:
            return PolicyPreviewTargets(agent_count=0, sample_list=[])
        stmt = select(Agent).where(
            Agent.is_deleted == 0,
            Agent.agent_id.in_(agent_ids),
        )
        results = await db.execute(stmt)
        agents = results.scalars().all()

    sample_list = []
    for agent in agents[:10]:
        sample_list.append({
            "agent_id": agent.agent_id,
            "hostname": agent.hostname,
            "ip_address": str(agent.ip_address) if agent.ip_address else "N/A",
        })

    return PolicyPreviewTargets(agent_count=len(agents), sample_list=sample_list)


async def _policy_to_detail(policy: Policy) -> PolicyDetail:
    """Convert Policy model to PolicyDetail schema."""
    return PolicyDetail(
        id=str(policy.id),
        name=policy.name,
        description=policy.description,
        policy_type=policy.policy_type,
        policy_type_label=POLICY_TYPE_LABELS.get(policy.policy_type),
        version=policy.version,
        rules=policy.rules,
        status=policy.status,
        status_label=STATUS_LABELS.get(policy.status),
        target_type=policy.target_type,
        target_value=policy.target_value,
        priority=policy.priority,
        effective_start=policy.effective_start,
        effective_end=policy.effective_end,
        is_template=policy.is_template,
        deployed_version=policy.deployed_version,
        last_deployed_at=policy.last_deployed_at,
        created_at=policy.created_at,
        updated_at=policy.updated_at,
    )