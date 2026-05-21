"""Integration API schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class IntegrationCreateDTO(BaseModel):
    """Request body for connecting an integration."""

    tool: str
    credentials: dict[str, Any]


class IntegrationDTO(BaseModel):
    """Response schema for a connected integration (credentials masked)."""

    tool: str
    connected: bool = True

    model_config = ConfigDict(from_attributes=True)
