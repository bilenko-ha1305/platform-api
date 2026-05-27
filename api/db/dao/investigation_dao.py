"""Investigation DAO."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import Depends
from sqlalchemy import delete, func, select
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from api.db.dependencies import get_db_session
from api.db.models.investigation_model import Investigation


class ConversationSummary:
    """In-memory summary of a conversation (group of investigations)."""

    __slots__ = ("conversation_id", "last_message_at", "message_count", "title")

    def __init__(
        self,
        conversation_id: uuid.UUID,
        title: str,
        message_count: int,
        last_message_at: datetime,
    ) -> None:
        self.conversation_id = conversation_id
        self.title = title
        self.message_count = message_count
        self.last_message_at = last_message_at


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
        conversation_id: uuid.UUID | None = None,
    ) -> Investigation:
        """Persist a completed investigation.

        :param org_id: Organisation UUID.
        :param created_by: Auth0 ID of the user who ran the investigation.
        :param question: Original natural-language question.
        :param result: Structured result dict from the AI agent.
        :param sources_used: List of integration names used.
        :param ai_model: LiteLLM model identifier used.
        :param conversation_id: Optional conversation UUID to group messages.
        :return: The saved Investigation row.
        """
        investigation = Investigation(
            org_id=org_id,
            created_by=created_by,
            question=question,
            result=result,
            sources_used=sources_used,
            ai_model=ai_model,
            conversation_id=conversation_id,
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
        month_start = now.replace(
            day=1, hour=0, minute=0, second=0, microsecond=0, tzinfo=None
        )
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

    async def list_by_conversation(
        self,
        conversation_id: uuid.UUID,
        org_id: uuid.UUID,
    ) -> list[Investigation]:
        """Return all investigations in a conversation, oldest first.

        :param conversation_id: Conversation UUID.
        :param org_id: Organisation UUID (ownership check).
        :return: List of Investigation rows ordered by created_at asc.
        """
        result = await self.session.execute(
            select(Investigation)
            .where(
                Investigation.conversation_id == conversation_id,
                Investigation.org_id == org_id,
            )
            .order_by(Investigation.created_at.asc())
        )
        return list(result.scalars().all())

    async def list_conversations(
        self,
        org_id: uuid.UUID,
    ) -> list[ConversationSummary]:
        """Return one summary per conversation for an org, newest first.

        :param org_id: Organisation UUID.
        :return: List of ConversationSummary objects.
        """
        rows_result = await self.session.execute(
            select(Investigation)
            .where(
                Investigation.org_id == org_id,
                Investigation.conversation_id.isnot(None),
            )
            .order_by(Investigation.created_at.asc())
        )
        rows = list(rows_result.scalars().all())

        conversations: dict[uuid.UUID, ConversationSummary] = {}
        for row in rows:
            cid = row.conversation_id  # type: ignore[assignment]
            if cid not in conversations:
                conversations[cid] = ConversationSummary(
                    conversation_id=cid,
                    title=row.question,
                    message_count=0,
                    last_message_at=row.created_at,
                )
            conversations[cid].message_count += 1
            conversations[cid].last_message_at = row.created_at

        return sorted(
            conversations.values(),
            key=lambda c: c.last_message_at,
            reverse=True,
        )

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

    async def delete_conversation(
        self, conversation_id: uuid.UUID, org_id: uuid.UUID
    ) -> int:
        """Delete all investigations in a conversation.

        :param conversation_id: Conversation UUID.
        :param org_id: Organisation UUID (ownership check).
        :return: Number of rows deleted.
        """
        cursor: CursorResult[Any] = await self.session.execute(  # type: ignore[assignment]
            delete(Investigation).where(
                Investigation.conversation_id == conversation_id,
                Investigation.org_id == org_id,
            )
        )
        await self.session.commit()
        return int(cursor.rowcount)
