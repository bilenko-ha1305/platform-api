"""LiteLLM tool definitions for the ChurnLens investigation agent."""

from __future__ import annotations

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

SYSTEM_PROMPT = (
    "You are ChurnLens, an AI analyst that investigates SaaS revenue drops.\n\n"
    "When the user asks about MRR or churn:\n"
    "1. Call the relevant data tools (multiple tools in one turn if needed)\n"
    "2. Find patterns: timing, feature abandonment, behaviour signals\n"
    "3. Rank root causes by how many users share the pattern\n\n"
    "Always respond in this exact JSON format:\n"
    "{\n"
    '  "summary": "One sentence summary of what happened",\n'
    '  "root_cause": "The most likely explanation with supporting evidence",\n'
    '  "evidence": ["Bullet 1", "Bullet 2", "Bullet 3"],\n'
    '  "recommended_action": "Specific, actionable next step",\n'
    '  "confidence": "high|medium|low"\n'
    "}\n\n"
    "If you lack data, say so clearly in root_cause.\n"
    'Always cite specific numbers (e.g. "7 of 8 churned users stopped using X").'
)
