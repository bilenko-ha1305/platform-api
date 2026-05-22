"""Supabase data fetcher via the PostgREST API."""

from __future__ import annotations

from typing import Any

import httpx


def _headers(api_key: str) -> dict[str, str]:
    return {
        "apikey": api_key,
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
    }


async def list_tables(project_url: str, api_key: str) -> list[dict[str, str]]:
    """Return the names of all tables exposed via PostgREST.

    :param project_url: Supabase project URL (https://xxx.supabase.co).
    :param api_key: Service role key.
    :return: List of {table} dicts.
    """
    url = f"{project_url.rstrip('/')}/rest/v1/"
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(url, headers=_headers(api_key))
        response.raise_for_status()
        data = response.json()

    if isinstance(data, dict):
        return [{"table": name} for name in sorted(data.keys())]
    return []


async def query_table(
    project_url: str,
    api_key: str,
    table: str,
    limit: int = 100,
    order: str | None = None,
    filters: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Fetch rows from a Supabase table via PostgREST.

    :param project_url: Supabase project URL.
    :param api_key: Service role key.
    :param table: Table name to query.
    :param limit: Maximum rows to return (capped at 500).
    :param order: PostgREST order expression e.g. ``created_at.desc``.
    :param filters: Column-level PostgREST filters e.g. ``{"status": "eq.active"}``.
    :return: List of row dicts.
    """
    url = f"{project_url.rstrip('/')}/rest/v1/{table}"
    params: dict[str, Any] = {
        "select": "*",
        "limit": min(limit, 500),
    }
    if order:
        params["order"] = order
    if filters:
        params.update(filters)

    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(url, params=params, headers=_headers(api_key))
        response.raise_for_status()
        return list(response.json())
