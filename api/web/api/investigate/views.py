"""Investigation endpoints."""

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
from api.services.ai.agent import run_investigation, stream_investigation
from api.settings import settings
from api.web.api.investigate.schema import (
    InvestigateRequestDTO,
    InvestigationResultDTO,
    InvestigationSummaryDTO,
)
from api.web.dependencies.auth import verify_token
from api.web.dependencies.org import OrgContext, get_org_context

router = APIRouter()

# Monthly investigation limits per plan; -1 = unlimited
PLAN_LIMITS: dict[str, int] = {
    "free": 3,
    "solo": 50,
    "studio": -1,
}


async def _check_plan_limit(
    org_id: Any,
    plan: str,
    investigation_dao: InvestigationDAO,
) -> None:
    limit = PLAN_LIMITS.get(plan, 3)
    if limit == -1:
        return
    used = await investigation_dao.count_this_month(org_id)
    if used >= limit:
        raise HTTPException(
            status_code=402,
            detail=(
                f"Monthly investigation limit reached ({used}/{limit} on the {plan} plan). "
                "Upgrade your plan to run more investigations."
            ),
        )


@router.post("/", response_model=InvestigationResultDTO, status_code=201)
async def investigate(
    body: InvestigateRequestDTO,
    user_payload: dict[str, Any] = Depends(verify_token),
    ctx: OrgContext = Depends(get_org_context),
    integration_dao: IntegrationDAO = Depends(),
    investigation_dao: InvestigationDAO = Depends(),
    org_dao: OrgDAO = Depends(),
) -> InvestigationResultDTO:
    """Run a churn investigation and persist the result.

    :param body: Natural-language investigation question.
    :param user_payload: Decoded JWT claims (for created_by).
    :param ctx: Resolved org context.
    :param integration_dao: Injected IntegrationDAO for credential lookup.
    :param investigation_dao: Injected InvestigationDAO for persistence.
    :param org_dao: Injected OrgDAO for business profile lookup.
    :return: Structured investigation result.
    :raises HTTPException: 400 if no integrations are connected.
    """
    await _check_plan_limit(ctx.org_id, ctx.plan, investigation_dao)

    integrations = await integration_dao.get_decrypted(org_id=ctx.org_id)

    if not integrations:
        raise HTTPException(
            status_code=400,
            detail=(
                "Connect at least one integration "
                "(Stripe or PostHog) before investigating."
            ),
        )

    org = await org_dao.get_by_id(ctx.org_id)
    result = await run_investigation(
        question=body.question,
        integrations=integrations,
        model=settings.ai_model,
        api_key=settings.ai_api_key,
        base_url=settings.ai_base_url,
        business_profile=org.business_profile if org else None,
    )

    sources_used: list[str] = result.pop("sources_used", [])

    row = await investigation_dao.create(
        org_id=ctx.org_id,
        created_by=user_payload["sub"],
        question=body.question,
        result=result,
        sources_used=sources_used,
        ai_model=settings.ai_model,
    )

    return InvestigationResultDTO(
        id=row.id,
        question=row.question,
        summary=result.get("summary", ""),
        root_cause=result.get("root_cause", ""),
        evidence=result.get("evidence", []),
        recommended_action=result.get("recommended_action", ""),
        confidence=result.get("confidence", "medium"),
        sources_used=sources_used,
        ai_model=row.ai_model,
        created_at=row.created_at,
    )


@router.post("/stream")
async def stream_investigate(
    body: InvestigateRequestDTO,
    user_payload: dict[str, Any] = Depends(verify_token),
    ctx: OrgContext = Depends(get_org_context),
    integration_dao: IntegrationDAO = Depends(),
    investigation_dao: InvestigationDAO = Depends(),
    org_dao: OrgDAO = Depends(),
) -> StreamingResponse:
    """Stream an investigation as Server-Sent Events.

    Events: status (progress), token (synthesis text), done (saved result).

    :param body: Natural-language investigation question.
    :param user_payload: Decoded JWT claims.
    :param ctx: Resolved org context.
    :param integration_dao: Injected IntegrationDAO.
    :param investigation_dao: Injected InvestigationDAO.
    :param org_dao: Injected OrgDAO for business profile lookup.
    :raises HTTPException: 400 if no integrations connected.
    :return: SSE StreamingResponse.
    """
    await _check_plan_limit(ctx.org_id, ctx.plan, investigation_dao)

    integrations = await integration_dao.get_decrypted(org_id=ctx.org_id)
    if not integrations:
        raise HTTPException(
            status_code=400,
            detail="Connect at least one integration before investigating.",
        )

    org = await org_dao.get_by_id(ctx.org_id)
    business_profile = org.business_profile if org else None

    async def _generate() -> AsyncGenerator[str, None]:
        result_data: dict[str, Any] | None = None
        async for event in stream_investigation(
            question=body.question,
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
            row = await investigation_dao.create(
                org_id=ctx.org_id,
                created_by=user_payload["sub"],
                question=body.question,
                result=result_data,
                sources_used=sources_used,
                ai_model=settings.ai_model,
            )
            done_payload = {
                "type": "done",
                "id": str(row.id),
                "question": body.question,
                "summary": result_data.get("summary", ""),
                "root_cause": result_data.get("root_cause", ""),
                "evidence": result_data.get("evidence", []),
                "recommended_action": result_data.get("recommended_action", ""),
                "confidence": result_data.get("confidence", "medium"),
                "sources_used": sources_used,
                "ai_model": settings.ai_model,
            }
            yield f"data: {json.dumps(done_payload)}\n\n"

    return StreamingResponse(
        _generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/{investigation_id}", response_model=InvestigationResultDTO)
async def get_investigation(
    investigation_id: uuid.UUID,
    ctx: OrgContext = Depends(get_org_context),
    investigation_dao: InvestigationDAO = Depends(),
) -> InvestigationResultDTO:
    """Return a single investigation by ID.

    :param investigation_id: UUID of the investigation.
    :param ctx: Resolved org context (scopes to current org).
    :param investigation_dao: Injected InvestigationDAO.
    :raises HTTPException: 404 if not found.
    :return: Full InvestigationResultDTO.
    """
    row = await investigation_dao.get_by_id(investigation_id, ctx.org_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Investigation not found")
    return InvestigationResultDTO(
        id=row.id,
        question=row.question,
        summary=row.result.get("summary", ""),
        root_cause=row.result.get("root_cause", ""),
        evidence=row.result.get("evidence", []),
        recommended_action=row.result.get("recommended_action", ""),
        confidence=row.result.get("confidence", "medium"),
        sources_used=row.sources_used,
        ai_model=row.ai_model,
        created_at=row.created_at,
    )


@router.get("/", response_model=list[InvestigationSummaryDTO])
async def list_investigations(
    limit: int = 20,
    offset: int = 0,
    ctx: OrgContext = Depends(get_org_context),
    investigation_dao: InvestigationDAO = Depends(),
) -> list[InvestigationSummaryDTO]:
    """Return paginated investigation history for the current organisation.

    :param limit: Max rows to return.
    :param offset: Row offset for pagination.
    :param ctx: Resolved org context.
    :param investigation_dao: Injected InvestigationDAO.
    :return: List of investigation summaries.
    """
    rows = await investigation_dao.list_for_org(
        org_id=ctx.org_id,
        limit=limit,
        offset=offset,
    )
    return [
        InvestigationSummaryDTO(
            id=row.id,
            question=row.question,
            summary=row.result.get("summary", ""),
            sources_used=row.sources_used,
            created_at=row.created_at,
        )
        for row in rows
    ]
