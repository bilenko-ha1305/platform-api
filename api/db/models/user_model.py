"""User model."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Enum as SAEnum
from sqlalchemy import String, func
from sqlalchemy.orm import Mapped, mapped_column

from api.db.base import Base
from api.enums import Plan


class User(Base):
    """Stores authenticated users keyed by Auth0 subject ID."""

    __tablename__ = "users"

    auth0_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    email: Mapped[str | None] = mapped_column(String(254), unique=True, nullable=True)
    name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    plan: Mapped[Plan] = mapped_column(
        SAEnum(Plan, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        server_default="free",
    )
    stripe_customer_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now()
    )
