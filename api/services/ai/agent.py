"""Revelio AI investigation agent using the OpenAI SDK."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from openai import AsyncOpenAI

from api.services.ai.tools import SYSTEM_PROMPT, TOOLS
from api.services.integrations import posthog_service, stripe_service


def _client(api_key: str, base_url: str) -> AsyncOpenAI:
    return AsyncOpenAI(api_key=api_key, base_url=base_url)


async def _execute_stripe(
    tool_name: str,
    tool_args: dict[str, Any],
    creds: dict[str, Any],
) -> Any:
    if tool_name == "get_stripe_cancellations":
        return await stripe_service.get_cancellations(
            api_key=creds["api_key"],
            start_date=tool_args["start_date"],
            end_date=tool_args["end_date"],
        )
    return await stripe_service.get_mrr_timeline(
        api_key=creds["api_key"],
        days=tool_args.get("days", 30),
    )


async def _execute_posthog(
    tool_name: str,
    tool_args: dict[str, Any],
    creds: dict[str, Any],
) -> Any:
    if tool_name == "get_posthog_user_events":
        return await posthog_service.get_user_events(
            api_key=creds["api_key"],
            project_id=creds.get("project_id", ""),
            user_ids=tool_args["user_ids"],
            days_back=tool_args.get("days_back", 30),
        )
    return await posthog_service.get_feature_usage(
        api_key=creds["api_key"],
        project_id=creds.get("project_id", ""),
        days_back=tool_args.get("days_back", 30),
    )


async def _execute_tool(
    tool_name: str,
    tool_args: dict[str, Any],
    integrations: dict[str, dict[str, Any]],
) -> Any:
    """Dispatch a tool call to the appropriate integration service.

    :param tool_name: Name of the tool function to invoke.
    :param tool_args: Parsed arguments from the LLM tool call.
    :param integrations: Decrypted credentials keyed by tool name.
    :return: JSON-serialisable result from the integration service.
    """
    if tool_name.startswith("get_stripe"):
        creds = integrations.get("stripe", {})
        if not creds:
            return {"error": "Stripe not connected"}
        return await _execute_stripe(tool_name, tool_args, creds)

    if tool_name.startswith("get_posthog"):
        creds = integrations.get("posthog", {})
        if not creds:
            return {"error": "PostHog not connected"}
        return await _execute_posthog(tool_name, tool_args, creds)

    return {"error": f"Unknown tool: {tool_name}"}


async def run_investigation(
    question: str,
    integrations: dict[str, dict[str, Any]],
    model: str,
    api_key: str,
    base_url: str = "https://models.github.ai/inference",
) -> dict[str, Any]:
    """Run a full churn investigation using the AI agent and connected tools.

    :param question: Natural-language question from the user.
    :param integrations: Decrypted integration credentials keyed by tool name.
    :param model: OpenAI-compatible model identifier (e.g. "openai/gpt-5-nano").
    :param api_key: API key / GitHub token for the provider.
    :param base_url: OpenAI-compatible inference endpoint.
    :return: Structured result dict with summary, root_cause, evidence, action.
    """
    client = _client(api_key=api_key, base_url=base_url)
    connected = list(integrations.keys())
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"Connected integrations: {connected}\n\nQuestion: {question}",
        },
    ]

    available_tools = [
        t
        for t in TOOLS
        if any(connected_tool in t["function"]["name"] for connected_tool in connected)
    ] or TOOLS

    response = await client.chat.completions.create(
        model=model,
        messages=messages,  # type: ignore[arg-type]
        tools=available_tools,  # type: ignore[arg-type]
        tool_choice="auto",
    )

    assistant_message = response.choices[0].message
    tool_calls = assistant_message.tool_calls or []
    sources_used: list[str] = []

    if tool_calls:
        messages.append(assistant_message.model_dump(exclude_unset=False))

        async def _call(tc: Any) -> tuple[str, Any]:
            args = json.loads(tc.function.arguments)
            result = await _execute_tool(tc.function.name, args, integrations)
            return tc.id, result

        results = await asyncio.gather(*[_call(tc) for tc in tool_calls])

        for call_id, result in results:
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call_id,
                    "content": json.dumps(result),
                }
            )
            tool_name = next(
                (tc.function.name for tc in tool_calls if tc.id == call_id), ""
            )
            if "stripe" in tool_name and "stripe" not in sources_used:
                sources_used.append("stripe")
            if "posthog" in tool_name and "posthog" not in sources_used:
                sources_used.append("posthog")

        final_response = await client.chat.completions.create(
            model=model,
            messages=messages,  # type: ignore[arg-type]
            response_format={"type": "json_object"},  # type: ignore[arg-type]
        )
        final_content = final_response.choices[0].message.content or "{}"
    else:
        final_content = assistant_message.content or "{}"

    try:
        result_dict: dict[str, Any] = json.loads(final_content)
    except json.JSONDecodeError:
        result_dict = {
            "summary": "Investigation complete",
            "root_cause": final_content,
            "evidence": [],
            "recommended_action": "Review the data manually.",
            "confidence": "low",
        }

    result_dict["sources_used"] = sources_used
    return result_dict
