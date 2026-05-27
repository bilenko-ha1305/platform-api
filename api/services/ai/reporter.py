"""Synvar AI report generator using the OpenAI SDK."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncGenerator
from typing import Any, cast

from openai import AsyncStream, AuthenticationError
from openai.types.chat import ChatCompletionChunk

logger = logging.getLogger(__name__)

from api.services.ai.agent import _client, _execute_tool
from api.services.ai.tools import TOOLS, build_report_system_prompt


async def stream_report(
    date_from: str,
    date_to: str,
    integrations: dict[str, dict[str, Any]],
    model: str,
    api_key: str,
    base_url: str = "https://models.github.ai/inference",
    business_profile: dict[str, Any] | None = None,
) -> AsyncGenerator[dict[str, Any], None]:
    """Stream a period report as SSE-ready event dicts.

    Yields dicts with a "type" key:
    - ``{"type": "status", "message": str}`` — progress update
    - ``{"type": "token", "content": str}`` — synthesis text token
    - ``{"type": "result", "data": dict}`` — final structured result (internal)
    """
    client = _client(api_key=api_key, base_url=base_url)
    connected = list(integrations.keys())
    messages: list[dict[str, Any]] = [
        {
            "role": "system",
            "content": build_report_system_prompt(date_from, date_to, business_profile),
        },
        {
            "role": "user",
            "content": (
                f"Connected integrations: {connected}\n\n"
                f"Generate a comprehensive revenue report for {date_from} to {date_to}."
            ),
        },
    ]

    available_tools = [
        t
        for t in TOOLS
        if any(connected_tool in t["function"]["name"] for connected_tool in connected)
    ] or TOOLS

    yield {"type": "status", "message": "Starting report generation…"}

    try:
        response = await client.chat.completions.create(  # type: ignore[call-overload]
            model=model,
            messages=messages,  # type: ignore[arg-type]
            tools=available_tools,  # type: ignore[arg-type]
            tool_choice="auto",
        )
    except AuthenticationError as exc:
        logger.error(
            "AI 401 Unauthorized (report tool-selection call) — model=%s base_url=%s key_set=%s body=%s",
            model,
            base_url,
            bool(api_key),
            exc.body,
        )
        raise

    assistant_message = response.choices[0].message
    tool_calls = assistant_message.tool_calls or []
    sources_used: list[str] = []

    if tool_calls:
        messages.append(assistant_message.model_dump(exclude_unset=False))

        tool_names = {tc.function.name for tc in tool_calls}
        if any("stripe" in t for t in tool_names):
            yield {"type": "status", "message": "Fetching Stripe data…"}
        if any("paypal" in t for t in tool_names):
            yield {"type": "status", "message": "Fetching PayPal transactions…"}
        if any("posthog" in t for t in tool_names):
            yield {"type": "status", "message": "Fetching PostHog events…"}
        if any("intercom" in t for t in tool_names):
            yield {"type": "status", "message": "Fetching Intercom conversations…"}
        if any("mailchimp" in t for t in tool_names):
            yield {"type": "status", "message": "Fetching Mailchimp data…"}
        if any("github" in t for t in tool_names):
            yield {"type": "status", "message": "Fetching GitHub activity…"}
        if any("vercel" in t for t in tool_names):
            yield {"type": "status", "message": "Fetching Vercel deployments…"}
        if any("supabase" in t for t in tool_names):
            yield {"type": "status", "message": "Querying Supabase database…"}

        async def _call(tc: Any) -> tuple[str, Any]:
            args = json.loads(tc.function.arguments)
            result = await _execute_tool(tc.function.name, args, integrations)
            return tc.id, result

        results = await asyncio.gather(*[_call(tc) for tc in tool_calls])

        for call_id, tool_result in results:
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call_id,
                    "content": json.dumps(tool_result),
                }
            )
            tool_name = next(
                (tc.function.name for tc in tool_calls if tc.id == call_id), ""
            )
            for source in (
                "stripe",
                "posthog",
                "intercom",
                "mailchimp",
                "github",
                "supabase",
            ):
                if source in tool_name and source not in sources_used:
                    sources_used.append(source)

        yield {"type": "status", "message": "Writing report…"}

        full_content = ""
        try:
            stream = cast(
                AsyncStream[ChatCompletionChunk],
                await client.chat.completions.create(
                    model=model,
                    messages=messages,  # type: ignore[arg-type]
                    stream=True,
                ),
            )
        except AuthenticationError as exc:
            logger.error(
                "AI 401 Unauthorized (report synthesis call) — model=%s base_url=%s key_set=%s body=%s",
                model,
                base_url,
                bool(api_key),
                exc.body,
            )
            raise
        async for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta.content
            if delta:
                full_content += delta
                yield {"type": "token", "content": delta}

        final_content = full_content
    else:
        final_content = assistant_message.content or "{}"
        for char in final_content:
            yield {"type": "token", "content": char}

    try:
        result_dict: dict[str, Any] = json.loads(final_content)
    except json.JSONDecodeError:
        result_dict = {
            "title": f"Revenue Report: {date_from} – {date_to}",
            "executive_summary": final_content,
            "mrr_overview": {},
            "churn_analysis": {"total_churned": 0, "mrr_lost": None, "top_reasons": []},
            "growth_analysis": {"new_subscriptions": 0, "upgrades": 0},
            "key_findings": [],
            "recommendations": [],
            "confidence": "low",
        }

    result_dict["sources_used"] = sources_used
    yield {"type": "result", "data": result_dict}


async def run_report(
    date_from: str,
    date_to: str,
    integrations: dict[str, dict[str, Any]],
    model: str,
    api_key: str,
    base_url: str = "https://models.github.ai/inference",
    business_profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Non-streaming wrapper around stream_report."""
    result: dict[str, Any] = {}
    async for event in stream_report(
        date_from=date_from,
        date_to=date_to,
        integrations=integrations,
        model=model,
        api_key=api_key,
        base_url=base_url,
        business_profile=business_profile,
    ):
        if event["type"] == "result":
            result = event["data"]
    return result
