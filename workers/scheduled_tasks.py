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
    # Auto-recovery: Check every 30 minutes
    "auto-recover-pipelines": {
        "task": "workers.scheduled_tasks.auto_recover_failed_pipelines",
        "schedule": crontab(minute="*/30"),
        "options": {"queue": "maintenance"},
    },
}


@shared_task(
    name="workers.scheduled_tasks.scheduled_discovery",
    bind=True,
    max_retries=2,
    default_retry_delay=300,
)
def scheduled_discovery(self) -> dict[str, Any]:
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


@shared_task(
    name="workers.scheduled_tasks.process_pending_followups",
    bind=True,
    max_retries=2,
    default_retry_delay=120,
)
def process_pending_followups(self) -> dict[str, Any]:
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
            leads = await lead_repo.find_by_statuses(
                [LeadStatus.OUTREACH_SENT, LeadStatus.IN_SEQUENCE],
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


@shared_task(
    name="workers.scheduled_tasks.generate_daily_report",
    bind=True,
    max_retries=2,
    default_retry_delay=300,
)
def generate_daily_report(self) -> dict[str, Any]:
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


@shared_task(
    name="workers.scheduled_tasks.cleanup_old_data",
    bind=True,
    max_retries=1,
    default_retry_delay=600,
)
def cleanup_old_data(
    self,
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


@shared_task(
    name="workers.scheduled_tasks.health_check",
    bind=True,
    max_retries=1,
    default_retry_delay=30,
)
def health_check(self) -> dict[str, Any]:
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


@shared_task(
    name="workers.scheduled_tasks.check_stale_leads",
    bind=True,
    max_retries=2,
    default_retry_delay=120,
)
def check_stale_leads(
    self,
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
                LeadStatus.LEAD_FOUND,
                LeadStatus.ENRICHED,
                LeadStatus.OUTREACH_SENT,
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


@shared_task(
    name="workers.scheduled_tasks.retry_failed_tasks",
    bind=True,
    max_retries=1,
    default_retry_delay=60,
)
def retry_failed_tasks(self) -> dict[str, Any]:
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


@shared_task(
    name="workers.scheduled_tasks.update_rate_limits",
    bind=True,
    max_retries=2,
    default_retry_delay=60,
)
def update_rate_limits(self) -> dict[str, Any]:
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


@shared_task(
    name="workers.scheduled_tasks.auto_recover_failed_pipelines",
    bind=True,
    max_retries=1,
    default_retry_delay=120,
)
def auto_recover_failed_pipelines(
    self,
    max_age_hours: int = 24,
    max_retries_per_run: int = 3,
) -> dict[str, Any]:
    """Auto-recover failed pipeline runs.

    Finds failed runs and attempts to retry them automatically.
    Only retries runs that haven't exceeded max retries.

    Args:
        max_age_hours: Only recover runs newer than this
        max_retries_per_run: Max auto-retry attempts per run

    Returns:
        Recovery results
    """
    import asyncio

    async def _run() -> dict[str, Any]:
        from app.observability import get_lead_traces, retry_pipeline_run
        from app.storage.database import async_session_factory
        from app.storage.redis import get_redis
        from app.storage.repositories.lead_repo import LeadRepository

        recovered = 0
        failed = 0
        skipped = 0

        async with async_session_factory() as db:
            lead_repo = LeadRepository(db)

            # Get leads with recent activity
            from app.models.enums import LeadStatus

            active_statuses = [
                LeadStatus.LEAD_FOUND,
                LeadStatus.ENRICHED,
                LeadStatus.SCORED,
                LeadStatus.EMAIL_READY,
            ]

            leads = await lead_repo.find_by_statuses(active_statuses, limit=100)

            for lead in leads:
                lead_id = str(lead.id)

                # Get recent traces
                traces = await get_lead_traces(lead_id, limit=5)

                for trace in traces:
                    if trace.status != "failed":
                        continue

                    # Check retry count
                    redis = await get_redis()
                    retry_key = f"auto_recovery_count:{lead_id}:{trace.run_id}"
                    retry_count = await redis.get(retry_key)
                    retry_count = int(retry_count) if retry_count else 0

                    if retry_count >= max_retries_per_run:
                        skipped += 1
                        continue

                    # Attempt recovery
                    try:
                        result = await retry_pipeline_run(lead_id, trace.run_id)

                        if result.get("success"):
                            recovered += 1
                            # Increment retry count
                            await redis.incr(retry_key)
                            await redis.expire(retry_key, 86400 * 7)  # 7 days TTL

                            logger.info(
                                f"[AUTO-RECOVERY] Recovered | lead_id={lead_id} | "
                                f"old_run_id={trace.run_id} | "
                                f"new_run_id={result.get('new_run_id')}"
                            )
                        else:
                            failed += 1

                    except Exception as e:
                        failed += 1
                        logger.error(
                            f"[AUTO-RECOVERY] Failed | lead_id={lead_id} | "
                            f"run_id={trace.run_id} | error={e}"
                        )

        logger.info(
            f"[AUTO-RECOVERY] Complete | recovered={recovered} | "
            f"failed={failed} | skipped={skipped}"
        )

        return {
            "recovered": recovered,
            "failed": failed,
            "skipped": skipped,
        }

    return asyncio.get_event_loop().run_until_complete(_run())
