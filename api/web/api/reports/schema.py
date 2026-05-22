"""Reports API schemas."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator


class ReportRequestDTO(BaseModel):
    """Request body to generate a period report."""

    date_from: date
    date_to: date

    @field_validator("date_to")
    @classmethod
    def date_to_after_date_from(cls, v: date, info: Any) -> date:
        """Ensure date_to is not before date_from."""
        date_from = info.data.get("date_from")
        if date_from and v < date_from:
            raise ValueError("date_to must be on or after date_from")
        return v


class ReportResultDTO(BaseModel):
    """Full report response."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    date_from: date
    date_to: date
    result: dict[str, Any]
    sources_used: list[str]
    ai_model: str
    created_at: datetime


class ReportSummaryDTO(BaseModel):
    """Compact report row for history listing."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    date_from: date
    date_to: date
    title: str
    confidence: str
    sources_used: list[str]
    created_at: datetime
