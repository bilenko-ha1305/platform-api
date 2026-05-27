"""Amplitude MCP server client."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx


def _mcp_url(region: str = "us") -> str:
    if region == "eu":
        return "https://mcp.eu.amplitude.com/mcp"
    return "https://mcp.amplitude.com/mcp"


def _parse_mcp_response(resp: httpx.Response) -> Any:
    content_type = resp.headers.get("content-type", "")
    if "text/event-stream" in content_type:
        for line in resp.text.splitlines():
            if line.startswith("data: "):
                try:
                    event = json.loads(line[6:])
                    if "result" in event:
                        return event
                except (json.JSONDecodeError, KeyError):
                    continue
        return None
    return resp.json()


async def _call_tool(
    access_token: str,
    region: str,
    tool_name: str,
    arguments: dict[str, Any],
) -> Any:
    url = _mcp_url(region)
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        init_resp = await client.post(
            url,
            headers=headers,
            json={
                "jsonrpc": "2.0",
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "revelio", "version": "1.0"},
                },
                "id": 0,
            },
        )
        session_id = init_resp.headers.get("Mcp-Session-Id")
        if session_id:
            headers["Mcp-Session-Id"] = session_id

        await client.post(
            url,
            headers=headers,
            json={"jsonrpc": "2.0", "method": "notifications/initialized"},
        )

        resp = await client.post(
            url,
            headers=headers,
            json={
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {"name": tool_name, "arguments": arguments},
                "id": 1,
            },
        )
        resp.raise_for_status()

    data = _parse_mcp_response(resp)
    if data is None or "error" in (data or {}):
        error_msg = (data or {}).get("error", {}).get("message", "Unknown error")
        raise RuntimeError(f"Amplitude MCP error: {error_msg}")

    content = data.get("result", {}).get("content", [])
    for item in content:
        if item.get("type") == "text":
            try:
                return json.loads(item["text"])
            except (json.JSONDecodeError, TypeError):
                return item["text"]
    return content


async def get_event_stats(
    access_token: str,
    project_id: str,
    region: str,
    days_back: int = 30,
) -> Any:
    """Fetch daily event engagement counts from Amplitude.

    Uses query_amplitude_data in discover mode first to get the query schema,
    then in execute mode to run the event segmentation query.

    :param access_token: OAuth access token.
    :param project_id: Amplitude project ID.
    :param region: Data residency region (us/eu).
    :param days_back: Days of history to fetch.
    :return: Event segmentation results with daily counts.
    """
    today = datetime.now(tz=UTC)
    from_date = (today - timedelta(days=days_back)).strftime("%Y%m%d")
    to_date = today.strftime("%Y%m%d")

    # Discover mode returns the schema; execute mode runs the query.
    return await _call_tool(
        access_token,
        region,
        "query_amplitude_data",
        {
            "project_id": project_id,
            "mode": "execute",
            "query_type": "segmentation",
            "events": [{"event_type": "Any Event"}],
            "start": from_date,
            "end": to_date,
            "metric": "totals",
            "interval": 1,
        },
    )


async def get_retention(
    access_token: str,
    project_id: str,
    region: str,
    days_back: int = 30,
) -> Any:
    """Fetch cohort retention data from Amplitude.

    :param access_token: OAuth access token.
    :param project_id: Amplitude project ID.
    :param region: Data residency region (us/eu).
    :param days_back: Days of history to include in the retention cohort.
    :return: Retention query results.
    """
    today = datetime.now(tz=UTC)
    from_date = (today - timedelta(days=days_back)).strftime("%Y%m%d")
    to_date = today.strftime("%Y%m%d")

    return await _call_tool(
        access_token,
        region,
        "query_amplitude_data",
        {
            "project_id": project_id,
            "mode": "execute",
            "query_type": "retention",
            "events": [{"event_type": "Any Event"}],
            "start": from_date,
            "end": to_date,
            "retention_type": "n-day",
        },
    )
