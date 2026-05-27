"""Scheduled report configuration model."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, Integer, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from api.db.base import Base


class ScheduledReport(Base):
    """Stores one daily-report schedule per organisation."""

    __tablename__ = "scheduled_reports"
    __table_args__ = (UniqueConstraint("org_id", name="scheduled_reports_org_id_key"),)

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    hour_utc: Mapped[int] = mapped_column(Integer, nullable=False, default=8)
    minute_utc: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    lookback_days: Mapped[int] = mapped_column(Integer, nullable=False, default=7)
    last_sent_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now(), onupdate=func.now()
    )
