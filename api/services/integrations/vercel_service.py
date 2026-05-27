"""Vercel API data fetcher."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

_BASE = "https://api.vercel.com"


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


async def get_deployments(
    token: str,
    team_id: str | None = None,
    project_id: str | None = None,
    days_back: int = 30,
) -> list[dict[str, Any]]:
    """Fetch recent Vercel deployments.

    :param token: Vercel personal access token.
    :param team_id: Optional team slug or ID.
    :param project_id: Optional project name or ID to filter by.
    :param days_back: Days of deployment history to retrieve.
    :return: List of deployments with state, date, and URL.
    """
    since_ms = int(
        (datetime.now(tz=UTC) - timedelta(days=days_back)).timestamp() * 1000
    )
    params: dict[str, str | int] = {"limit": 50, "since": since_ms}
    if team_id:
        params["teamId"] = team_id
    if project_id:
        params["projectId"] = project_id

    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(
            f"{_BASE}/v6/deployments",
            params=params,
            headers=_headers(token),
        )
        response.raise_for_status()
        data = response.json()

    results: list[dict[str, Any]] = []
    for d in data.get("deployments", []):
        created_ms = d.get("created", 0)
        created_at = (
            datetime.fromtimestamp(created_ms / 1000, tz=UTC).isoformat()
            if created_ms
            else None
        )
        results.append(
            {
                "id": d.get("uid"),
                "name": d.get("name"),
                "url": d.get("url"),
                "state": d.get("state"),  # READY | ERROR | CANCELED | BUILDING
                "target": d.get("target"),  # production | preview
                "created_at": created_at,
                "creator": d.get("creator", {}).get("username"),
            }
        )
    return results


async def get_failed_deployments(
    token: str,
    team_id: str | None = None,
    project_id: str | None = None,
    days_back: int = 30,
) -> list[dict[str, Any]]:
    """Return only deployments that errored or were cancelled.

    :param token: Vercel personal access token.
    :param team_id: Optional team slug or ID.
    :param project_id: Optional project name or ID.
    :param days_back: Days of history to scan.
    :return: List of failed deployment records.
    """
    all_deploys = await get_deployments(
        token=token,
        team_id=team_id,
        project_id=project_id,
        days_back=days_back,
    )
    return [d for d in all_deploys if d.get("state") in {"ERROR", "CANCELED"}]


async def get_deployment_logs(
    token: str,
    deployment_id: str,
    team_id: str | None = None,
) -> list[dict[str, Any]]:
    """Fetch build and runtime log entries for a specific deployment.

    :param token: Vercel personal access token.
    :param deployment_id: Vercel deployment UID (dpl_...).
    :param team_id: Optional team slug or ID.
    :return: List of log entries with timestamp, type, and text.
    """
    params: dict[str, str] = {}
    if team_id:
        params["teamId"] = team_id

    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(
            f"{_BASE}/v2/deployments/{deployment_id}/events",
            params=params,
            headers=_headers(token),
        )
        response.raise_for_status()
        events = response.json()

    return [
        {
            "created_at": e.get("created"),
            "type": e.get("type"),
            "text": (e.get("payload", {}) or {}).get("text", ""),
        }
        for e in (events if isinstance(events, list) else [])
        if e.get("type") in {"stdout", "stderr", "error"}
    ]
