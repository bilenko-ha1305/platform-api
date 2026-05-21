"""Users API endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from api.db.dao.user_dao import UserDAO
from api.web.api.users.schema import UserDTO
from api.web.dependencies.auth import verify_token

router = APIRouter()


@router.post("/sync", response_model=UserDTO)
async def sync_user(
    user_payload: dict[str, Any] = Depends(verify_token),
    user_dao: UserDAO = Depends(),
) -> UserDTO:
    """Upsert the authenticated user on first login.

    Called by the frontend immediately after Auth0 redirects back.
    Creates the user row if it doesn't exist, or refreshes email/name.

    :param user_payload: Decoded JWT claims from Auth0.
    :param user_dao: Injected UserDAO.
    :return: Current user data.
    """
    user = await user_dao.upsert(
        auth0_id=user_payload["sub"],
        email=user_payload.get("email", ""),
        name=user_payload.get("name"),
    )
    return UserDTO.model_validate(user)
