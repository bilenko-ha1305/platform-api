"""APScheduler setup and daily report job."""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime, timedelta
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from api.db.dao.integration_dao import IntegrationDAO
from api.db.dao.org_dao import OrgDAO
from api.db.dao.scheduled_report_dao import ScheduledReportDAO
from api.services.ai.reporter import run_report
from api.services.notifications import slack_service
from api.settings import settings

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


async def _run_due_reports(session_factory: async_sessionmaker[AsyncSession]) -> None:
    """Check for due scheduled reports and send them.

    Runs every minute. For each enabled schedule where the current UTC
    hour:minute matches and no report has been sent today, generate a
    report and post it to Slack.

    :param session_factory: Async session factory from app.state.
    """
    now = datetime.now(tz=UTC)

    async with session_factory() as session:
        await session.begin()
        sched_dao = ScheduledReportDAO(session=session)
        int_dao = IntegrationDAO(session=session)
        org_dao = OrgDAO(session=session)

        schedules = await sched_dao.list_enabled()
        for schedule in schedules:
            if schedule.hour_utc != now.hour or schedule.minute_utc != now.minute:
                continue

            already_sent = (
                schedule.last_sent_at is not None
                and schedule.last_sent_at.replace(tzinfo=UTC).date() == now.date()
            )
            if already_sent:
                continue

            org = await org_dao.get_by_id(schedule.org_id)
            if org is None:
                continue

            integrations = await int_dao.get_decrypted(schedule.org_id)
            slack_creds = integrations.get("slack")
            if not slack_creds or not slack_creds.get("webhook_url"):
                logger.warning("Org %s has a schedule but no Slack webhook", schedule.org_id)
                continue

            date_to: date = now.date() - timedelta(days=1)
            date_from: date = date_to - timedelta(days=schedule.lookback_days - 1)

            logger.info(
                "Sending scheduled report for org %s (%s → %s)",
                schedule.org_id,
                date_from,
                date_to,
            )

            try:
                report = await run_report(
                    date_from=str(date_from),
                    date_to=str(date_to),
                    integrations=integrations,
                    model=settings.ai_model,
                    api_key=settings.ai_api_key,
                    base_url=settings.ai_base_url,
                    business_profile=org.business_profile,
                )
                await slack_service.post_report(
                    webhook_url=slack_creds["webhook_url"],
                    report=report,
                    date_from=str(date_from),
                    date_to=str(date_to),
                )
                await sched_dao.update_last_sent(schedule.id)
                await session.commit()
                logger.info("Scheduled report sent for org %s", schedule.org_id)
            except Exception:
                logger.exception("Failed to send scheduled report for org %s", schedule.org_id)


def start_scheduler(session_factory: async_sessionmaker[AsyncSession]) -> None:
    """Start the APScheduler and register the minute-tick job.

    :param session_factory: SQLAlchemy async session factory.
    """
    global _scheduler  # noqa: PLW0603
    _scheduler = AsyncIOScheduler()
    _scheduler.add_job(
        _run_due_reports,
        trigger="cron",
        minute="*",
        kwargs={"session_factory": session_factory},
        id="daily_reports",
        replace_existing=True,
        misfire_grace_time=30,
    )
    _scheduler.start()
    logger.info("Scheduler started")


def stop_scheduler() -> None:
    """Shut down the scheduler gracefully."""
    global _scheduler  # noqa: PLW0603
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")
    _scheduler = None


def get_scheduler_info() -> dict[str, Any]:
    """Return basic scheduler status (for monitoring).

    :return: Dict with running flag and job count.
    """
    if _scheduler is None:
        return {"running": False, "jobs": 0}
    return {"running": _scheduler.running, "jobs": len(_scheduler.get_jobs())}
