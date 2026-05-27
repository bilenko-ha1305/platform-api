"""OpenAI-compatible tool definitions for the Synvar investigation agent."""

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
            "name": "get_stripe_subscription_history",
            "description": (
                "Fetch all Stripe subscriptions (active, cancelled, trialing — any status) "
                "sorted oldest-first. Use this to answer questions like 'when did I get my first user', "
                "'who are my longest-running customers', or 'how many subscribers did I have on date X'. "
                "Returns customer email, plan, status, and created_at date for each subscription."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "days_back": {
                        "type": "integer",
                        "description": "How far back to search in days (default 730 = 2 years). Use 1825 for 5 years.",
                    },
                },
                "required": [],
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
            "name": "get_paypal_transactions",
            "description": (
                "Fetch PayPal transactions for a date range. "
                "Returns transaction amounts, statuses, and payer emails."
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
            "name": "get_paypal_subscription_cancellations",
            "description": (
                "Fetch PayPal subscription cancellation events for the last N days. "
                "Returns payer emails and cancellation dates."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "days_back": {
                        "type": "integer",
                        "description": "Days of history to fetch (default 30).",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_vercel_deployments",
            "description": (
                "Fetch recent Vercel deployments with their state (READY/ERROR/CANCELED). "
                "Use to correlate broken deploys with churn or support spikes."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "days_back": {
                        "type": "integer",
                        "description": "Days of deployment history to fetch (default 30).",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_vercel_failed_deployments",
            "description": (
                "Return only Vercel deployments that errored or were cancelled. "
                "High failure rates often precede user complaints and churn."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "days_back": {
                        "type": "integer",
                        "description": "Days of history to scan (default 30).",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_vercel_deployment_logs",
            "description": (
                "Fetch stderr/error log lines for a specific Vercel deployment. "
                "Call after get_vercel_failed_deployments to inspect what went wrong."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "deployment_id": {
                        "type": "string",
                        "description": "Vercel deployment UID (e.g. dpl_xxx).",
                    },
                },
                "required": ["deployment_id"],
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
    {
        "type": "function",
        "function": {
            "name": "get_chargebee_cancellations",
            "description": (
                "Fetch subscriptions cancelled within a date range from Chargebee. "
                "Returns customer IDs, plan names, MRR lost, and cancellation dates."
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
            "name": "get_chargebee_subscription_overview",
            "description": (
                "Get active subscription count and estimated MRR from Chargebee "
                "for the last N days."
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
            "name": "list_supabase_tables",
            "description": (
                "List all tables available in the user's Supabase database. "
                "Call this first to discover table names before querying specific tables."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_supabase_table",
            "description": (
                "Fetch rows from a specific table in the user's Supabase database. "
                "Use to query users, events, subscriptions, or any custom business data "
                "that can help explain churn patterns or answer questions about the product."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "table": {
                        "type": "string",
                        "description": "Table name to query.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum rows to return (default 100, max 500).",
                    },
                    "order": {
                        "type": "string",
                        "description": (
                            "PostgREST order expression, e.g. 'created_at.desc' to get "
                            "the most recent rows first."
                        ),
                    },
                    "filters": {
                        "type": "object",
                        "description": (
                            "Column-level PostgREST filters as key-value pairs. "
                            "e.g. {\"status\": \"eq.active\", \"plan\": \"eq.pro\"}. "
                            "Supported operators: eq, neq, lt, lte, gt, gte, like, ilike."
                        ),
                        "additionalProperties": {"type": "string"},
                    },
                },
                "required": ["table"],
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
        f"You are Synvar, an AI revenue analyst assistant. Today is {today}.\n\n"
        f"{biz_section}"
        "## Your job\n"
        "Answer any question about the user's business by querying their connected data tools. "
        "Questions range from factual lookups ('when did I get my first user?', 'who are my top customers?') "
        "to analytical investigations ('why did MRR drop last month?', 'what caused the churn spike?'). "
        "Always fetch real data — never infer or estimate when a tool can give the exact answer.\n\n"
        "## Process\n"
        "1. Read the question carefully. Identify what data is needed to answer it directly.\n"
        "2. Call all tools required to answer the question. For factual lookups, use wide date ranges "
        "   (e.g. days=365 or start_date far in the past) to capture full history.\n"
        "3. Extract the precise answer from the tool results. Quote exact values, dates, and names.\n"
        "4. If the question is analytical (a 'why' or 'how' question), also identify root causes ranked by evidence.\n\n"
        "## Rules\n"
        "- NEVER speculate or infer when tools can return the real data. If the user asks 'when was my first user', "
        "  call get_stripe_mrr_timeline with days=730 or get_stripe_cancellations with a wide range to find the earliest record — "
        "  do not guess based on the launch date.\n"
        "- Always cite exact values from tool results: dates, amounts, emails, counts.\n"
        "- If a tool returned an error or insufficient data, say so explicitly in the summary.\n"
        "- Never invent data points — only use what the tools returned.\n"
        "- Set confidence to 'high' only when the answer comes directly from tool data.\n\n"
        "## Output format\n"
        "Always respond with valid JSON in this exact shape:\n"
        "{\n"
        '  "summary": "Direct answer to the question in 1–2 sentences, citing exact numbers/dates from the data",\n'
        '  "root_cause": "For analytical questions: 2–4 sentences explaining why. For factual questions: empty string or additional context",\n'
        '  "evidence": [\n'
        '    "Exact data point with number/date/name from tool result",\n'
        '    "Exact data point 2",\n'
        '    "Exact data point 3 (omit if not applicable)"\n'
        "  ],\n"
        '  "recommended_action": "Next step if actionable, otherwise empty string",\n'
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
        f"You are Synvar, an AI revenue analyst. Today is {today}.\n\n"
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
