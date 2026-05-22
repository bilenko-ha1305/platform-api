"""Organisation API schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from api.enums import BusinessModel, OrgRole, Plan


class OrgCreateDTO(BaseModel):
    """Request body to create an organisation."""

    name: str = Field(min_length=2, max_length=100)


class MemberDTO(BaseModel):
    """A single organisation member with user profile."""

    user_auth0_id: str
    email: str | None
    name: str | None
    role: OrgRole
    joined_at: datetime


class InviteCreateDTO(BaseModel):
    """Request body to invite a user."""

    email: EmailStr
    role: OrgRole = OrgRole.MEMBER


class InviteDTO(BaseModel):
    """Invite row (full details, admin-only)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    role: OrgRole
    token: str
    created_at: datetime
    expires_at: datetime
    accepted_at: datetime | None = None


class BusinessProfileDTO(BaseModel):
    """Request body to set the organisation's business profile."""

    description: str = Field(max_length=500)
    business_model: BusinessModel
    launched_at: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")  # YYYY-MM


class OrgDTO(BaseModel):
    """Full organisation response including members and pending invites."""

    id: uuid.UUID
    name: str
    slug: str
    plan: Plan
    has_billing: bool
    business_profile: dict[str, Any] | None = None
    members: list[MemberDTO]
    pending_invites: list[InviteDTO]


class OrgUpdatePlanDTO(BaseModel):
    """Request body to change the organisation plan."""

    plan: Plan


class PublicInviteDTO(BaseModel):
    """Public invite details shown before accepting (no auth required)."""

    org_name: str
    email: str
    role: OrgRole
    expires_at: datetime
    is_expired: bool
    is_accepted: bool
