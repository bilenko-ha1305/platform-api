"""Integration model."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from api.db.base import Base


class Integration(Base):
    """Stores encrypted third-party API credentials per organisation per tool."""

    __tablename__ = "integrations"
    __table_args__ = (
        UniqueConstraint(
            "org_id",
            "tool",
            name="integrations_org_id_tool_key",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    tool: Mapped[str] = mapped_column(String(50), nullable=False)
    credentials_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    connected_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now()
    )
    last_sync: Mapped[datetime | None] = mapped_column(nullable=True)
