"""Workers module for Celery tasks."""

from workers.celery_app import celery_app

# Import tasks to register them with Celery
from workers import analysis_tasks, discovery_tasks, outreach_tasks, scheduled_tasks

__all__ = [
    "celery_app",
    "discovery_tasks",
    "outreach_tasks",
    "analysis_tasks",
    "scheduled_tasks",
]
