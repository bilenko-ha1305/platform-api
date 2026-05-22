"""Report model."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import Date, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from api.db.base import Base


class Report(Base):
    """Stores the result of a period-based revenue and churn report."""

    __tablename__ = "reports"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_by: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("users.auth0_id", ondelete="CASCADE"),
        nullable=False,
    )
    date_from: Mapped[date] = mapped_column(Date, nullable=False)
    date_to: Mapped[date] = mapped_column(Date, nullable=False)
    result: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    sources_used: Mapped[list[Any]] = mapped_column(
        ARRAY(String(50)), nullable=False, default=list
    )
    ai_model: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now()
    )
