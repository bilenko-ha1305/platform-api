"""Intercom API data fetcher."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import httpx


async def get_conversations(
    access_token: str,
    days_back: int = 30,
) -> list[dict[str, Any]]:
    """Fetch recent Intercom conversations, focusing on churn/cancellation signals.

    :param access_token: Intercom access token.
    :param days_back: Days of conversation history to retrieve.
    :return: List of conversation summaries with sentiment and tags.
    """
    since_ts = int((datetime.now(tz=UTC) - timedelta(days=days_back)).timestamp())

    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(
            "https://api.intercom.io/conversations",
            params={
                "created_at_after": since_ts,
                "per_page": 50,
                "order": "desc",
                "sort": "created_at",
            },
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json",
                "Intercom-Version": "2.11",
            },
        )
        response.raise_for_status()
        data = response.json()

    results: list[dict[str, Any]] = []
    for conv in data.get("conversations", []):
        source = conv.get("source", {})
        tags = [t.get("name", "") for t in conv.get("tags", {}).get("tags", [])]
        assignee = conv.get("assignee", {}) or {}
        results.append(
            {
                "id": conv.get("id"),
                "created_at": conv.get("created_at"),
                "state": conv.get("state"),
                "subject": source.get("subject", ""),
                "body_preview": (source.get("body", "") or "")[:300],
                "tags": tags,
                "rating": conv.get("conversation_rating", {}).get("rating"),
                "assignee_name": assignee.get("name"),
                "open": conv.get("open"),
            }
        )

    return results
