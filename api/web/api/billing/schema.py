"""Billing API schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class CheckoutRequestDTO(BaseModel):
    """Request body to start a Stripe Checkout session."""

    plan: str = Field(pattern="^(solo|studio)$")


class CheckoutResponseDTO(BaseModel):
    """Stripe Checkout redirect URL."""

    url: str


class PortalResponseDTO(BaseModel):
    """Stripe Customer Portal redirect URL."""

    url: str
