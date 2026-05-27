"""Paddle MCP server client (codemode interface)."""

from __future__ import annotations

import json
from typing import Any

import httpx


def _mcp_url(environment: str = "live") -> str:
    if environment == "sandbox":
        return "https://sandbox-mcp.paddle.com/mcp"
    return "https://mcp.paddle.com/mcp"


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


async def _execute_code(
    api_key: str,
    environment: str,
    code: str,
) -> Any:
    url = _mcp_url(environment)
    headers = {
        "Authorization": f"Bearer {api_key}",
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
                "params": {
                    "name": "execute",
                    "arguments": {"code": code},
                },
                "id": 1,
            },
        )
        resp.raise_for_status()

    data = _parse_mcp_response(resp)
    if data is None or "error" in (data or {}):
        error_msg = (data or {}).get("error", {}).get("message", "Unknown error")
        raise RuntimeError(f"Paddle MCP error: {error_msg}")

    content = data.get("result", {}).get("content", [])
    for item in content:
        if item.get("type") == "text":
            try:
                return json.loads(item["text"])
            except (json.JSONDecodeError, TypeError):
                return item["text"]
    return content


async def get_cancellations(
    api_key: str,
    environment: str,
    start_date: str,
    end_date: str,
) -> list[dict[str, Any]]:
    """Fetch cancelled subscriptions from Paddle within a date range.

    :param api_key: Paddle API key.
    :param environment: 'live' or 'sandbox'.
    :param start_date: Range start in YYYY-MM-DD format.
    :param end_date: Range end in YYYY-MM-DD format.
    :return: List of cancellation records.
    """
    code = f"""
const startTs = new Date('{start_date}T00:00:00Z').getTime();
const endTs = new Date('{end_date}T23:59:59Z').getTime();
const response = await paddle.subscriptions.list({{ status: ['canceled'], perPage: 200 }});
const subs = (response.data || []).filter(sub => {{
  if (!sub.canceledAt) return false;
  const ts = new Date(sub.canceledAt).getTime();
  return ts >= startTs && ts <= endTs;
}});
return {{ subscriptions: subs.map(sub => ({{
  subscription_id: sub.id,
  customer_id: sub.customerId,
  status: sub.status,
  plan_name: (sub.items && sub.items[0] && sub.items[0].price && sub.items[0].price.description) || null,
  mrr_lost: (sub.items && sub.items[0] && sub.items[0].price && sub.items[0].price.unitPrice)
    ? parseInt(sub.items[0].price.unitPrice.amount || '0', 10) / 100
    : null,
  cancelled_at: sub.canceledAt,
}})) }};
"""
    raw = await _execute_code(api_key, environment, code)
    subs = raw.get("subscriptions", []) if isinstance(raw, dict) else []
    return list(subs)


async def get_subscription_overview(
    api_key: str,
    environment: str,
    days: int = 30,
) -> list[dict[str, Any]]:
    """Get active subscription count and estimated MRR from Paddle.

    :param api_key: Paddle API key.
    :param environment: 'live' or 'sandbox'.
    :param days: History window label (informational only).
    :return: Single-element list with subscription count and MRR.
    """
    code = """
const response = await paddle.subscriptions.list({ status: ['active'], perPage: 200 });
const subs = response.data || [];
const totalMrr = subs.reduce((acc, sub) => {
  const item = sub.items && sub.items[0];
  if (!item || !item.price || !item.price.unitPrice) return acc;
  return acc + parseInt(item.price.unitPrice.amount || '0', 10) / 100;
}, 0);
return { active_subscriptions: subs.length, estimated_mrr: totalMrr };
"""
    raw = await _execute_code(api_key, environment, code)
    active = raw.get("active_subscriptions", 0) if isinstance(raw, dict) else 0
    mrr = raw.get("estimated_mrr", 0.0) if isinstance(raw, dict) else 0.0
    return [
        {
            "period": f"last_{days}_days",
            "active_subscriptions": active,
            "estimated_mrr": mrr,
        }
    ]
