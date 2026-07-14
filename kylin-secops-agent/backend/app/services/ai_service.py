"""AI service: natural language query, alert analysis, playbook generation."""

import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.ai import AiConversation, AiModelConfig
from app.core.security import decrypt_api_key, encrypt_api_key

import logging as _ai_log
import re as _re

_LOGGER = _ai_log.getLogger(__name__)
_API_KEY_RE = _re.compile(
    r"(?i)(Bearer\s+[A-Za-z0-9._\-]+|sk-[A-Za-z0-9]{8,}|"
    r"x-api-key[=:\s]+[^\s,\"]+|api[_-]?key[=:\s]+[^\s,\"]+)"
)


def _redact(text: str) -> str:
    """Strip credentials/keys from a string before logging."""
    return _API_KEY_RE.sub("***", text or "")


def _safe_ai_error(
    status: Optional[int] = None,
    raw_detail: str = "",
    exc: Optional[Exception] = None,
) -> str:
    """Return a generic, non-leaking error message; log full detail server-side."""
    if exc is not None:
        _LOGGER.exception("AI model call failed: %s", _redact(str(exc)))
    else:
        _LOGGER.error("AI model call HTTP %s: %s", status, _redact(str(raw_detail)))
    return "模型调用失败，请联系管理员查看后端日志"
from app.schemas.ai import (
    AIFeedbackRequest,
    AIPlaybookResponse,
    AIQueryRequest,
    AIQueryResponse,
    AiModelTestRequest,
    AiModelTestResponse,
    AISuggestion,
    AiModelConfig as AiModelConfigSchema,
    AiModelConfigCreate,
    AiModelConfigUpdate,
    ConversationDetail,
    ConversationSummary,
    PlaybookStep,
)
from app.schemas.common import Page


async def query(
    db: AsyncSession,
    req: AIQueryRequest,
    user: dict,
) -> AIQueryResponse:
    """Process natural language query using configured model."""
    conv_id = str(uuid.uuid4())
    msg_id = str(uuid.uuid4())

    # Call configured model API (returns answer text AND the real model name used)
    answer, model_name = await _call_model_api(db, req, user["id"])
    token_usage = len(req.question) + len(answer) if answer else 150

    # Save conversation
    conv = AiConversation(
        id=uuid.UUID(conv_id),
        user_id=uuid.UUID(user["id"]),
        title=req.question[:100],
        messages=[
            {"role": "user", "content": req.question, "id": msg_id},
            {"role": "assistant", "content": answer, "id": str(uuid.uuid4())},
        ],
        context={"timezone": req.timezone or "Asia/Shanghai"},
        model_name=model_name,
        token_usage=token_usage,
    )
    if req.context_alert_id:
        try:
            conv.related_alert_id = uuid.UUID(req.context_alert_id)
        except (ValueError, AttributeError):
            raise HTTPException(
                status_code=400, detail="非法的 context_alert_id"
            )
    db.add(conv)
    await db.flush()

    return AIQueryResponse(
        conversation_id=conv_id,
        message_id=msg_id,
        answer=answer,
        data_sources=[],
        suggested_actions=[],
        token_usage=token_usage,
    )


async def _call_model_api(
    db: AsyncSession,
    req: AIQueryRequest,
    user_id: str,
) -> tuple:
    """Call the configured model API. Returns (answer, model_name)."""
    import uuid
    model_name = "default"
    try:
        stmt = select(AiModelConfig).where(
            AiModelConfig.user_id == uuid.UUID(user_id),
            AiModelConfig.is_active == 1,
            AiModelConfig.is_default == 1,
        )
        result = await db.execute(stmt)
        model_config = result.scalar_one_or_none()

        if not model_config:
            return "尚未配置默认模型，暂无法回答。请先到「模型配置」中设置默认模型。", model_name

        provider = model_config.provider.lower()
        api_url = model_config.api_url or ""
        api_key = decrypt_api_key(model_config.api_key) if model_config.api_key else ""
        model_name = model_config.model or ""

        # Validate required fields
        if not api_url:
            return "模型调用失败：API 地址未配置，请先到「模型配置」中填写 API 地址。", model_name
        if not model_name:
            return "模型调用失败：模型标识未配置，请先到「模型配置」中填写模型标识。", model_name
        if api_key == "":
            return "模型调用失败：API Key 未配置，请先到「模型配置」中填写 API Key。", model_name

        if provider in ("openai", "custom"):
            import aiohttp
            url = api_url.rstrip("/") + "/chat/completions"
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            payload = {
                "model": model_name,
                "messages": [
                    {"role": "system", "content": model_config.system_prompt or "你是一个安全运维助手。"},
                    {"role": "user", "content": req.question},
                ],
                "temperature": model_config.temperature,
                "max_tokens": model_config.max_tokens,
            }
            timeout = aiohttp.ClientTimeout(total=30)
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, headers=headers, timeout=timeout) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data.get("choices", [{}])[0].get("message", {}).get("content", "请求成功但未返回内容"), model_name
                    else:
                        try:
                            error_data = await resp.json()
                            detail = error_data.get("error", {}).get("message", str(error_data))
                        except Exception:
                            detail = await resp.text() if resp.headers.get("content-type", "").startswith("text") else ""
                        return _safe_ai_error(status=resp.status, raw_detail=detail), model_name

        elif provider == "anthropic":
            import aiohttp
            url = api_url.rstrip("/") + "/messages"
            headers = {"x-api-key": api_key, "anthropic-version": "2023-06-01", "Content-Type": "application/json"}
            payload = {
                "model": model_name,
                "max_tokens": model_config.max_tokens,
                "messages": [{"role": "user", "content": req.question}],
            }
            timeout = aiohttp.ClientTimeout(total=30)
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, headers=headers, timeout=timeout) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data.get("content", [{}])[0].get("text", "请求成功但未返回内容"), model_name
                    else:
                        try:
                            error_data = await resp.json()
                            detail = error_data.get("error", {}).get("message", str(error_data))
                        except Exception:
                            detail = await resp.text() if resp.headers.get("content-type", "").startswith("text") else ""
                        return _safe_ai_error(status=resp.status, raw_detail=detail), model_name

        elif provider == "ollama":
            import aiohttp
            url = api_url.rstrip("/") + "/api/chat"
            payload = {
                "model": model_name,
                "messages": [
                    {"role": "system", "content": model_config.system_prompt or "你是一个安全运维助手。"},
                    {"role": "user", "content": req.question},
                ],
                "stream": False,
            }
            timeout = aiohttp.ClientTimeout(total=30)
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=timeout) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data.get("message", {}).get("content", "请求成功但未返回内容"), model_name
                    else:
                        return f"模型调用失败 (HTTP {resp.status})", model_name

        else:
            return f"不支持的提供商: {provider}", model_name

    except Exception as e:
        return _safe_ai_error(exc=e), model_name


# Provider default base URLs (when api_url not given)
_PROVIDER_DEFAULT_URL = {
    "openai": "https://api.openai.com/v1",
    "anthropic": "https://api.anthropic.com/v1",
    "ollama": "http://localhost:11434/v1",
    "custom": "",
}


async def test_model_config(
    db: AsyncSession,
    req: "AiModelTestRequest",
    user_id: str,
) -> dict:
    """Probe a model provider to verify connectivity / key / model.

    Uses a saved config (by config_id) or inline temporary fields. Returns a
    result dict: {ok, message, latency_ms, model}.
    """
    if req.config_id:
        stmt = select(AiModelConfig).where(
            AiModelConfig.id == uuid.UUID(req.config_id),
            AiModelConfig.user_id == uuid.UUID(user_id),
        )
        cfg = (await db.execute(stmt)).scalar_one_or_none()
        if not cfg:
            return {"ok": False, "message": "模型配置不存在或无权限", "latency_ms": 0, "model": None}
        provider = cfg.provider
        model = cfg.model
        api_url = cfg.api_url or _PROVIDER_DEFAULT_URL.get(cfg.provider.lower(), "")
        api_key = decrypt_api_key(cfg.api_key) if cfg.api_key else ""
    else:
        if not req.provider or not req.model:
            return {"ok": False, "message": "请提供 provider 与 model", "latency_ms": 0, "model": None}
        provider = req.provider
        model = req.model
        api_url = req.api_url or _PROVIDER_DEFAULT_URL.get(req.provider.lower(), "")
        api_key = req.api_key or ""

    if not api_url and provider == "custom":
        return {"ok": False, "message": "自定义提供商必须填写 API 地址", "latency_ms": 0, "model": model}

    ok, message, latency = await _probe_provider(provider, api_url, api_key, model)
    return {"ok": ok, "message": message, "latency_ms": latency, "model": model}


async def _probe_provider(
    provider: str, api_url: str, api_key: str, model: str,
) -> tuple:
    """Send a minimal request to the provider. Returns (ok, message, latency_ms)."""
    import aiohttp

    provider = (provider or "").lower()
    api_url = (api_url or "").rstrip("/")
    if not api_url:
        return False, f"未配置 API 地址（{provider} 需要显式地址）", 0
    if not model:
        return False, "未配置模型标识", 0

    test_prompt = "ping"
    start = time.perf_counter()
    timeout = aiohttp.ClientTimeout(total=15)
    try:
        if provider in ("openai", "custom"):
            url = api_url + "/chat/completions"
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            payload = {
                "model": model,
                "messages": [{"role": "user", "content": test_prompt}],
                "max_tokens": 8,
                "temperature": 0,
            }
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, headers=headers, timeout=timeout) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                        return True, f"连接成功，模型返回: {content[:40]!r}", int((time.perf_counter() - start) * 1000)
                    detail = await _read_error(resp)
                    return False, f"模型返回 HTTP {resp.status}: {detail}", int((time.perf_counter() - start) * 1000)

        elif provider == "anthropic":
            url = api_url + "/messages"
            headers = {"x-api-key": api_key, "anthropic-version": "2023-06-01", "Content-Type": "application/json"}
            payload = {"model": model, "max_tokens": 8, "messages": [{"role": "user", "content": test_prompt}]}
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, headers=headers, timeout=timeout) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        content = data.get("content", [{}])[0].get("text", "")
                        return True, f"连接成功，模型返回: {content[:40]!r}", int((time.perf_counter() - start) * 1000)
                    detail = await _read_error(resp)
                    return False, f"模型返回 HTTP {resp.status}: {detail}", int((time.perf_counter() - start) * 1000)

        elif provider == "ollama":
            url = api_url + "/api/chat"
            payload = {
                "model": model,
                "messages": [{"role": "user", "content": test_prompt}],
                "stream": False,
                "options": {"num_predict": 8},
            }
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=timeout) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        content = data.get("message", {}).get("content", "")
                        return True, f"连接成功，模型返回: {content[:40]!r}", int((time.perf_counter() - start) * 1000)
                    detail = await _read_error(resp)
                    return False, f"模型返回 HTTP {resp.status}: {detail}", int((time.perf_counter() - start) * 1000)

        else:
            return False, f"不支持的提供商: {provider}", int((time.perf_counter() - start) * 1000)

    except aiohttp.ClientError as e:
        return False, f"连接失败: {str(e)}", int((time.perf_counter() - start) * 1000)
    except Exception as e:
        return False, f"测试异常: {str(e)}", int((time.perf_counter() - start) * 1000)


async def _read_error(resp) -> str:
    """Best-effort extraction of an error message from a provider error response."""
    try:
        error_data = await resp.json()
        if isinstance(error_data, dict):
            err = error_data.get("error")
            if isinstance(err, dict):
                return str(err.get("message", error_data))[:200]
            return str(err)[:200]
        return str(error_data)[:200]
    except Exception:
        try:
            return (await resp.text())[:200]
        except Exception:
            return ""


async def suggest(
    db: AsyncSession,
    alert_id: str,
    user: dict,
) -> AISuggestion:
    """Generate AI analysis suggestion for an alert."""
    return AISuggestion(
        alert_id=alert_id,
        verdict="needs_investigation",
        confidence=0.7,
        analysis="AI研判分析：该告警需要进一步调查。建议检查Agent日志和关联事件。",
        recommended_actions=[
            "检查Agent系统日志",
            "查看关联告警",
            "确认是否存在误报可能",
        ],
        related_alerts=[],
        mitre_mapping=None,
    )


async def generate_playbook(
    db: AsyncSession,
    alert_ids: List[str],
    scenario: Optional[str],
    user: dict,
) -> AIPlaybookResponse:
    """Generate incident response playbook."""
    return AIPlaybookResponse(
        steps=[
            PlaybookStep(
                order=1,
                action="分析告警详情",
                description=f"查看 {len(alert_ids)} 条告警的详细信息和关联事件",
                estimated_time_seconds=120,
            ),
            PlaybookStep(
                order=2,
                action="确认影响范围",
                description="确定受影响的Agent和系统",
                estimated_time_seconds=300,
            ),
            PlaybookStep(
                order=3,
                action="执行处置",
                description="根据告警类型执行相应处置动作",
                estimated_time_seconds=600,
            ),
            PlaybookStep(
                order=4,
                action="更新告警状态",
                description="将告警状态更新为已解决并添加处置备注",
                estimated_time_seconds=60,
            ),
        ],
        summary="标准告警处置流程",
        risk_level="medium",
    )


async def list_conversations(
    db: AsyncSession,
    user_id: str,
    page: int = 1,
    size: int = 20,
) -> Page[ConversationSummary]:
    """List AI conversation history."""
    from app.repositories.base import BaseRepository
    from sqlalchemy import desc, select, func

    repo = BaseRepository(AiConversation, db)
    query = select(AiConversation).where(AiConversation.user_id == uuid.UUID(user_id))

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    query = query.order_by(desc(AiConversation.updated_at)).offset((page - 1) * size).limit(size)
    result = await db.execute(query)
    convs = result.scalars().all()

    items = [
        ConversationSummary(
            id=str(c.id),
            title=c.title,
            message_count=len(c.messages) if c.messages else 0,
            last_message=c.messages[-1].get("content", "")[:100] if c.messages else None,
            related_alert_id=str(c.related_alert_id) if c.related_alert_id else None,
            token_usage=c.token_usage,
            created_at=c.created_at,
            updated_at=c.updated_at,
        )
        for c in convs
    ]
    return Page.create(items, total, page, size)


async def get_conversation(
    db: AsyncSession,
    conv_id: str,
    user: dict,
) -> ConversationDetail:
    """Get conversation detail."""
    from app.repositories.base import BaseRepository
    from sqlalchemy import select

    repo = BaseRepository(AiConversation, db)
    result = await db.execute(
        select(AiConversation).where(AiConversation.id == uuid.UUID(conv_id))
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="对话不存在")

    return ConversationDetail(
        id=str(conv.id),
        title=conv.title,
        messages=conv.messages or [],
        context=conv.context,
        related_alert_id=str(conv.related_alert_id) if conv.related_alert_id else None,
        feedback_score=conv.feedback_score,
        token_usage=conv.token_usage,
        model_name=conv.model_name,
        duration_ms=conv.duration_ms,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
    )


async def delete_conversation(db: AsyncSession, conv_id: str, operator: dict):
    """Delete a conversation."""
    from app.repositories.base import BaseRepository
    from sqlalchemy import select

    repo = BaseRepository(AiConversation, db)
    result = await db.execute(
        select(AiConversation).where(AiConversation.id == uuid.UUID(conv_id))
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="对话不存在")
    await db.delete(conv)
    await db.flush()


async def save_feedback(
    db: AsyncSession,
    req: AIFeedbackRequest,
    user: dict,
):
    """Save feedback for AI response."""
    from app.repositories.base import BaseRepository
    from sqlalchemy import select

    result = await db.execute(
        select(AiConversation).where(
            AiConversation.id == uuid.UUID(req.conversation_id),
            AiConversation.user_id == uuid.UUID(user["id"]),
        )
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="对话不存在")

    conv.feedback_score = req.rating
    conv.feedback_comment = req.comment
    await db.flush()


# ── Model Config CRUD ──

async def list_model_configs(db: AsyncSession, user_id: str) -> List[AiModelConfigSchema]:
    """List all model configs for a user."""
    from sqlalchemy import select, desc
    result = await db.execute(
        select(AiModelConfig)
        .where(AiModelConfig.user_id == uuid.UUID(user_id))
        .order_by(desc(AiModelConfig.is_default), desc(AiModelConfig.created_at))
    )
    configs = result.scalars().all()
    return [
        AiModelConfigSchema(
            id=str(c.id),
            name=c.name,
            provider=c.provider,
            model=c.model,
            api_url=c.api_url,
            temperature=c.temperature,
            max_tokens=c.max_tokens,
            system_prompt=c.system_prompt,
            is_active=bool(c.is_active),
            is_default=bool(c.is_default),
            has_api_key=bool(c.api_key and len(c.api_key) > 10),
            created_at=c.created_at,
            updated_at=c.updated_at,
        )
        for c in configs
    ]


async def get_model_config(
    db: AsyncSession, config_id: str, user_id: str,
) -> AiModelConfigSchema:
    """Get a single model config."""
    from sqlalchemy import select
    result = await db.execute(
        select(AiModelConfig).where(
            AiModelConfig.id == uuid.UUID(config_id),
            AiModelConfig.user_id == uuid.UUID(user_id),
        )
    )
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="模型配置不存在")
    return AiModelConfigSchema(
        id=str(config.id),
        name=config.name,
        provider=config.provider,
        model=config.model,
        api_url=config.api_url,
        temperature=config.temperature,
        max_tokens=config.max_tokens,
        system_prompt=config.system_prompt,
        is_active=bool(config.is_active),
        is_default=bool(config.is_default),
        has_api_key=bool(config.api_key and len(config.api_key) > 10),
        created_at=config.created_at,
        updated_at=config.updated_at,
    )


async def create_model_config(
    db: AsyncSession, req: AiModelConfigCreate, user_id: str,
) -> AiModelConfigSchema:
    """Create a new model config.

    Auto-default: if the user has no existing default config (or no configs at
    all), the new config is marked as default so chat can use it immediately.
    This also removes the dependency on the undefined `_unset_other_defaults`.
    """
    uid = uuid.UUID(user_id)

    existing = (
        await db.execute(select(AiModelConfig).where(AiModelConfig.user_id == uid))
    ).scalars().all()
    has_default = any(c.is_default == 1 for c in existing)
    make_default = bool(req.is_default) or not has_default

    # Clear any existing default flag so only one config stays default
    if make_default:
        await db.execute(
            AiModelConfig.__table__.update()
            .where(AiModelConfig.user_id == uid)
            .values(is_default=0)
        )

    # Build API URL defaults for known providers
    api_url = req.api_url
    if not api_url and req.provider == "openai":
        api_url = "https://api.openai.com/v1"
    elif not api_url and req.provider == "anthropic":
        api_url = "https://api.anthropic.com/v1"
    elif not api_url and req.provider == "ollama":
        api_url = _PROVIDER_DEFAULT_URL["ollama"]

    config = AiModelConfig(
        user_id=uid,
        name=req.name,
        provider=req.provider,
        model=req.model,
        api_url=api_url,
        api_key=encrypt_api_key(req.api_key) if req.api_key else None,
        temperature=req.temperature,
        max_tokens=req.max_tokens,
        system_prompt=req.system_prompt,
        is_active=1,
        is_default=1 if make_default else 0,
    )
    db.add(config)
    await db.flush()
    await db.refresh(config)

    return AiModelConfigSchema(
        id=str(config.id),
        name=config.name,
        provider=config.provider,
        model=config.model,
        api_url=config.api_url,
        temperature=config.temperature,
        max_tokens=config.max_tokens,
        system_prompt=config.system_prompt,
        is_active=bool(config.is_active),
        is_default=bool(config.is_default),
        has_api_key=bool(config.api_key and len(config.api_key) > 10),
        created_at=config.created_at,
        updated_at=config.updated_at,
    )


async def update_model_config(
    db: AsyncSession, config_id: str, req: AiModelConfigUpdate, user_id: str,
) -> AiModelConfigSchema:
    """Update a model config."""
    from sqlalchemy import select
    result = await db.execute(
        select(AiModelConfig).where(
            AiModelConfig.id == uuid.UUID(config_id),
            AiModelConfig.user_id == uuid.UUID(user_id),
        )
    )
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="模型配置不存在")

    if req.name is not None:
        config.name = req.name
    if req.provider is not None:
        config.provider = req.provider
    if req.model is not None:
        config.model = req.model
    if req.api_url is not None:
        config.api_url = req.api_url
    if req.api_key is not None:
        config.api_key = encrypt_api_key(req.api_key)
    if req.temperature is not None:
        config.temperature = req.temperature
    if req.max_tokens is not None:
        config.max_tokens = req.max_tokens
    if req.system_prompt is not None:
        config.system_prompt = req.system_prompt
    if req.is_active is not None:
        config.is_active = 1 if req.is_active else 0
    if req.is_default is not None and req.is_default:
        # Unset default from other configs
        await db.execute(
            AiModelConfig.__table__.update()
            .where(AiModelConfig.user_id == uuid.UUID(user_id))
            .values(is_default=0)
        )
        config.is_default = 1

    await db.flush()
    await db.refresh(config)

    return AiModelConfigSchema(
        id=str(config.id),
        name=config.name,
        provider=config.provider,
        model=config.model,
        api_url=config.api_url,
        temperature=config.temperature,
        max_tokens=config.max_tokens,
        system_prompt=config.system_prompt,
        is_active=bool(config.is_active),
        is_default=bool(config.is_default),
        has_api_key=bool(config.api_key and len(config.api_key) > 10),
        created_at=config.created_at,
        updated_at=config.updated_at,
    )


async def delete_model_config(db: AsyncSession, config_id: str, user_id: str):
    """Delete a model config."""
    from sqlalchemy import select
    result = await db.execute(
        select(AiModelConfig).where(
            AiModelConfig.id == uuid.UUID(config_id),
            AiModelConfig.user_id == uuid.UUID(user_id),
        )
    )
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="模型配置不存在")
    await db.delete(config)
    await db.flush()


async def set_default_model_config(
    db: AsyncSession, config_id: str, user_id: str,
) -> AiModelConfigSchema:
    """Set a model config as default."""
    from sqlalchemy import select
    result = await db.execute(
        select(AiModelConfig).where(
            AiModelConfig.id == uuid.UUID(config_id),
            AiModelConfig.user_id == uuid.UUID(user_id),
        )
    )
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="模型配置不存在")

    # Unset default from all other configs
    await db.execute(
        AiModelConfig.__table__.update()
        .where(AiModelConfig.user_id == uuid.UUID(user_id))
        .values(is_default=0)
    )
    config.is_default = 1
    await db.flush()
    await db.refresh(config)

    return AiModelConfigSchema(
        id=str(config.id),
        name=config.name,
        provider=config.provider,
        model=config.model,
        api_url=config.api_url,
        temperature=config.temperature,
        max_tokens=config.max_tokens,
        system_prompt=config.system_prompt,
        is_active=bool(config.is_active),
        is_default=bool(config.is_default),
        has_api_key=bool(config.api_key and len(config.api_key) > 10),
        created_at=config.created_at,
        updated_at=config.updated_at,
    )