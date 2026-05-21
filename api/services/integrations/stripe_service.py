"""Stripe API data fetcher."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import httpx


async def get_cancellations(
    api_key: str,
    start_date: str,
    end_date: str,
) -> list[dict[str, str | float | None]]:
    """Fetch cancelled subscriptions from Stripe within a date range.

    :param api_key: Stripe restricted API key (read-only).
    :param start_date: ISO date string for range start (YYYY-MM-DD).
    :param end_date: ISO date string for range end (YYYY-MM-DD).
    :return: List of cancellation records.
    """
    start_ts = int(
        datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=UTC).timestamp()
    )
    end_ts = int(
        datetime.strptime(end_date, "%Y-%m-%d").replace(tzinfo=UTC).timestamp()
    )

    params: dict[str, str | int] = {
        "status": "canceled",
        "created[gte]": start_ts,
        "created[lte]": end_ts,
        "limit": 100,
        "expand[]": "data.customer",
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(
            "https://api.stripe.com/v1/subscriptions",
            params=params,
            auth=(api_key, ""),
        )
        response.raise_for_status()
        data = response.json()

    results: list[dict[str, str | float | None]] = []
    for sub in data.get("data", []):
        customer = sub.get("customer", {})
        plan_amount: float | None = None
        items = sub.get("items", {}).get("data", [])
        if items:
            plan_amount = items[0].get("plan", {}).get("amount", 0) / 100

        cust_id = customer.get("id") if isinstance(customer, dict) else customer
        cust_email = customer.get("email") if isinstance(customer, dict) else None
        plan_name = items[0].get("plan", {}).get("nickname") if items else None
        cancel_reason = sub.get("cancellation_details", {}).get("reason")
        results.append(
            {
                "subscription_id": sub.get("id"),
                "customer_id": cust_id,
                "customer_email": cust_email,
                "plan_name": plan_name,
                "mrr_lost": plan_amount,
                "cancelled_at": sub.get("canceled_at"),
                "cancellation_reason": cancel_reason,
            }
        )

    return results


async def get_mrr_timeline(
    api_key: str,
    days: int = 30,
) -> list[dict[str, str | float]]:
    """Estimate daily active MRR from Stripe subscriptions.

    :param api_key: Stripe restricted API key.
    :param days: Number of days of history to fetch.
    :return: List of {date, active_subscriptions, estimated_mrr} dicts.
    """
    since_ts = int((datetime.now(tz=UTC) - timedelta(days=days)).timestamp())

    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(
            "https://api.stripe.com/v1/subscriptions",
            params={"status": "active", "limit": 100, "created[gte]": since_ts},
            auth=(api_key, ""),
        )
        response.raise_for_status()
        data = response.json()

    active_count = len(data.get("data", []))

    def _sub_amount(sub: dict[str, Any]) -> float:
        items = sub.get("items", {}).get("data", [{}])
        return items[0].get("plan", {}).get("amount", 0) / 100

    total_mrr: float = sum(
        _sub_amount(sub)
        for sub in data.get("data", [])
        if sub.get("items", {}).get("data")
    )

    return [
        {
            "period": f"last_{days}_days",
            "active_subscriptions": active_count,
            "estimated_mrr": total_mrr,
        }
    ]
