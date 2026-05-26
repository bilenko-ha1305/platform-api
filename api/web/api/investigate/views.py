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
from api.db.dao.report_dao import ReportDAO
from api.services.ai.agent import run_investigation, stream_investigation
from api.settings import settings
from api.web.api.investigate.schema import (
    ConversationSummaryDTO,
    InvestigateRequestDTO,
    InvestigationResultDTO,
    InvestigationSummaryDTO,
    TokenUsageDTO,
)
from api.web.api.shared import check_plan_credits
from api.web.dependencies.auth import verify_token
from api.web.dependencies.org import OrgContext, get_org_context

router = APIRouter()


@router.get("/conversations", response_model=list[ConversationSummaryDTO])
async def list_conversations(
    ctx: OrgContext = Depends(get_org_context),
    investigation_dao: InvestigationDAO = Depends(),
) -> list[ConversationSummaryDTO]:
    """Return one summary per conversation for the sidebar.

    :param ctx: Resolved org context.
    :param investigation_dao: Injected InvestigationDAO.
    :return: List of ConversationSummaryDTO ordered by last activity desc.
    """
    summaries = await investigation_dao.list_conversations(org_id=ctx.org_id)
    return [
        ConversationSummaryDTO(
            conversation_id=s.conversation_id,
            title=s.title,
            message_count=s.message_count,
            last_message_at=s.last_message_at,
        )
        for s in summaries
    ]


@router.get("/conversations/{conversation_id}", response_model=list[InvestigationResultDTO])
async def get_conversation(
    conversation_id: uuid.UUID,
    ctx: OrgContext = Depends(get_org_context),
    investigation_dao: InvestigationDAO = Depends(),
) -> list[InvestigationResultDTO]:
    """Return all investigations in a conversation, oldest first.

    :param conversation_id: Conversation UUID.
    :param ctx: Resolved org context.
    :param investigation_dao: Injected InvestigationDAO.
    :return: Ordered list of InvestigationResultDTO.
    """
    rows = await investigation_dao.list_by_conversation(
        conversation_id=conversation_id,
        org_id=ctx.org_id,
    )
    return [
        InvestigationResultDTO(
            id=row.id,
            question=row.question,
            summary=row.result.get("summary", ""),
            root_cause=row.result.get("root_cause", ""),
            evidence=row.result.get("evidence", []),
            recommended_action=row.result.get("recommended_action", ""),
            confidence=row.result.get("confidence", "medium"),
            sources_used=row.sources_used,
            ai_model=row.ai_model,
            token_usage=_token_usage_from_result(row.result),
            conversation_id=row.conversation_id,
            created_at=row.created_at,
        )
        for row in rows
    ]


@router.post("/", response_model=InvestigationResultDTO, status_code=201)
async def investigate(
    body: InvestigateRequestDTO,
    user_payload: dict[str, Any] = Depends(verify_token),
    ctx: OrgContext = Depends(get_org_context),
    integration_dao: IntegrationDAO = Depends(),
    investigation_dao: InvestigationDAO = Depends(),
    report_dao: ReportDAO = Depends(),
    org_dao: OrgDAO = Depends(),
) -> InvestigationResultDTO:
    """Run a churn investigation and persist the result.

    :param body: Natural-language question plus optional conversation_id.
    :param user_payload: Decoded JWT claims (for created_by).
    :param ctx: Resolved org context.
    :param integration_dao: Injected IntegrationDAO for credential lookup.
    :param investigation_dao: Injected InvestigationDAO for persistence.
    :param report_dao: Injected ReportDAO (for cross-type credit counting).
    :param org_dao: Injected OrgDAO for business profile lookup.
    :return: Structured investigation result.
    :raises HTTPException: 400 if no integrations are connected.
    """
    await check_plan_credits(ctx.org_id, ctx.plan, investigation_dao, report_dao)

    integrations = await integration_dao.get_decrypted(org_id=ctx.org_id)
    if not integrations:
        raise HTTPException(
            status_code=400,
            detail="Connect at least one integration (Stripe or PostHog) before investigating.",
        )

    conversation_history = await _load_conversation_history(
        body.conversation_id, ctx.org_id, investigation_dao
    )

    org = await org_dao.get_by_id(ctx.org_id)
    result = await run_investigation(
        question=body.question,
        integrations=integrations,
        model=settings.ai_model,
        api_key=settings.ai_api_key,
        base_url=settings.ai_base_url,
        business_profile=org.business_profile if org else None,
        conversation_history=conversation_history,
    )

    sources_used: list[str] = result.pop("sources_used", [])
    row = await investigation_dao.create(
        org_id=ctx.org_id,
        created_by=user_payload["sub"],
        question=body.question,
        result=result,
        sources_used=sources_used,
        ai_model=settings.ai_model,
        conversation_id=body.conversation_id,
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
        token_usage=_token_usage_from_result(result),
        conversation_id=row.conversation_id,
        created_at=row.created_at,
    )


@router.post("/stream")
async def stream_investigate(
    body: InvestigateRequestDTO,
    user_payload: dict[str, Any] = Depends(verify_token),
    ctx: OrgContext = Depends(get_org_context),
    integration_dao: IntegrationDAO = Depends(),
    investigation_dao: InvestigationDAO = Depends(),
    report_dao: ReportDAO = Depends(),
    org_dao: OrgDAO = Depends(),
) -> StreamingResponse:
    """Stream an investigation as Server-Sent Events.

    Events: status (progress), token (synthesis text), done (saved result).

    :param body: Natural-language question plus optional conversation_id.
    :param user_payload: Decoded JWT claims.
    :param ctx: Resolved org context.
    :param integration_dao: Injected IntegrationDAO.
    :param investigation_dao: Injected InvestigationDAO.
    :param report_dao: Injected ReportDAO (for cross-type credit counting).
    :param org_dao: Injected OrgDAO for business profile lookup.
    :raises HTTPException: 400 if no integrations connected.
    :return: SSE StreamingResponse.
    """
    await check_plan_credits(ctx.org_id, ctx.plan, investigation_dao, report_dao)

    integrations = await integration_dao.get_decrypted(org_id=ctx.org_id)
    if not integrations:
        raise HTTPException(
            status_code=400,
            detail="Connect at least one integration before investigating.",
        )

    conversation_history = await _load_conversation_history(
        body.conversation_id, ctx.org_id, investigation_dao
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
            conversation_history=conversation_history,
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
                conversation_id=body.conversation_id,
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
                "token_usage": result_data.get("token_usage"),
                "conversation_id": str(body.conversation_id) if body.conversation_id else None,
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
        token_usage=_token_usage_from_result(row.result),
        conversation_id=row.conversation_id,
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
            conversation_id=row.conversation_id,
            created_at=row.created_at,
        )
        for row in rows
    ]


def _token_usage_from_result(result: dict[str, Any]) -> TokenUsageDTO | None:
    raw = result.get("token_usage")
    if not isinstance(raw, dict):
        return None
    try:
        return TokenUsageDTO(**raw)
    except Exception:
        return None


async def _load_conversation_history(
    conversation_id: uuid.UUID | None,
    org_id: uuid.UUID,
    investigation_dao: InvestigationDAO,
) -> list[dict[str, str]]:
    """Load prior Q&A pairs from a conversation for AI context.

    :param conversation_id: Optional conversation UUID.
    :param org_id: Organisation UUID (ownership scoping).
    :param investigation_dao: Injected DAO.
    :return: List of {question, answer} dicts, oldest first.
    """
    if conversation_id is None:
        return []
    rows = await investigation_dao.list_by_conversation(conversation_id, org_id)
    return [
        {
            "question": row.question,
            "answer": row.result.get("root_cause", row.result.get("summary", "")),
        }
        for row in rows
    ]
