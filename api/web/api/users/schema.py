"""User API schemas."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class UserDTO(BaseModel):
    """Response schema for a user."""

    auth0_id: str
    email: str
    name: str | None
    plan: str

    model_config = ConfigDict(from_attributes=True)
