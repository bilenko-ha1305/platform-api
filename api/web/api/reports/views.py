"""Reports endpoints."""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncGenerator
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from api.db.dao.integration_dao import IntegrationDAO
from api.db.dao.investigation_dao import InvestigationDAO
from api.db.dao.org_dao import OrgDAO
from api.db.dao.report_dao import ReportDAO
from api.services.ai.reporter import stream_report
from api.settings import settings
from api.web.api.reports.schema import (
    ReportRequestDTO,
    ReportResultDTO,
    ReportSummaryDTO,
)
from api.web.api.shared import REPORT_COST, check_plan_credits
from api.web.dependencies.auth import verify_token
from api.web.dependencies.org import OrgContext, get_org_context

router = APIRouter()


@router.post("/stream")
async def stream_generate_report(
    body: ReportRequestDTO,
    user_payload: dict[str, Any] = Depends(verify_token),
    ctx: OrgContext = Depends(get_org_context),
    integration_dao: IntegrationDAO = Depends(),
    investigation_dao: InvestigationDAO = Depends(),
    report_dao: ReportDAO = Depends(),
    org_dao: OrgDAO = Depends(),
) -> StreamingResponse:
    """Stream a period report as Server-Sent Events.

    Events: status (progress), token (synthesis text), done (saved result).
    Costs REPORT_COST investigation credits.

    :param body: Date range for the report.
    :param user_payload: Decoded JWT claims.
    :param ctx: Resolved org context.
    :param integration_dao: Injected IntegrationDAO.
    :param investigation_dao: Injected InvestigationDAO (for credit counting).
    :param report_dao: Injected ReportDAO.
    :param org_dao: Injected OrgDAO for business profile.
    :raises HTTPException: 400 if no integrations; 402 if credit limit exceeded.
    :return: SSE StreamingResponse.
    """
    await check_plan_credits(
        ctx.org_id, ctx.plan, investigation_dao, report_dao, additional_cost=REPORT_COST
    )

    integrations = await integration_dao.get_decrypted(org_id=ctx.org_id)
    if not integrations:
        raise HTTPException(
            status_code=400,
            detail="Connect at least one integration before generating a report.",
        )

    org = await org_dao.get_by_id(ctx.org_id)
    business_profile = org.business_profile if org else None
    date_from_str = body.date_from.isoformat()
    date_to_str = body.date_to.isoformat()

    async def _generate() -> AsyncGenerator[str, None]:
        result_data: dict[str, Any] | None = None
        async for event in stream_report(
            date_from=date_from_str,
            date_to=date_to_str,
            integrations=integrations,
            model=settings.ai_model,
            api_key=settings.ai_api_key,
            base_url=settings.ai_base_url,
            business_profile=business_profile,
        ):
            if event["type"] == "result":
                result_data = event["data"]
            else:
                yield f"data: {json.dumps(event)}\n\n"

        if result_data is not None:
            sources_used: list[str] = result_data.pop("sources_used", [])
            row = await report_dao.create(
                org_id=ctx.org_id,
                created_by=user_payload["sub"],
                date_from=body.date_from,
                date_to=body.date_to,
                result=result_data,
                sources_used=sources_used,
                ai_model=settings.ai_model,
            )
            done_payload = {
                "type": "done",
                "id": str(row.id),
                "date_from": date_from_str,
                "date_to": date_to_str,
                "result": result_data,
                "sources_used": sources_used,
                "ai_model": settings.ai_model,
                "created_at": row.created_at.isoformat(),
            }
            yield f"data: {json.dumps(done_payload)}\n\n"

    return StreamingResponse(
        _generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/{report_id}", response_model=ReportResultDTO)
async def get_report(
    report_id: uuid.UUID,
    ctx: OrgContext = Depends(get_org_context),
    report_dao: ReportDAO = Depends(),
) -> ReportResultDTO:
    """Return a single report by ID.

    :param report_id: UUID of the report.
    :param ctx: Resolved org context.
    :param report_dao: Injected ReportDAO.
    :raises HTTPException: 404 if not found.
    :return: Full ReportResultDTO.
    """
    row = await report_dao.get_by_id(report_id, ctx.org_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Report not found")
    return ReportResultDTO(
        id=row.id,
        date_from=row.date_from,
        date_to=row.date_to,
        result=row.result,
        sources_used=row.sources_used,
        ai_model=row.ai_model,
        created_at=row.created_at,
    )


@router.get("/", response_model=list[ReportSummaryDTO])
async def list_reports(
    limit: int = 20,
    offset: int = 0,
    ctx: OrgContext = Depends(get_org_context),
    report_dao: ReportDAO = Depends(),
) -> list[ReportSummaryDTO]:
    """Return paginated report history for the current organisation.

    :param limit: Max rows to return.
    :param offset: Row offset for pagination.
    :param ctx: Resolved org context.
    :param report_dao: Injected ReportDAO.
    :return: List of report summaries.
    """
    rows = await report_dao.list_for_org(org_id=ctx.org_id, limit=limit, offset=offset)
    return [
        ReportSummaryDTO(
            id=row.id,
            date_from=row.date_from,
            date_to=row.date_to,
            title=row.result.get("title", f"Report {row.date_from} – {row.date_to}"),
            confidence=row.result.get("confidence", "medium"),
            sources_used=row.sources_used,
            created_at=row.created_at,
        )
        for row in rows
    ]
