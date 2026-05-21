"""Investigation DAO."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.db.dependencies import get_db_session
from api.db.models.investigation_model import Investigation


class InvestigationDAO:
    """Provides access to the investigations table."""

    def __init__(self, session: AsyncSession = Depends(get_db_session)) -> None:
        self.session = session

    async def create(
        self,
        user_auth0_id: str,
        question: str,
        result: dict[str, Any],
        sources_used: list[str],
        ai_model: str,
    ) -> Investigation:
        """Persist a completed investigation.

        :param user_auth0_id: Auth0 subject ID of the requesting user.
        :param question: Original natural-language question.
        :param result: Structured result dict from the AI agent.
        :param sources_used: List of integration names used.
        :param ai_model: LiteLLM model identifier used.
        :return: The saved Investigation row.
        """
        investigation = Investigation(
            user_auth0_id=user_auth0_id,
            question=question,
            result=result,
            sources_used=sources_used,
            ai_model=ai_model,
        )
        self.session.add(investigation)
        await self.session.flush()
        return investigation

    async def list_for_user(
        self,
        user_auth0_id: str,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Investigation]:
        """Return paginated investigations for a user, newest first.

        :param user_auth0_id: Auth0 subject ID.
        :param limit: Maximum rows to return.
        :param offset: Row offset for pagination.
        :return: List of Investigation rows.
        """
        result = await self.session.execute(
            select(Investigation)
            .where(Investigation.user_auth0_id == user_auth0_id)
            .order_by(Investigation.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def get_by_id(
        self, investigation_id: uuid.UUID, user_auth0_id: str
    ) -> Investigation | None:
        """Fetch a single investigation, scoped to the requesting user.

        :param investigation_id: UUID primary key.
        :param user_auth0_id: Auth0 subject ID (ownership check).
        :return: Investigation if found and owned by user, else None.
        """
        result = await self.session.execute(
            select(Investigation).where(
                Investigation.id == investigation_id,
                Investigation.user_auth0_id == user_auth0_id,
            )
        )
        return result.scalar_one_or_none()
