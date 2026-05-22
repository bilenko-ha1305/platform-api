"""OpenAI-compatible tool definitions for the Revelio investigation agent."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from api.enums import BusinessModel

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
    {
        "type": "function",
        "function": {
            "name": "get_intercom_conversations",
            "description": (
                "Fetch recent Intercom conversations to identify support complaints, "
                "cancellation requests, and negative sentiment that precede churn."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "days_back": {
                        "type": "integer",
                        "description": "Days of conversation history to fetch (default 30).",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_mailchimp_campaign_stats",
            "description": (
                "Fetch Mailchimp email campaign send stats including open rates, "
                "click rates, and unsubscribes. Useful for correlating email engagement "
                "drops with churn spikes."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "days_back": {
                        "type": "integer",
                        "description": "Days of campaign history to fetch (default 60).",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_mailchimp_unsubscribes",
            "description": (
                "Fetch recent email list unsubscribes from Mailchimp, including reason codes. "
                "High unsubscribe rates often precede subscription cancellations."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "days_back": {
                        "type": "integer",
                        "description": "Days of unsubscribe history to fetch (default 30).",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_github_commits",
            "description": (
                "Fetch recent GitHub commits to correlate code deployments or breaking "
                "changes with churn spikes. Look for timing overlaps between deploys and "
                "cancellation surges."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "days_back": {
                        "type": "integer",
                        "description": "Days of commit history to fetch (default 30).",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_github_releases",
            "description": (
                "Fetch the most recent GitHub releases/tags. Useful for pinpointing "
                "which version was live when churn spiked."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
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
            label = {
                BusinessModel.B2B: "B2B (business customers)",
                BusinessModel.B2C: "B2C (consumer)",
                BusinessModel.BOTH: "B2B + B2C",
            }.get(BusinessModel(bm), bm)
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


def build_report_system_prompt(
    date_from: str,
    date_to: str,
    business_profile: dict[str, Any] | None = None,
) -> str:
    """Build a system prompt for period-based revenue and churn report generation."""
    today = datetime.now(tz=UTC).strftime("%Y-%m-%d")

    biz_section = ""
    if business_profile:
        lines: list[str] = []
        if desc := business_profile.get("description"):
            lines.append(f"Product description: {desc}")
        if bm := business_profile.get("business_model"):
            label = {
                BusinessModel.B2B: "B2B (business customers)",
                BusinessModel.B2C: "B2C (consumer)",
                BusinessModel.BOTH: "B2B + B2C",
            }.get(BusinessModel(bm), bm)
            lines.append(f"Business model: {label}")
        if launched := business_profile.get("launched_at"):
            lines.append(f"Product launched: {launched}")
        if lines:
            biz_section = "## About this business\n" + "\n".join(lines) + "\n\n"

    return (
        f"You are Revelio, an AI revenue analyst. Today is {today}.\n\n"
        f"{biz_section}"
        f"## Report period\n"
        f"Generate a comprehensive revenue and churn report for: **{date_from} to {date_to}**.\n\n"
        "## Your job\n"
        "Use all available tools to pull data for the exact report period above, "
        "then produce a structured analysis covering MRR, churn, and growth.\n\n"
        "## Report process\n"
        "1. Call get_stripe_cancellations with start_date and end_date set to the report period.\n"
        "2. Call get_stripe_mrr_timeline to understand the MRR trend.\n"
        "3. If PostHog is connected, call get_posthog_feature_usage for the period.\n"
        "4. Synthesise all data into a clear period report with specific numbers.\n\n"
        "## Rules\n"
        "- Always cite exact numbers and percentages.\n"
        "- If data is missing or a tool returned an error, state what could not be checked.\n"
        "- Never invent data points — only use what the tools returned.\n\n"
        "## Output format\n"
        "Always respond with valid JSON in this exact shape:\n"
        "{\n"
        f'  "title": "Revenue Report: {date_from} – {date_to}",\n'
        '  "executive_summary": "2-3 sentence overview of the period",\n'
        '  "mrr_overview": {\n'
        '    "start_mrr": <number or null>,\n'
        '    "end_mrr": <number or null>,\n'
        '    "net_change": <number or null>\n'
        "  },\n"
        '  "churn_analysis": {\n'
        '    "total_churned": <number>,\n'
        '    "mrr_lost": <number or null>,\n'
        '    "top_reasons": ["reason 1", "reason 2"]\n'
        "  },\n"
        '  "growth_analysis": {\n'
        '    "new_subscriptions": <number>,\n'
        '    "upgrades": <number>\n'
        "  },\n"
        '  "key_findings": ["Finding with numbers 1", "Finding with numbers 2"],\n'
        '  "recommendations": ["Actionable recommendation 1", "Actionable recommendation 2"],\n'
        '  "confidence": "high | medium | low"\n'
        "}\n"
    )


# Keep a default for backwards compatibility
SYSTEM_PROMPT = build_system_prompt()
