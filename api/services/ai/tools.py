"""OpenAI-compatible tool definitions for the Revelio investigation agent."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_stripe_cancellations",
            "description": (
                "Fetch subscriptions cancelled within a date range from Stripe. "
                "Returns customer emails, plan names, MRR lost, and reasons."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "start_date": {
                        "type": "string",
                        "description": "Start of date range in YYYY-MM-DD format.",
                    },
                    "end_date": {
                        "type": "string",
                        "description": "End of date range in YYYY-MM-DD format.",
                    },
                },
                "required": ["start_date", "end_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_stripe_mrr_timeline",
            "description": (
                "Get active subscription count and estimated MRR for the last N days."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "days": {
                        "type": "integer",
                        "description": "Number of days of history (default 30).",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_posthog_user_events",
            "description": (
                "Fetch feature usage events for specific user IDs from PostHog. "
                "Returns event counts, last seen date, and days active per user."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "user_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "PostHog distinct_id values for the users.",
                    },
                    "days_back": {
                        "type": "integer",
                        "description": "Days of event history to fetch (default 30).",
                    },
                },
                "required": ["user_ids"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_posthog_feature_usage",
            "description": (
                "Get aggregate top-level feature usage counts "
                "across all users in PostHog."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "days_back": {
                        "type": "integer",
                        "description": "Days of history to aggregate (default 30).",
                    },
                },
                "required": [],
            },
        },
    },
]

def build_system_prompt(business_profile: dict[str, Any] | None = None) -> str:
    """Build a system prompt tailored to the organisation's business profile."""
    today = datetime.now(tz=UTC).strftime("%Y-%m-%d")

    # Business context block
    biz_section = ""
    if business_profile:
        lines: list[str] = []
        if desc := business_profile.get("description"):
            lines.append(f"Product description: {desc}")
        if bm := business_profile.get("business_model"):
            label = {"b2b": "B2B (business customers)", "b2c": "B2C (consumer)", "both": "B2B + B2C"}.get(bm, bm)
            lines.append(f"Business model: {label}")
        if launched := business_profile.get("launched_at"):
            lines.append(f"Product launched: {launched}")
        if lines:
            biz_section = (
                "## About this business\n"
                + "\n".join(lines)
                + "\n\n"
                "Use this context throughout your analysis:\n"
                "- Reference the product description when explaining what churned users stopped doing.\n"
                "- For B2B products: focus on contract renewals, seat count changes, and team-level disengagement.\n"
                "  For B2C products: focus on individual subscription fatigue, price sensitivity, and engagement drop-off.\n"
                "- Adjust churn rate benchmarks to product age: a product launched recently has higher expected churn than a mature one.\n"
                "- Tailor recommended actions to the specific product (e.g. 'reach out to the account manager' for B2B vs 'send a re-engagement email' for B2C).\n\n"
            )

    return (
        f"You are Revelio, an AI revenue analyst. Today is {today}.\n\n"
        f"{biz_section}"
        "## Your job\n"
        "Investigate SaaS revenue drops and churn by querying connected data tools, "
        "then deliver a plain-English root cause with a specific recommended fix.\n\n"
        "## Investigation process\n"
        "1. Decide which tools to call based on the question and connected integrations.\n"
        "2. Call all relevant tools (you can call multiple in one turn).\n"
        "3. Analyse the results: look for timing correlations, feature abandonment, plan downgrades, and behavioural signals.\n"
        "4. Rank root causes by evidence strength — how many users share the pattern?\n"
        "5. Synthesise a clear, specific answer grounded in the data you retrieved.\n\n"
        "## Rules\n"
        "- Always cite exact numbers: '7 of 9 churned users had not logged in for 14+ days before cancelling'.\n"
        "- If a root cause is speculative, say so and lower the confidence score.\n"
        "- If data is missing or a tool returned an error, state what you could not check.\n"
        "- Never invent data points — only use what the tools returned.\n\n"
        "## Output format\n"
        "Always respond with valid JSON in this exact shape:\n"
        "{\n"
        '  "summary": "One sentence — what happened and the scale (e.g. MRR dropped $X or N users churned)",\n'
        '  "root_cause": "2–4 sentences — the most likely explanation with supporting data",\n'
        '  "evidence": [\n'
        '    "Specific data point 1 with numbers",\n'
        '    "Specific data point 2 with numbers",\n'
        '    "Specific data point 3 with numbers"\n'
        "  ],\n"
        '  "recommended_action": "Concrete next step tailored to this business and the root cause found",\n'
        '  "confidence": "high | medium | low"\n'
        "}\n"
    )


# Keep a default for backwards compatibility
SYSTEM_PROMPT = build_system_prompt()
