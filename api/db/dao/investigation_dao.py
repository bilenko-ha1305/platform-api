"""Investigation DAO."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.db.dependencies import get_db_session
from api.db.models.investigation_model import Investigation


class InvestigationDAO:
    """Provides access to the investigations table."""

    def __init__(self, session: AsyncSession = Depends(get_db_session)) -> None:
        self.session = session

    async def create(
        self,
        org_id: uuid.UUID,
        created_by: str,
        question: str,
        result: dict[str, Any],
        sources_used: list[str],
        ai_model: str,
    ) -> Investigation:
        """Persist a completed investigation.

        :param org_id: Organisation UUID.
        :param created_by: Auth0 ID of the user who ran the investigation.
        :param question: Original natural-language question.
        :param result: Structured result dict from the AI agent.
        :param sources_used: List of integration names used.
        :param ai_model: LiteLLM model identifier used.
        :return: The saved Investigation row.
        """
        investigation = Investigation(
            org_id=org_id,
            created_by=created_by,
            question=question,
            result=result,
            sources_used=sources_used,
            ai_model=ai_model,
        )
        self.session.add(investigation)
        await self.session.flush()
        return investigation

    async def count_this_month(self, org_id: uuid.UUID) -> int:
        """Count investigations run by this org in the current calendar month.

        :param org_id: Organisation UUID.
        :return: Count of investigations since the start of this month.
        """
        now = datetime.now(tz=UTC)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0, tzinfo=None)
        result = await self.session.execute(
            select(func.count()).where(
                Investigation.org_id == org_id,
                Investigation.created_at >= month_start,
            )
        )
        return result.scalar_one()

    async def list_for_org(
        self,
        org_id: uuid.UUID,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Investigation]:
        """Return paginated investigations for an organisation, newest first.

        :param org_id: Organisation UUID.
        :param limit: Maximum rows to return.
        :param offset: Row offset for pagination.
        :return: List of Investigation rows.
        """
        result = await self.session.execute(
            select(Investigation)
            .where(Investigation.org_id == org_id)
            .order_by(Investigation.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def get_by_id(
        self, investigation_id: uuid.UUID, org_id: uuid.UUID
    ) -> Investigation | None:
        """Fetch a single investigation, scoped to the organisation.

        :param investigation_id: UUID primary key.
        :param org_id: Organisation UUID (ownership check).
        :return: Investigation if found, else None.
        """
        result = await self.session.execute(
            select(Investigation).where(
                Investigation.id == investigation_id,
                Investigation.org_id == org_id,
            )
        )
        return result.scalar_one_or_none()
