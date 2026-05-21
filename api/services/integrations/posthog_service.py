"""PostHog API data fetcher."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx


async def get_user_events(
    api_key: str,
    project_id: str,
    user_ids: list[str],
    days_back: int = 30,
) -> list[dict[str, str | int | None]]:
    """Fetch feature usage events for specific users from PostHog.

    :param api_key: PostHog personal API key.
    :param project_id: PostHog project ID.
    :param user_ids: List of distinct_id values to query.
    :param days_back: Number of days of event history to retrieve.
    :return: List of event records grouped by user and event name.
    """
    after = (datetime.now(tz=UTC) - timedelta(days=days_back)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )

    results: list[dict[str, str | int | None]] = []

    async with httpx.AsyncClient(timeout=20.0) as client:
        for user_id in user_ids[:20]:
            response = await client.get(
                f"https://app.posthog.com/api/projects/{project_id}/events/",
                params={
                    "distinct_id": user_id,
                    "after": after,
                    "limit": 200,
                },
                headers={"Authorization": f"Bearer {api_key}"},
            )
            if response.status_code != 200:
                continue

            data = response.json()
            events = data.get("results", [])

            event_counts: dict[str, int] = {}
            last_seen: str | None = None

            for event in events:
                name = event.get("event", "unknown")
                event_counts[name] = event_counts.get(name, 0) + 1
                if last_seen is None:
                    last_seen = event.get("timestamp")

            results.append(
                {
                    "user_id": user_id,
                    "total_events": len(events),
                    "last_seen": last_seen,
                    "event_summary": str(event_counts),
                    "days_active": len(
                        {
                            e.get("timestamp", "")[:10]
                            for e in events
                            if e.get("timestamp")
                        }
                    ),
                }
            )

    return results


async def get_feature_usage(
    api_key: str,
    project_id: str,
    days_back: int = 30,
) -> list[dict[str, str | int]]:
    """Aggregate feature usage across all users in a PostHog project.

    :param api_key: PostHog personal API key.
    :param project_id: PostHog project ID.
    :param days_back: Days of history to consider.
    :return: List of top events by frequency.
    """
    after = (datetime.now(tz=UTC) - timedelta(days=days_back)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )

    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(
            f"https://app.posthog.com/api/projects/{project_id}/events/",
            params={"after": after, "limit": 500},
            headers={"Authorization": f"Bearer {api_key}"},
        )
        response.raise_for_status()
        data = response.json()

    event_counts: dict[str, int] = {}
    for event in data.get("results", []):
        name = event.get("event", "unknown")
        event_counts[name] = event_counts.get(name, 0) + 1

    return [
        {"event_name": name, "count": count}
        for name, count in sorted(
            event_counts.items(), key=lambda x: x[1], reverse=True
        )[:20]
    ]
