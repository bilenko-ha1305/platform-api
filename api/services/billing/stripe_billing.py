"""Stripe billing helpers for Revelio's own subscriptions."""

from __future__ import annotations

import asyncio
from typing import Any

import stripe

from api.settings import settings


# Map plan name → Stripe price ID (resolved at call time from settings)
def _price_map() -> dict[str, str]:
    return {
        "solo": settings.stripe_price_solo,
        "studio": settings.stripe_price_studio,
    }


def _plan_from_price_id(price_id: str) -> str:
    """Reverse-map a Stripe price ID to a plan name."""
    for plan, pid in _price_map().items():
        if pid and pid == price_id:
            return plan
    return "free"


async def create_checkout_session(
    org_id: str,
    plan: str,
    customer_id: str | None,
    success_url: str,
    cancel_url: str,
) -> str:
    """Create a Stripe Checkout session and return the redirect URL.

    :param org_id: Organisation UUID string (stored in session metadata).
    :param plan: Target plan identifier ("solo" | "studio").
    :param customer_id: Existing Stripe customer ID if any.
    :param success_url: URL Stripe redirects to on success.
    :param cancel_url: URL Stripe redirects to on cancel.
    :return: Stripe-hosted checkout URL.
    """
    price_id = _price_map()[plan]
    params: dict[str, Any] = {
        "api_key": settings.stripe_secret_key,
        "mode": "subscription",
        "line_items": [{"price": price_id, "quantity": 1}],
        "success_url": success_url,
        "cancel_url": cancel_url,
        "metadata": {"org_id": org_id, "plan": plan},
        "subscription_data": {"metadata": {"org_id": org_id, "plan": plan}},
    }
    if customer_id:
        params["customer"] = customer_id

    session: stripe.checkout.Session = await asyncio.to_thread(
        stripe.checkout.Session.create, **params
    )
    return str(session.url)


async def create_portal_session(customer_id: str, return_url: str) -> str:
    """Create a Stripe Customer Portal session.

    :param customer_id: Stripe cus_xxx identifier.
    :param return_url: URL to redirect to after the portal session.
    :return: Stripe-hosted portal URL.
    """
    session: stripe.billing_portal.Session = await asyncio.to_thread(
        stripe.billing_portal.Session.create,
        customer=customer_id,
        return_url=return_url,
        api_key=settings.stripe_secret_key,
    )
    return str(session.url)


def construct_event(payload: bytes, sig_header: str) -> stripe.Event:
    """Verify and parse an incoming Stripe webhook event.

    :param payload: Raw request body bytes.
    :param sig_header: Value of the Stripe-Signature header.
    :raises stripe.SignatureVerificationError: On invalid signature.
    :return: Parsed Stripe Event.
    """
    return stripe.Webhook.construct_event(
        payload, sig_header, settings.stripe_webhook_secret
    )


def plan_from_subscription(sub: Any) -> str:
    """Extract the plan name from a Stripe Subscription object."""
    try:
        price_id: str = sub["items"]["data"][0]["price"]["id"]
        return _plan_from_price_id(price_id)
    except (KeyError, IndexError):
        return "free"
