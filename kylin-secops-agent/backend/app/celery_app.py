"""Celery application for async task processing."""

from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "kylin_secops",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "app.celery_tasks",
    ],
)

# Celery configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes
    task_soft_time_limit=25 * 60,  # 25 minutes
    worker_max_tasks_per_child=100,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_default_queue="default",
    task_queues={
        "default": {"exchange": "default", "routing_key": "default"},
        "heartbeat": {"exchange": "heartbeat", "routing_key": "heartbeat"},
        "alerts": {"exchange": "alerts", "routing_key": "alerts"},
        "policies": {"exchange": "policies", "routing_key": "policies"},
    },
    task_routes={
        "app.celery_tasks.heartbeat.*": {"queue": "heartbeat"},
        "app.celery_tasks.alerts.*": {"queue": "alerts"},
        "app.celery_tasks.policies.*": {"queue": "policies"},
    },
)


@celery_app.task(bind=True, name="health_check")
def health_check(self):
    """Celery health check task."""
    return {"status": "ok", "task_id": self.request.id}


@celery_app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    """Setup periodic tasks."""
    # Check offline agents every 60 seconds
    sender.add_periodic_task(
        60.0,
        check_offline_agents.s(),
        name="check-offline-agents",
    )


@celery_app.task(bind=True, name="check_offline_agents")
def check_offline_agents(self):
    """Check and mark offline agents."""
    # This would be implemented with async DB access
    pass