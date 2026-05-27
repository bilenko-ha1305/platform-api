"""Chargebee Data Access MCP Server client."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import httpx


def _mcp_url(site: str, data_center: str = "us") -> str:
    if data_center == "eu":
        return f"https://{site}.mcp.eu.chargebee.com/data_lookup_agent"
    if data_center == "au":
        return f"https://{site}.mcp.au.chargebee.com/data_lookup_agent"
    return f"https://{site}.mcp.chargebee.com/data_lookup_agent"


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
    url: str,
    api_key: str,
    tool_name: str,
    arguments: dict[str, Any],
) -> Any:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }

    async with httpx.AsyncClient(timeout=20.0) as client:
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
        raise RuntimeError(f"Chargebee MCP error: {error_msg}")

    content = data.get("result", {}).get("content", [])
    for item in content:
        if item.get("type") == "text":
            try:
                return json.loads(item["text"])
            except (json.JSONDecodeError, TypeError):
                return item["text"]
    return content


async def get_cancellations(
    site: str,
    api_key: str,
    data_center: str,
    start_date: str,
    end_date: str,
) -> list[dict[str, Any]]:
    """Fetch cancelled subscriptions from Chargebee within a date range.

    :param site: Chargebee subdomain (e.g. "mycompany" for mycompany.chargebee.com).
    :param api_key: MCP server API key.
    :param data_center: Data center region (us/eu/au).
    :param start_date: Range start in YYYY-MM-DD format.
    :param end_date: Range end in YYYY-MM-DD format.
    :return: List of cancellation records.
    """
    start_ts = int(
        datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=UTC).timestamp()
    )
    end_ts = int(
        datetime.strptime(end_date, "%Y-%m-%d").replace(tzinfo=UTC).timestamp()
    )

    url = _mcp_url(site, data_center)
    raw = await _call_tool(url, api_key, "list_subscriptions", {
        "status[is]": "cancelled",
        "cancelled_at[after]": start_ts,
        "cancelled_at[before]": end_ts,
        "limit": 100,
    })

    items: list[Any] = raw.get("list", []) if isinstance(raw, dict) else []
    results: list[dict[str, Any]] = []
    for item in items:
        sub: dict[str, Any] = item.get("subscription", {}) if isinstance(item, dict) else {}
        customer: dict[str, Any] = item.get("customer", {}) if isinstance(item, dict) else {}
        plan_amount = sub.get("plan_amount")
        results.append({
            "subscription_id": sub.get("id"),
            "customer_id": sub.get("customer_id"),
            "customer_email": customer.get("email"),
            "plan_name": sub.get("plan_id"),
            "mrr_lost": plan_amount / 100 if plan_amount else None,
            "cancelled_at": sub.get("cancelled_at"),
        })
    return results


async def get_subscription_overview(
    site: str,
    api_key: str,
    data_center: str,
    days: int = 30,
) -> list[dict[str, Any]]:
    """Get active subscription count and estimated MRR from Chargebee.

    :param site: Chargebee subdomain.
    :param api_key: MCP server API key.
    :param data_center: Data center region (us/eu/au).
    :param days: History window label (informational only).
    :return: Single-element list with subscription count and MRR.
    """
    url = _mcp_url(site, data_center)
    raw = await _call_tool(url, api_key, "list_subscriptions", {
        "status[is]": "active",
        "limit": 100,
    })

    items: list[Any] = raw.get("list", []) if isinstance(raw, dict) else []
    active_count = len(items)
    total_mrr: float = 0.0
    for item in items:
        sub: dict[str, Any] = item.get("subscription", {}) if isinstance(item, dict) else {}
        amount = sub.get("plan_amount") or 0
        total_mrr += amount / 100

    return [{
        "period": f"last_{days}_days",
        "active_subscriptions": active_count,
        "estimated_mrr": total_mrr,
    }]
