"""Synvar AI investigation agent using the OpenAI SDK."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncGenerator
from typing import Any, cast

from openai import AsyncOpenAI, AsyncStream, AuthenticationError
from openai.types.chat import ChatCompletionChunk

logger = logging.getLogger(__name__)

from api.services.ai.tools import TOOLS, build_system_prompt
from api.services.integrations import (
    chargebee_service,
    github_service,
    intercom_service,
    mailchimp_service,
    paypal_service,
    posthog_service,
    stripe_service,
    supabase_service,
    vercel_service,
)


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
    if tool_name == "get_stripe_subscription_history":
        return await stripe_service.get_subscription_history(
            api_key=creds["api_key"],
            days_back=tool_args.get("days_back", 730),
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

    if tool_name.startswith("get_paypal"):
        creds = integrations.get("paypal", {})
        if not creds:
            return {"error": "PayPal not connected"}
        mode = creds.get("mode", "live")
        if tool_name == "get_paypal_transactions":
            return await paypal_service.get_transactions(
                client_id=creds["client_id"],
                client_secret=creds["client_secret"],
                start_date=tool_args["start_date"],
                end_date=tool_args["end_date"],
                mode=mode,
            )
        return await paypal_service.get_subscription_cancellations(
            client_id=creds["client_id"],
            client_secret=creds["client_secret"],
            days_back=tool_args.get("days_back", 30),
            mode=mode,
        )

    if tool_name.startswith("get_intercom"):
        creds = integrations.get("intercom", {})
        if not creds:
            return {"error": "Intercom not connected"}
        return await intercom_service.get_conversations(
            access_token=creds["access_token"],
            days_back=tool_args.get("days_back", 30),
        )

    if tool_name.startswith("get_mailchimp"):
        creds = integrations.get("mailchimp", {})
        if not creds:
            return {"error": "Mailchimp not connected"}
        if tool_name == "get_mailchimp_campaign_stats":
            return await mailchimp_service.get_campaign_stats(
                api_key=creds["api_key"],
                days_back=tool_args.get("days_back", 60),
            )
        return await mailchimp_service.get_unsubscribes(
            api_key=creds["api_key"],
            list_id=creds.get("list_id", ""),
            days_back=tool_args.get("days_back", 30),
        )

    if tool_name.startswith("get_vercel"):
        creds = integrations.get("vercel", {})
        if not creds:
            return {"error": "Vercel not connected"}
        team_id = creds.get("team_id") or None
        project_id = creds.get("project_id") or None
        if tool_name == "get_vercel_deployments":
            return await vercel_service.get_deployments(
                token=creds["token"],
                team_id=team_id,
                project_id=project_id,
                days_back=tool_args.get("days_back", 30),
            )
        if tool_name == "get_vercel_failed_deployments":
            return await vercel_service.get_failed_deployments(
                token=creds["token"],
                team_id=team_id,
                project_id=project_id,
                days_back=tool_args.get("days_back", 30),
            )
        return await vercel_service.get_deployment_logs(
            token=creds["token"],
            deployment_id=tool_args["deployment_id"],
            team_id=team_id,
        )

    if tool_name.startswith("get_github"):
        creds = integrations.get("github", {})
        if not creds:
            return {"error": "GitHub not connected"}
        repos = [
            r.strip()
            for r in creds.get("repos", "").replace(",", "\n").splitlines()
            if r.strip()
        ]
        if not repos:
            return {"error": "No GitHub repositories configured"}
        if tool_name == "get_github_commits":
            results = await asyncio.gather(
                *[
                    github_service.get_recent_commits(
                        token=creds["token"],
                        repo=repo,
                        days_back=tool_args.get("days_back", 30),
                    )
                    for repo in repos
                ]
            )
            return [
                {**commit, "repo": repo}
                for repo, commits in zip(repos, results)
                for commit in commits
            ]
        results_rel = await asyncio.gather(
            *[
                github_service.get_recent_releases(token=creds["token"], repo=repo)
                for repo in repos
            ]
        )
        return [
            {**release, "repo": repo}
            for repo, releases in zip(repos, results_rel)
            for release in releases
        ]

    if tool_name.startswith("get_chargebee"):
        creds = integrations.get("chargebee", {})
        if not creds:
            return {"error": "Chargebee not connected"}
        site = creds.get("site", "")
        api_key = creds.get("api_key", "")
        data_center = creds.get("data_center", "us")
        if tool_name == "get_chargebee_cancellations":
            return await chargebee_service.get_cancellations(
                site=site,
                api_key=api_key,
                data_center=data_center,
                start_date=tool_args["start_date"],
                end_date=tool_args["end_date"],
            )
        return await chargebee_service.get_subscription_overview(
            site=site,
            api_key=api_key,
            data_center=data_center,
            days=tool_args.get("days", 30),
        )

    if tool_name in ("list_supabase_tables", "get_supabase_table"):
        creds = integrations.get("supabase", {})
        if not creds:
            return {"error": "Supabase not connected"}
        project_url = creds.get("project_url", "")
        api_key = creds.get("api_key", "")
        if tool_name == "list_supabase_tables":
            return await supabase_service.list_tables(
                project_url=project_url,
                api_key=api_key,
            )
        return await supabase_service.query_table(
            project_url=project_url,
            api_key=api_key,
            table=tool_args["table"],
            limit=tool_args.get("limit", 100),
            order=tool_args.get("order"),
            filters=tool_args.get("filters"),
        )

    return {"error": f"Unknown tool: {tool_name}"}


async def stream_investigation(
    question: str,
    integrations: dict[str, dict[str, Any]],
    model: str,
    api_key: str,
    base_url: str = "https://models.github.ai/inference",
    business_profile: dict[str, Any] | None = None,
    conversation_history: list[dict[str, str]] | None = None,
) -> AsyncGenerator[dict[str, Any], None]:
    """Stream an investigation as SSE-ready event dicts.

    Yields dicts with a "type" key:
    - ``{"type": "status", "message": str}`` — progress update
    - ``{"type": "token", "content": str}`` — synthesis text token
    - ``{"type": "result", "data": dict}`` — final structured result (internal)
    """
    client = _client(api_key=api_key, base_url=base_url)
    connected = list(integrations.keys())
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": build_system_prompt(business_profile)},
    ]
    for prior in conversation_history or []:
        messages.append({"role": "user", "content": prior["question"]})
        messages.append({"role": "assistant", "content": prior["answer"]})
    messages.append(
        {
            "role": "user",
            "content": f"Connected integrations: {connected}\n\nQuestion: {question}",
        }
    )

    available_tools = [
        t
        for t in TOOLS
        if any(connected_tool in t["function"]["name"] for connected_tool in connected)
    ] or TOOLS

    yield {"type": "status", "message": "Analysing your question…"}

    # Accumulated token counts across all LLM calls in this investigation.
    prompt_tokens = 0
    completion_tokens = 0

    try:
        response = await client.chat.completions.create(  # type: ignore[call-overload]
            model=model,
            messages=messages,  # type: ignore[arg-type]
            tools=available_tools,  # type: ignore[arg-type]
            tool_choice="auto",
        )
    except AuthenticationError as exc:
        logger.error(
            "AI 401 Unauthorized (tool-selection call) — model=%s base_url=%s key_set=%s body=%s",
            model,
            base_url,
            bool(api_key),
            exc.body,
        )
        raise

    if response.usage:
        prompt_tokens += response.usage.prompt_tokens
        completion_tokens += response.usage.completion_tokens

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
        if any("chargebee" in t for t in tool_names):
            yield {"type": "status", "message": "Fetching Chargebee billing data…"}

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
                "chargebee",
            ):
                if source in tool_name and source not in sources_used:
                    sources_used.append(source)

        yield {"type": "status", "message": "Writing investigation report…"}

        full_content = ""
        try:
            stream = cast(
                AsyncStream[ChatCompletionChunk],
                await client.chat.completions.create(
                    model=model,
                    messages=messages,  # type: ignore[arg-type]
                    stream=True,
                    stream_options={"include_usage": True},  # type: ignore[call-overload]
                ),
            )
        except AuthenticationError as exc:
            logger.error(
                "AI 401 Unauthorized (synthesis call) — model=%s base_url=%s key_set=%s body=%s",
                model,
                base_url,
                bool(api_key),
                exc.body,
            )
            raise
        async for chunk in stream:
            # Last chunk carries usage when stream_options.include_usage=True
            if chunk.usage:
                prompt_tokens += chunk.usage.prompt_tokens
                completion_tokens += chunk.usage.completion_tokens
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta.content
            if delta:
                full_content += delta
                yield {"type": "token", "content": delta}

        final_content = full_content
    else:
        final_content = assistant_message.content or "{}"
        # Stream character-by-character for consistency
        for char in final_content:
            yield {"type": "token", "content": char}

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
    result_dict["token_usage"] = {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
    }
    yield {"type": "result", "data": result_dict}


async def run_investigation(
    question: str,
    integrations: dict[str, dict[str, Any]],
    model: str,
    api_key: str,
    base_url: str = "https://models.github.ai/inference",
    business_profile: dict[str, Any] | None = None,
    conversation_history: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Non-streaming wrapper around stream_investigation."""
    result: dict[str, Any] = {}
    async for event in stream_investigation(
        question=question,
        integrations=integrations,
        model=model,
        api_key=api_key,
        base_url=base_url,
        business_profile=business_profile,
        conversation_history=conversation_history,
    ):
        if event["type"] == "result":
            result = event["data"]
    return result
