"""Organization, membership, and invite models."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from api.db.base import Base


class Organization(Base):
    """A workspace that groups users, integrations, and investigations."""

    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    owner_auth0_id: Mapped[str | None] = mapped_column(
        String(128),
        ForeignKey("users.auth0_id", ondelete="SET NULL"),
        nullable=True,
    )
    plan: Mapped[str] = mapped_column(String(20), nullable=False, server_default="free")
    stripe_customer_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True, unique=True
    )
    stripe_subscription_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now()
    )


class OrganizationMember(Base):
    """Links a user to an organization with a role."""

    __tablename__ = "organization_members"
    __table_args__ = (
        UniqueConstraint("org_id", "user_auth0_id", name="org_members_org_user_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_auth0_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("users.auth0_id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="member"
    )
    invited_by: Mapped[str | None] = mapped_column(
        String(128),
        ForeignKey("users.auth0_id", ondelete="SET NULL"),
        nullable=True,
    )
    joined_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now()
    )


class OrganizationInvite(Base):
    """Pending e-mail invite to join an organization."""

    __tablename__ = "organization_invites"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    email: Mapped[str] = mapped_column(String(254), nullable=False)
    token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    role: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="member"
    )
    invited_by: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("users.auth0_id", ondelete="CASCADE"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    accepted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
