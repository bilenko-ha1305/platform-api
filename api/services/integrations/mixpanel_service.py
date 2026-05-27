"""Mixpanel MCP server client."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx


def _mcp_url(region: str = "us") -> str:
    if region == "eu":
        return "https://mcp-eu.mixpanel.com/mcp"
    if region == "in":
        return "https://mcp-in.mixpanel.com/mcp"
    return "https://mcp.mixpanel.com/mcp"


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
        raise RuntimeError(f"Mixpanel MCP error: {error_msg}")

    content = data.get("result", {}).get("content", [])
    for item in content:
        if item.get("type") == "text":
            try:
                return json.loads(item["text"])
            except (json.JSONDecodeError, TypeError):
                return item["text"]
    return content


async def get_event_counts(
    access_token: str,
    project_id: str,
    region: str,
    days_back: int = 30,
) -> dict[str, Any]:
    """Fetch event engagement counts over time from Mixpanel.

    :param access_token: OAuth access token.
    :param project_id: Mixpanel project ID.
    :param region: Data residency region (us/eu/in).
    :param days_back: Days of history to fetch.
    :return: Insights query result with event counts per day.
    """
    today = datetime.now(tz=UTC)
    from_date = (today - timedelta(days=days_back)).strftime("%Y-%m-%d")
    to_date = today.strftime("%Y-%m-%d")

    return await _call_tool(
        access_token,
        region,
        "Run-Query",
        {
            "project_id": project_id,
            "query_type": "insights",
            "event": [{"event": "$all_events"}],
            "from_date": from_date,
            "to_date": to_date,
            "unit": "day",
            "type": "general",
        },
    )


async def get_top_events(
    access_token: str,
    project_id: str,
    region: str,
) -> Any:
    """List tracked events with metadata from Mixpanel Lexicon.

    :param access_token: OAuth access token.
    :param project_id: Mixpanel project ID.
    :param region: Data residency region (us/eu/in).
    :return: List of event definitions.
    """
    return await _call_tool(
        access_token,
        region,
        "Get-Events",
        {"project_id": project_id},
    )
