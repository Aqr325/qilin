"""API V1 router - combine all route modules."""

from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.agents import router as agent_comm_router
from app.api.v1.agents import mgmt_router as agent_mgmt_router
from app.api.v1.alerts import router as alerts_router
from app.api.v1.policies import router as policies_router
from app.api.v1.dashboard import router as dashboard_router
from app.api.v1.system import router as system_router
from app.api.v1.ai import router as ai_router
from app.api.v1.local_status import router as local_status_router

api_router = APIRouter()

api_router.include_router(auth_router)
api_router.include_router(agent_comm_router)
api_router.include_router(agent_mgmt_router)
api_router.include_router(alerts_router)
api_router.include_router(policies_router)
api_router.include_router(dashboard_router)
api_router.include_router(system_router)
api_router.include_router(ai_router)
api_router.include_router(local_status_router)

__all__ = ["api_router"]