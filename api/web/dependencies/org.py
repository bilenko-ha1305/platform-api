"""Organisation context FastAPI dependency."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from fastapi import Depends, HTTPException

from api.db.dao.org_dao import OrgDAO
from api.web.dependencies.auth import verify_token


@dataclass
class OrgContext:
    """Resolved organisation membership context for the current request."""

    org_id: uuid.UUID
    role: str  # "admin" | "member"


async def get_org_context(
    user_payload: dict[str, Any] = Depends(verify_token),
    org_dao: OrgDAO = Depends(),
) -> OrgContext:
    """Resolve the current user's organisation membership.

    :param user_payload: Decoded JWT claims.
    :param org_dao: Injected OrgDAO.
    :raises HTTPException: 403 if user has no organisation.
    :return: OrgContext with org_id and role.
    """
    member = await org_dao.get_membership(user_payload["sub"])
    if not member:
        raise HTTPException(
            status_code=403,
            detail="No organisation found. Create or join one first.",
        )
    return OrgContext(org_id=member.org_id, role=member.role)
