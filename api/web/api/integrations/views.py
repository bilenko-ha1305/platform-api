"""Integrations CRUD endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from api.db.dao.integration_dao import IntegrationDAO
from api.web.api.integrations.schema import IntegrationCreateDTO, IntegrationDTO
from api.web.dependencies.auth import verify_token

router = APIRouter()


@router.get("/", response_model=list[IntegrationDTO])
async def list_integrations(
    user_payload: dict[str, Any] = Depends(verify_token),
    integration_dao: IntegrationDAO = Depends(),
) -> list[IntegrationDTO]:
    """Return all connected integrations for the current user (credentials masked).

    :param user_payload: Decoded JWT claims.
    :param integration_dao: Injected IntegrationDAO.
    :return: List of connected integration summaries.
    """
    rows = await integration_dao.get_for_user(user_auth0_id=user_payload["sub"])
    return [IntegrationDTO(tool=row.tool) for row in rows]


@router.post("/", response_model=IntegrationDTO, status_code=201)
async def connect_integration(
    body: IntegrationCreateDTO,
    user_payload: dict[str, Any] = Depends(verify_token),
    integration_dao: IntegrationDAO = Depends(),
) -> IntegrationDTO:
    """Save or update API credentials for an integration.

    :param body: Tool name and plain-text credentials.
    :param user_payload: Decoded JWT claims.
    :param integration_dao: Injected IntegrationDAO.
    :return: Confirmation of connected integration.
    """
    await integration_dao.upsert(
        user_auth0_id=user_payload["sub"],
        tool=body.tool,
        credentials=body.credentials,
    )
    return IntegrationDTO(tool=body.tool)


@router.delete("/{tool}", status_code=204)
async def disconnect_integration(
    tool: str,
    user_payload: dict[str, Any] = Depends(verify_token),
    integration_dao: IntegrationDAO = Depends(),
) -> None:
    """Remove a connected integration.

    :param tool: Integration identifier to remove.
    :param user_payload: Decoded JWT claims.
    :param integration_dao: Injected IntegrationDAO.
    :raises HTTPException: 404 if the integration does not exist.
    """
    rows = await integration_dao.get_for_user(user_auth0_id=user_payload["sub"])
    if not any(row.tool == tool for row in rows):
        raise HTTPException(status_code=404, detail="Integration not found")
    await integration_dao.delete_tool(user_auth0_id=user_payload["sub"], tool=tool)
