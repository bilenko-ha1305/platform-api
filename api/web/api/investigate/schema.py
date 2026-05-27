"""Investigation API schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from api.enums import Confidence


class TokenUsageDTO(BaseModel):
    """Token counts for a single investigation."""

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class InvestigateRequestDTO(BaseModel):
    """Request body to start an investigation."""

    question: str
    conversation_id: uuid.UUID | None = None


class InvestigationResultDTO(BaseModel):
    """Response schema for a completed investigation."""

    id: uuid.UUID
    question: str
    summary: str
    # New structured fields
    likely_root_cause: str
    affected_customers: list[str]
    revenue_impact: str | None
    shared_pattern: str | None
    supporting_events: list[str]
    recommended_next_actions: list[str]
    category: str | None
    owner_team: str | None
    confidence: Confidence
    sources_used: list[Any]
    ai_model: str
    token_usage: TokenUsageDTO | None = None
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
