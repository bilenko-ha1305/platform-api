"""Stripe billing endpoints."""

from __future__ import annotations

import uuid
from typing import Any

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request

from api.db.dao.org_dao import OrgDAO
from api.services.billing import stripe_billing
from api.settings import settings
from api.web.api.billing.schema import (
    CheckoutRequestDTO,
    CheckoutResponseDTO,
    PortalResponseDTO,
)
from api.web.dependencies.org import OrgContext, get_org_context

router = APIRouter()


@router.post("/checkout", response_model=CheckoutResponseDTO)
async def create_checkout(
    body: CheckoutRequestDTO,
    ctx: OrgContext = Depends(get_org_context),
    org_dao: OrgDAO = Depends(),
) -> CheckoutResponseDTO:
    """Create a Stripe Checkout session for a plan upgrade.

    :param body: Target plan (solo or studio).
    :param ctx: Resolved org context.
    :param org_dao: Injected OrgDAO.
    :raises HTTPException: 403 if not admin.
    :return: Redirect URL to Stripe Checkout.
    """
    if ctx.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    org = await org_dao.get_by_id(ctx.org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="Organisation not found")

    url = await stripe_billing.create_checkout_session(
        org_id=str(ctx.org_id),
        plan=body.plan,
        customer_id=org.stripe_customer_id,
        success_url=(f"{settings.app_base_url}/dashboard/billing?billing=success"),
        cancel_url=(f"{settings.app_base_url}/dashboard/billing?billing=canceled"),
    )
    return CheckoutResponseDTO(url=url)


@router.post("/portal", response_model=PortalResponseDTO)
async def create_portal(
    ctx: OrgContext = Depends(get_org_context),
    org_dao: OrgDAO = Depends(),
) -> PortalResponseDTO:
    """Create a Stripe Customer Portal session for subscription management.

    :param ctx: Resolved org context.
    :param org_dao: Injected OrgDAO.
    :raises HTTPException: 400 if no billing account exists.
    :return: Redirect URL to the Stripe portal.
    """
    org = await org_dao.get_by_id(ctx.org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="Organisation not found")
    if not org.stripe_customer_id:
        raise HTTPException(status_code=400, detail="No billing account found")

    url = await stripe_billing.create_portal_session(
        customer_id=org.stripe_customer_id,
        return_url=f"{settings.app_base_url}/dashboard/billing",
    )
    return PortalResponseDTO(url=url)


@router.post("/webhook", status_code=200)
async def stripe_webhook(
    request: Request,
    org_dao: OrgDAO = Depends(),
) -> dict[str, bool]:
    """Handle incoming Stripe webhook events.

    Processes checkout completion and subscription lifecycle events
    to keep the org plan in sync with the Stripe subscription state.

    :param request: Raw FastAPI request (body read for signature check).
    :param org_dao: Injected OrgDAO.
    :raises HTTPException: 400 on invalid or unverifiable webhook.
    :return: Acknowledgement dict.
    """
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    try:
        event = stripe_billing.construct_event(payload, sig_header)
    except stripe.SignatureVerificationError as exc:
        raise HTTPException(
            status_code=400, detail="Invalid webhook signature"
        ) from exc

    event_type: str = event["type"]
    obj: Any = event["data"]["object"]

    if event_type == "checkout.session.completed":
        await _handle_checkout_completed(obj, org_dao)

    elif event_type == "customer.subscription.updated":
        await _handle_subscription_updated(obj, org_dao)

    elif event_type == "customer.subscription.deleted":
        await _handle_subscription_deleted(obj, org_dao)

    return {"ok": True}


async def _handle_checkout_completed(session: Any, org_dao: OrgDAO) -> None:
    org_id_str: str | None = (session.get("metadata") or {}).get("org_id")
    plan: str = (session.get("metadata") or {}).get("plan", "free")
    customer_id: str | None = session.get("customer")
    subscription_id: str | None = session.get("subscription")

    if not org_id_str or not customer_id:
        return

    try:
        org_id = uuid.UUID(org_id_str)
    except ValueError:
        return

    await org_dao.update_billing(
        org_id=org_id,
        stripe_customer_id=customer_id,
        stripe_subscription_id=subscription_id,
        plan=plan,
    )


async def _handle_subscription_updated(sub: Any, org_dao: OrgDAO) -> None:
    customer_id: str | None = sub.get("customer")
    if not customer_id:
        return

    org = await org_dao.get_by_stripe_customer_id(customer_id)
    if org is None:
        return

    status: str = sub.get("status", "")
    if status not in ("active", "trialing"):
        return

    plan = stripe_billing.plan_from_subscription(sub)
    subscription_id: str | None = sub.get("id")
    await org_dao.update_billing(
        org_id=org.id,
        stripe_customer_id=customer_id,
        stripe_subscription_id=subscription_id,
        plan=plan,
    )


async def _handle_subscription_deleted(sub: Any, org_dao: OrgDAO) -> None:
    customer_id: str | None = sub.get("customer")
    if not customer_id:
        return

    org = await org_dao.get_by_stripe_customer_id(customer_id)
    if org is None:
        return

    await org_dao.update_billing(
        org_id=org.id,
        stripe_customer_id=customer_id,
        stripe_subscription_id=None,
        plan="free",
    )
