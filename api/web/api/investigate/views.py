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

router = APIRouter()


@router.post("/", response_model=InvestigationResultDTO, status_code=201)
async def investigate(
    body: InvestigateRequestDTO,
    user_payload: dict[str, Any] = Depends(verify_token),
    integration_dao: IntegrationDAO = Depends(),
    investigation_dao: InvestigationDAO = Depends(),
) -> InvestigationResultDTO:
    """Run a churn investigation and persist the result.

    :param body: Natural-language investigation question.
    :param user_payload: Decoded JWT claims.
    :param integration_dao: Injected IntegrationDAO for credential lookup.
    :param investigation_dao: Injected InvestigationDAO for persistence.
    :return: Structured investigation result.
    :raises HTTPException: 400 if no integrations are connected.
    """
    user_id: str = user_payload["sub"]
    integrations = await integration_dao.get_decrypted(user_auth0_id=user_id)

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
    )

    sources_used: list[str] = result.pop("sources_used", [])

    row = await investigation_dao.create(
        user_auth0_id=user_id,
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
    user_payload: dict[str, Any] = Depends(verify_token),
    investigation_dao: InvestigationDAO = Depends(),
) -> list[InvestigationSummaryDTO]:
    """Return paginated investigation history for the current user.

    :param limit: Max rows to return.
    :param offset: Row offset for pagination.
    :param user_payload: Decoded JWT claims.
    :param investigation_dao: Injected InvestigationDAO.
    :return: List of investigation summaries.
    """
    rows = await investigation_dao.list_for_user(
        user_auth0_id=user_payload["sub"],
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
