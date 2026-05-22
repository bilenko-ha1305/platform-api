"""PayPal API data fetcher."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import httpx


def _base_url(mode: str) -> str:
    return (
        "https://api-m.sandbox.paypal.com"
        if mode == "sandbox"
        else "https://api-m.paypal.com"
    )


async def _get_access_token(
    client_id: str,
    client_secret: str,
    mode: str,
) -> str:
    """Fetch a short-lived OAuth 2.0 access token from PayPal.

    :param client_id: PayPal app client ID.
    :param client_secret: PayPal app client secret.
    :param mode: "live" or "sandbox".
    :return: Bearer access token string.
    """
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(
            f"{_base_url(mode)}/v1/oauth2/token",
            data={"grant_type": "client_credentials"},
            auth=(client_id, client_secret),
            headers={"Accept": "application/json"},
        )
        response.raise_for_status()
        return str(response.json()["access_token"])


async def get_transactions(
    client_id: str,
    client_secret: str,
    start_date: str,
    end_date: str,
    mode: str = "live",
) -> list[dict[str, Any]]:
    """Fetch PayPal transactions for a date range.

    :param client_id: PayPal app client ID.
    :param client_secret: PayPal app client secret.
    :param start_date: Start date in YYYY-MM-DD format.
    :param end_date: End date in YYYY-MM-DD format.
    :param mode: "live" or "sandbox".
    :return: List of transaction summaries.
    """
    token = await _get_access_token(client_id, client_secret, mode)
    start_iso = f"{start_date}T00:00:00-0000"
    end_iso = f"{end_date}T23:59:59-0000"

    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(
            f"{_base_url(mode)}/v1/reporting/transactions",
            params={
                "start_date": start_iso,
                "end_date": end_iso,
                "fields": "transaction_info,payer_info",
                "page_size": 100,
                "page": 1,
            },
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
        )
        response.raise_for_status()
        data = response.json()

    results: list[dict[str, Any]] = []
    for item in data.get("transaction_details", []):
        tx = item.get("transaction_info", {})
        payer = item.get("payer_info", {})
        amount = tx.get("transaction_amount", {})
        results.append(
            {
                "id": tx.get("transaction_id"),
                "date": tx.get("transaction_initiation_date"),
                "status": tx.get("transaction_status"),
                "event_code": tx.get("transaction_event_code"),
                "amount": amount.get("value"),
                "currency": amount.get("currency_code"),
                "payer_email": payer.get("email_address"),
                "subject": tx.get("transaction_subject"),
            }
        )

    return results


async def get_subscription_cancellations(
    client_id: str,
    client_secret: str,
    days_back: int = 30,
    mode: str = "live",
) -> list[dict[str, Any]]:
    """Fetch PayPal subscription cancellation transactions.

    Filters the transaction feed for cancellation event codes (T0005, T0006).

    :param client_id: PayPal app client ID.
    :param client_secret: PayPal app client secret.
    :param days_back: Days of history to retrieve.
    :param mode: "live" or "sandbox".
    :return: List of cancellation transaction records.
    """
    end = datetime.now(tz=UTC)
    start = end - timedelta(days=days_back)
    all_tx = await get_transactions(
        client_id=client_id,
        client_secret=client_secret,
        start_date=start.strftime("%Y-%m-%d"),
        end_date=end.strftime("%Y-%m-%d"),
        mode=mode,
    )
    # T0005 = subscription cancellation, T0006 = subscription expiry
    cancellation_codes = {"T0005", "T0006"}
    return [tx for tx in all_tx if tx.get("event_code") in cancellation_codes]
