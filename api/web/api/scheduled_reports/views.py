"""Scheduled report configuration endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from api.db.dao.scheduled_report_dao import ScheduledReportDAO
from api.enums import OrgRole
from api.web.api.scheduled_reports.schema import ScheduledReportDTO, ScheduledReportUpsertDTO
from api.web.dependencies.org import OrgContext, get_org_context

router = APIRouter()


@router.get("/me", response_model=ScheduledReportDTO | None)
async def get_schedule(
    ctx: OrgContext = Depends(get_org_context),
    dao: ScheduledReportDAO = Depends(),
) -> ScheduledReportDTO | None:
    """Return the scheduled report configuration for the current org.

    :param ctx: Resolved org context.
    :param dao: Injected ScheduledReportDAO.
    :return: ScheduledReportDTO or None if not configured.
    """
    row = await dao.get_for_org(ctx.org_id)
    if row is None:
        return None
    return ScheduledReportDTO.model_validate(row)


@router.put("/me", response_model=ScheduledReportDTO)
async def upsert_schedule(
    body: ScheduledReportUpsertDTO,
    ctx: OrgContext = Depends(get_org_context),
    dao: ScheduledReportDAO = Depends(),
) -> ScheduledReportDTO:
    """Create or update the daily report schedule (admin only).

    :param body: Schedule configuration.
    :param ctx: Resolved org context.
    :param dao: Injected ScheduledReportDAO.
    :raises HTTPException: 403 if caller is not admin.
    :return: Updated ScheduledReportDTO.
    """
    if ctx.role != OrgRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin access required")
    row = await dao.upsert(
        org_id=ctx.org_id,
        enabled=body.enabled,
        hour_utc=body.hour_utc,
        minute_utc=body.minute_utc,
        lookback_days=body.lookback_days,
    )
    return ScheduledReportDTO.model_validate(row)
