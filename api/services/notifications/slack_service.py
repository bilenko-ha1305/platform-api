"""Slack webhook notification service."""

from __future__ import annotations

from typing import Any

import httpx


def _mrr_line(mrr_overview: dict[str, Any]) -> str:
    """Format the MRR change line for Slack."""
    start = mrr_overview.get("start_mrr")
    end = mrr_overview.get("end_mrr")
    change = mrr_overview.get("net_change")
    parts: list[str] = []
    if start is not None:
        parts.append(f"Start: *${start:,.0f}*")
    if end is not None:
        parts.append(f"End: *${end:,.0f}*")
    if change is not None:
        sign = "+" if change >= 0 else ""
        parts.append(f"Change: *{sign}${change:,.0f}*")
    return "  |  ".join(parts) if parts else "_No MRR data_"


def _confidence_emoji(confidence: str) -> str:
    return {"high": ":large_green_circle:", "medium": ":large_yellow_circle:", "low": ":red_circle:"}.get(
        confidence.lower(), ":white_circle:"
    )


def build_blocks(report: dict[str, Any], date_from: str, date_to: str) -> list[dict[str, Any]]:
    """Build Slack Block Kit blocks from a report dict.

    :param report: Structured report as returned by run_report().
    :param date_from: Report start date string.
    :param date_to: Report end date string.
    :return: List of Slack blocks.
    """
    churn = report.get("churn_analysis", {})
    growth = report.get("growth_analysis", {})
    confidence = report.get("confidence", "low")

    blocks: list[dict[str, Any]] = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f":bar_chart: Daily Report: {date_from} – {date_to}"},
        },
        {"type": "divider"},
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": report.get("executive_summary", "_No summary available_")},
        },
        {"type": "divider"},
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*MRR*\n{_mrr_line(report.get('mrr_overview', {}))}"},
                {
                    "type": "mrkdwn",
                    "text": (
                        f"*Churn*\n"
                        f"{churn.get('total_churned', 0)} cancellations"
                        + (f"  |  ${churn.get('mrr_lost', 0):,.0f} MRR lost" if churn.get("mrr_lost") else "")
                    ),
                },
                {
                    "type": "mrkdwn",
                    "text": f"*New subs*\n{growth.get('new_subscriptions', 0)}",
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Upgrades*\n{growth.get('upgrades', 0)}",
                },
            ],
        },
    ]

    if findings := report.get("key_findings"):
        text = "*Key findings*\n" + "\n".join(f"• {f}" for f in findings)
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": text}})

    if recs := report.get("recommendations"):
        text = "*Recommendations*\n" + "\n".join(f"→ {r}" for r in recs)
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": text}})

    blocks.append({
        "type": "context",
        "elements": [
            {
                "type": "mrkdwn",
                "text": f"{_confidence_emoji(confidence)} Confidence: *{confidence}*  •  Powered by Revelio",
            }
        ],
    })

    return blocks


async def post_report(
    webhook_url: str,
    report: dict[str, Any],
    date_from: str,
    date_to: str,
) -> None:
    """Post a formatted report to a Slack incoming webhook.

    :param webhook_url: Slack incoming webhook URL.
    :param report: Structured report dict.
    :param date_from: Report start date.
    :param date_to: Report end date.
    :raises httpx.HTTPStatusError: On non-2xx Slack response.
    """
    payload = {"blocks": build_blocks(report, date_from, date_to)}
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(webhook_url, json=payload)
        response.raise_for_status()
