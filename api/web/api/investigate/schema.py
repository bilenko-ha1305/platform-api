"""Investigation API schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class InvestigateRequestDTO(BaseModel):
    """Request body to start an investigation."""

    question: str


class InvestigationResultDTO(BaseModel):
    """Response schema for a completed investigation."""

    id: uuid.UUID
    question: str
    summary: str
    root_cause: str
    evidence: list[str]
    recommended_action: str
    confidence: str
    sources_used: list[Any]
    ai_model: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InvestigationSummaryDTO(BaseModel):
    """Compact investigation row for history listing."""

    id: uuid.UUID
    question: str
    summary: str
    sources_used: list[Any]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
