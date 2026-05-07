from __future__ import annotations

from celery import Celery

from app.core.config import settings


celery_app = Celery(
    "interview_crm",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.task_routes = {
    "app.worker.tasks.process_automation_job": {"queue": "crm_automations"},
}
