"""Scheduled Celery tasks (Celery Beat).

Периодические задачи для автоматизации процессов.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

# Python 3.10 compatibility
UTC = timezone.utc

from celery import shared_task
from celery.schedules import crontab

from workers.celery_app import celery_app

logger = logging.getLogger(__name__)


# Celery Beat schedule
celery_app.conf.beat_schedule = {
    # Discovery: Run every 4 hours during business hours
    "discover-new-employers": {
        "task": "workers.scheduled_tasks.scheduled_discovery",
        "schedule": crontab(minute=0, hour="9,13,17"),  # 9:00, 13:00, 17:00
        "options": {"queue": "discovery"},
    },
    # Follow-ups: Check every hour
    "process-pending-followups": {
        "task": "workers.scheduled_tasks.process_pending_followups",
        "schedule": crontab(minute=0),  # Every hour
        "options": {"queue": "outreach"},
    },
    # Analytics: Generate daily report
    "daily-analytics-report": {
        "task": "workers.scheduled_tasks.generate_daily_report",
        "schedule": crontab(minute=0, hour=8),  # 8:00 AM
        "options": {"queue": "analytics"},
    },
    # Cleanup: Run daily at midnight
    "cleanup-old-data": {
        "task": "workers.scheduled_tasks.cleanup_old_data",
        "schedule": crontab(minute=0, hour=0),  # Midnight
        "options": {"queue": "maintenance"},
    },
    # Health check: Every 5 minutes
    "health-check": {
        "task": "workers.scheduled_tasks.health_check",
        "schedule": crontab(minute="*/5"),
        "options": {"queue": "maintenance"},
    },
    # Stale leads: Check every 6 hours
    "check-stale-leads": {
        "task": "workers.scheduled_tasks.check_stale_leads",
        "schedule": crontab(minute=0, hour="*/6"),
        "options": {"queue": "maintenance"},
    },
}


@shared_task(name="workers.scheduled_tasks.scheduled_discovery")
def scheduled_discovery() -> dict[str, Any]:
    """Run scheduled employer discovery.

    Returns:
        Discovery results
    """
    from workers.discovery_tasks import batch_discover

    logger.info("Starting scheduled discovery")

    result = batch_discover.delay(
        industries=["retail", "logistics", "horeca", "manufacturing"],
        regions=["Москва", "Санкт-Петербург", "Новосибирск", "Екатеринбург"],
        limit_per_industry=50,
    )

    return {
        "task_id": result.id,
        "started_at": datetime.now(UTC).isoformat(),
    }


@shared_task(name="workers.scheduled_tasks.process_pending_followups")
def process_pending_followups() -> dict[str, Any]:
    """Process pending follow-up emails.

    Returns:
        Processing results
    """
    import asyncio

    async def _run() -> dict[str, Any]:
        from app.models.enums import LeadStatus
        from app.storage.database import async_session_factory
        from app.storage.repositories.lead_repo import LeadRepository

        async with async_session_factory() as db:
            lead_repo = LeadRepository(db)

            # Find leads in outreach that need follow-up
            leads = await lead_repo.find_by_status(
                LeadStatus.OUTREACH_STARTED,
                limit=100,
            )

            followups_sent = 0

            for lead in leads:
                # Check if follow-up is due
                # This would check the email history and timing
                # For now, just log
                pass

            logger.info(f"Processed pending followups: {followups_sent} sent")

            return {
                "leads_checked": len(leads),
                "followups_sent": followups_sent,
            }

    return asyncio.get_event_loop().run_until_complete(_run())


@shared_task(name="workers.scheduled_tasks.generate_daily_report")
def generate_daily_report() -> dict[str, Any]:
    """Generate daily analytics report.

    Returns:
        Report summary
    """
    import asyncio

    async def _run() -> dict[str, Any]:
        from app.services.analytics_service import AnalyticsService
        from app.storage.database import async_session_factory

        async with async_session_factory() as db:
            analytics = AnalyticsService(db=db)

            # Get yesterday's date range
            today = datetime.now(UTC).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            yesterday = today - timedelta(days=1)

            # Get metrics
            funnel = await analytics.get_funnel_metrics(
                start_date=yesterday,
                end_date=today,
            )

            email_perf = await analytics.get_email_performance(
                start_date=yesterday,
                end_date=today,
            )

            report = {
                "date": yesterday.date().isoformat(),
                "funnel": {
                    "discovered": funnel.discovered,
                    "enriched": funnel.enriched,
                    "scored": funnel.scored,
                    "qualified": funnel.qualified,
                    "outreach_started": funnel.outreach_started,
                    "replied": funnel.replied,
                    "interested": funnel.interested,
                    "handed_off": funnel.handed_off,
                    "converted": funnel.converted,
                },
                "email_performance": {
                    "sent": email_perf.total_sent,
                    "delivered": email_perf.total_delivered,
                    "opened": email_perf.total_opened,
                    "clicked": email_perf.total_clicked,
                    "replied": email_perf.total_replied,
                    "bounced": email_perf.total_bounced,
                    "open_rate": email_perf.open_rate,
                    "click_rate": email_perf.click_rate,
                    "reply_rate": email_perf.reply_rate,
                },
            }

            # TODO: Send report via Slack or email

            logger.info(f"Generated daily report for {yesterday.date()}")

            return report

    return asyncio.get_event_loop().run_until_complete(_run())


@shared_task(name="workers.scheduled_tasks.cleanup_old_data")
def cleanup_old_data(
    retention_days: int = 90,
) -> dict[str, Any]:
    """Clean up old data beyond retention period.

    Args:
        retention_days: Days to retain data

    Returns:
        Cleanup results
    """
    import asyncio

    async def _run() -> dict[str, Any]:
        from app.storage.database import async_session_factory

        cutoff_date = datetime.now(UTC) - timedelta(days=retention_days)

        async with async_session_factory() as db:
            # Clean up old events
            # Clean up processed emails older than retention
            # Archive converted/lost leads

            # For now, just log
            logger.info(
                f"Cleanup task: would clean data older than {cutoff_date.date()}"
            )

            return {
                "cutoff_date": cutoff_date.isoformat(),
                "events_deleted": 0,
                "emails_archived": 0,
                "leads_archived": 0,
            }

    return asyncio.get_event_loop().run_until_complete(_run())


@shared_task(name="workers.scheduled_tasks.health_check")
def health_check() -> dict[str, Any]:
    """Perform system health check.

    Returns:
        Health status
    """
    import asyncio

    async def _run() -> dict[str, Any]:
        from sqlalchemy import text

        from app.storage.database import async_session_factory
        from app.storage.redis import get_redis

        health = {
            "timestamp": datetime.now(UTC).isoformat(),
            "database": "unknown",
            "redis": "unknown",
            "celery": "ok",
        }

        # Check database
        try:
            async with async_session_factory() as db:
                await db.execute(text("SELECT 1"))
            health["database"] = "ok"
        except Exception as e:
            health["database"] = f"error: {e}"

        # Check Redis
        try:
            redis = await get_redis()
            await redis.ping()
            health["redis"] = "ok"
        except Exception as e:
            health["redis"] = f"error: {e}"

        # Log if any issues
        if health["database"] != "ok" or health["redis"] != "ok":
            logger.warning(f"Health check issues: {health}")
        else:
            logger.debug("Health check passed")

        return health

    return asyncio.get_event_loop().run_until_complete(_run())


@shared_task(name="workers.scheduled_tasks.check_stale_leads")
def check_stale_leads(
    stale_hours: int = 48,
) -> dict[str, Any]:
    """Check for stale leads that need attention.

    Args:
        stale_hours: Hours after which lead is considered stale

    Returns:
        Check results
    """
    import asyncio

    async def _run() -> dict[str, Any]:
        from app.models.enums import LeadStatus
        from app.storage.database import async_session_factory
        from app.storage.repositories.lead_repo import LeadRepository

        cutoff = datetime.now(UTC) - timedelta(hours=stale_hours)

        async with async_session_factory() as db:
            lead_repo = LeadRepository(db)

            # Find stale leads
            stale_counts = {}

            for status in [
                LeadStatus.DISCOVERED,
                LeadStatus.ENRICHED,
                LeadStatus.OUTREACH_STARTED,
            ]:
                leads = await lead_repo.find_stale(
                    status=status,
                    older_than=cutoff,
                )
                stale_counts[status.value] = len(leads)

            total_stale = sum(stale_counts.values())

            if total_stale > 0:
                logger.warning(f"Found {total_stale} stale leads: {stale_counts}")
            else:
                logger.debug("No stale leads found")

            return {
                "stale_hours": stale_hours,
                "cutoff": cutoff.isoformat(),
                "stale_counts": stale_counts,
                "total_stale": total_stale,
            }

    return asyncio.get_event_loop().run_until_complete(_run())


@shared_task(name="workers.scheduled_tasks.retry_failed_tasks")
def retry_failed_tasks() -> dict[str, Any]:
    """Retry failed tasks that can be retried.

    Returns:
        Retry results
    """
    # This would inspect the Celery task results and retry
    # failed tasks that haven't exceeded max retries

    logger.info("Checking for failed tasks to retry")

    return {
        "tasks_retried": 0,
        "tasks_abandoned": 0,
    }


@shared_task(name="workers.scheduled_tasks.update_rate_limits")
def update_rate_limits() -> dict[str, Any]:
    """Update rate limit counters (reset daily limits).

    Returns:
        Update results
    """
    import asyncio

    async def _run() -> dict[str, Any]:
        from app.storage.redis import get_redis

        redis = await get_redis()

        # Find and delete expired rate limit keys
        # Keys pattern: rate_limit:*:YYYY-MM-DD
        yesterday = (datetime.now(UTC) - timedelta(days=1)).strftime("%Y-%m-%d")
        pattern = f"rate_limit:*:{yesterday}"

        # Scan and delete old keys
        deleted = 0
        async for key in redis.scan_iter(pattern):
            await redis.delete(key)
            deleted += 1

        logger.info(f"Cleaned up {deleted} expired rate limit keys")

        return {
            "keys_deleted": deleted,
            "pattern": pattern,
        }

    return asyncio.get_event_loop().run_until_complete(_run())
