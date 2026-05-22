"""Mailchimp API data fetcher."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import httpx


def _server(api_key: str) -> str:
    """Extract the datacenter prefix from a Mailchimp API key (e.g. 'us1')."""
    parts = api_key.split("-")
    return parts[-1] if len(parts) > 1 else "us1"


async def get_campaign_stats(
    api_key: str,
    days_back: int = 60,
) -> list[dict[str, Any]]:
    """Fetch recent Mailchimp campaign send stats.

    :param api_key: Mailchimp API key (format: key-us1).
    :param days_back: Days of campaign history to retrieve.
    :return: List of campaigns with open/click/unsubscribe rates.
    """
    server = _server(api_key)
    since = (datetime.now(tz=UTC) - timedelta(days=days_back)).strftime(
        "%Y-%m-%dT%H:%M:%S+00:00"
    )

    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(
            f"https://{server}.api.mailchimp.com/3.0/campaigns",
            params={
                "since_send_time": since,
                "status": "sent",
                "count": 20,
                "fields": (
                    "campaigns.id,campaigns.settings.subject_line,"
                    "campaigns.send_time,campaigns.report_summary,"
                    "campaigns.emails_sent"
                ),
            },
            auth=("anystring", api_key),
        )
        response.raise_for_status()
        data = response.json()

    results: list[dict[str, Any]] = []
    for campaign in data.get("campaigns", []):
        summary = campaign.get("report_summary", {})
        results.append(
            {
                "id": campaign.get("id"),
                "subject": campaign.get("settings", {}).get("subject_line", ""),
                "sent_at": campaign.get("send_time"),
                "emails_sent": campaign.get("emails_sent", 0),
                "open_rate": summary.get("open_rate", 0),
                "click_rate": summary.get("click_rate", 0),
                "unsubscribes": summary.get("unsubscribe_count", 0),
                "bounces": summary.get("hard_bounces", 0),
            }
        )

    return results


async def get_unsubscribes(
    api_key: str,
    list_id: str,
    days_back: int = 30,
) -> list[dict[str, Any]]:
    """Fetch recent unsubscribes from a Mailchimp audience.

    :param api_key: Mailchimp API key.
    :param list_id: Audience / list ID.
    :param days_back: Days of history to retrieve.
    :return: List of unsubscribe records with email and timestamp.
    """
    server = _server(api_key)
    since = (datetime.now(tz=UTC) - timedelta(days=days_back)).strftime(
        "%Y-%m-%dT%H:%M:%S+00:00"
    )

    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(
            f"https://{server}.api.mailchimp.com/3.0/lists/{list_id}/members",
            params={
                "status": "unsubscribed",
                "since_last_changed": since,
                "count": 100,
                "fields": "members.email_address,members.timestamp_opt,members.unsubscribe_reason",
            },
            auth=("anystring", api_key),
        )
        response.raise_for_status()
        data = response.json()

    return [
        {
            "email": m.get("email_address"),
            "unsubscribed_at": m.get("timestamp_opt"),
            "reason": m.get("unsubscribe_reason"),
        }
        for m in data.get("members", [])
    ]
