"""Investigation endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from api.db.dao.integration_dao import IntegrationDAO
from api.db.dao.investigation_dao import InvestigationDAO
from api.services.ai.agent import run_investigation
from api.settings import settings
from api.web.api.investigate.schema import (
    InvestigateRequestDTO,
    InvestigationResultDTO,
    InvestigationSummaryDTO,
)
from api.web.dependencies.auth import verify_token
from api.web.dependencies.org import OrgContext, get_org_context

router = APIRouter()


@router.post("/", response_model=InvestigationResultDTO, status_code=201)
async def investigate(
    body: InvestigateRequestDTO,
    user_payload: dict[str, Any] = Depends(verify_token),
    ctx: OrgContext = Depends(get_org_context),
    integration_dao: IntegrationDAO = Depends(),
    investigation_dao: InvestigationDAO = Depends(),
) -> InvestigationResultDTO:
    """Run a churn investigation and persist the result.

    :param body: Natural-language investigation question.
    :param user_payload: Decoded JWT claims (for created_by).
    :param ctx: Resolved org context.
    :param integration_dao: Injected IntegrationDAO for credential lookup.
    :param investigation_dao: Injected InvestigationDAO for persistence.
    :return: Structured investigation result.
    :raises HTTPException: 400 if no integrations are connected.
    """
    integrations = await integration_dao.get_decrypted(org_id=ctx.org_id)

    if not integrations:
        raise HTTPException(
            status_code=400,
            detail=(
                "Connect at least one integration "
                "(Stripe or PostHog) before investigating."
            ),
        )

    result = await run_investigation(
        question=body.question,
        integrations=integrations,
        model=settings.ai_model,
        api_key=settings.ai_api_key,
        base_url=settings.ai_base_url,
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
