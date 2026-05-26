"""Investigation API schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from api.enums import Confidence


class InvestigateRequestDTO(BaseModel):
    """Request body to start an investigation."""

    question: str
    conversation_id: uuid.UUID | None = None


class InvestigationResultDTO(BaseModel):
    """Response schema for a completed investigation."""

    id: uuid.UUID
    question: str
    summary: str
    root_cause: str
    evidence: list[str]
    recommended_action: str
    confidence: Confidence
    sources_used: list[Any]
    ai_model: str
    conversation_id: uuid.UUID | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InvestigationSummaryDTO(BaseModel):
    """Compact investigation row for history listing."""

    id: uuid.UUID
    question: str
    summary: str
    sources_used: list[Any]
    conversation_id: uuid.UUID | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ConversationSummaryDTO(BaseModel):
    """One entry in the conversations sidebar."""

    conversation_id: uuid.UUID
    title: str
    message_count: int
    last_message_at: datetime
