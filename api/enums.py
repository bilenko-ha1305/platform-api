"""Shared enumerations used across models, schemas, and business logic."""

from __future__ import annotations

import enum


class Plan(enum.StrEnum):
    FREE = "free"
    SOLO = "solo"
    STUDIO = "studio"
    INTERNAL = "internal"


class OrgRole(enum.StrEnum):
    ADMIN = "admin"
    MEMBER = "member"


class BusinessModel(enum.StrEnum):
    B2B = "b2b"
    B2C = "b2c"
    BOTH = "both"


class Confidence(enum.StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
