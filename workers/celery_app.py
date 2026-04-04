"""Celery application configuration."""

from celery import Celery

from app.config import settings

celery_app = Celery(
    "otclick_worker",
    broker=settings.celery_broker_url,
    backend=settings.redis_url,
)

# Celery configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=600,  # 10 minutes
    task_soft_time_limit=540,  # 9 minutes
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
)

# Auto-discover tasks from workers module
celery_app.autodiscover_tasks(["workers"])
