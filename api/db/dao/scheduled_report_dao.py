"""Scheduled report schedule DAO."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import Depends
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from api.db.dependencies import get_db_session
from api.db.models.scheduled_report_model import ScheduledReport


class ScheduledReportDAO:
    """Provides access to the scheduled_reports table."""

    def __init__(self, session: AsyncSession = Depends(get_db_session)) -> None:
        self.session = session

    async def upsert(
        self,
        org_id: uuid.UUID,
        enabled: bool,
        hour_utc: int,
        minute_utc: int,
        lookback_days: int,
    ) -> ScheduledReport:
        """Create or update the schedule for an organisation.

        :param org_id: Organisation UUID.
        :param enabled: Whether the schedule is active.
        :param hour_utc: Hour of day (0-23) to send the report.
        :param minute_utc: Minute (0-59) to send the report.
        :param lookback_days: Days of history to include in the report.
        :return: Persisted ScheduledReport row.
        """
        values: dict[str, Any] = {
            "org_id": org_id,
            "enabled": enabled,
            "hour_utc": hour_utc,
            "minute_utc": minute_utc,
            "lookback_days": lookback_days,
        }
        stmt = (
            insert(ScheduledReport)
            .values(**values)
            .on_conflict_do_update(
                constraint="scheduled_reports_org_id_key",
                set_={
                    "enabled": enabled,
                    "hour_utc": hour_utc,
                    "minute_utc": minute_utc,
                    "lookback_days": lookback_days,
                    "updated_at": func_now(),
                },
            )
            .returning(ScheduledReport)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def get_for_org(self, org_id: uuid.UUID) -> ScheduledReport | None:
        """Fetch the schedule for an organisation.

        :param org_id: Organisation UUID.
        :return: ScheduledReport or None.
        """
        result = await self.session.execute(
            select(ScheduledReport).where(ScheduledReport.org_id == org_id)
        )
        return result.scalar_one_or_none()

    async def list_enabled(self) -> list[ScheduledReport]:
        """Return all enabled schedules across all organisations.

        :return: List of enabled ScheduledReport rows.
        """
        result = await self.session.execute(
            select(ScheduledReport).where(ScheduledReport.enabled.is_(True))
        )
        return list(result.scalars().all())

    async def update_last_sent(self, schedule_id: uuid.UUID) -> None:
        """Record that a report was just sent for this schedule.

        :param schedule_id: ScheduledReport primary key.
        """
        await self.session.execute(
            update(ScheduledReport)
            .where(ScheduledReport.id == schedule_id)
            .values(last_sent_at=datetime.now(tz=UTC))
        )


def func_now() -> datetime:
    """Return current UTC datetime (used as onupdate value in upsert)."""
    return datetime.now(tz=UTC)
