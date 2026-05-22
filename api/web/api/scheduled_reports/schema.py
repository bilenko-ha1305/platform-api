"""Scheduled report request/response schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ScheduledReportUpsertDTO(BaseModel):
    """Request body for creating/updating a scheduled report."""

    enabled: bool
    hour_utc: int = Field(..., ge=0, le=23)
    minute_utc: int = Field(..., ge=0, le=59)
    lookback_days: int = Field(..., ge=1, le=90)


class ScheduledReportDTO(BaseModel):
    """Response schema for a scheduled report configuration."""

    id: uuid.UUID
    org_id: uuid.UUID
    enabled: bool
    hour_utc: int
    minute_utc: int
    lookback_days: int
    last_sent_at: datetime | None
    updated_at: datetime

    model_config = {"from_attributes": True}
