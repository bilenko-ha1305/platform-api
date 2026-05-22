"""Shared helpers used across multiple API modules."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import HTTPException

from api.db.dao.investigation_dao import InvestigationDAO
from api.db.dao.report_dao import ReportDAO
from api.enums import Plan

REPORT_COST = 10

PLAN_LIMITS: dict[Plan, int] = {
    Plan.FREE: 3,
    Plan.SOLO: 50,
    Plan.STUDIO: -1,
}


async def check_plan_credits(
    org_id: uuid.UUID,
    plan: Plan,
    investigation_dao: InvestigationDAO,
    report_dao: ReportDAO,
    additional_cost: int = 1,
) -> None:
    """Raise HTTP 402 if the org would exceed its monthly credit limit.

    Each investigation costs 1 credit; each report costs REPORT_COST credits.

    :param org_id: Organisation UUID.
    :param plan: Current plan for limit lookup.
    :param investigation_dao: DAO used to count investigations this month.
    :param report_dao: DAO used to count reports this month.
    :param additional_cost: Credits the pending operation will consume.
    :raises HTTPException: 402 if limit would be exceeded.
    """
    limit = PLAN_LIMITS.get(plan, 3)
    if limit == -1:
        return
    inv = await investigation_dao.count_this_month(org_id)
    rep = await report_dao.count_this_month(org_id)
    used = inv + rep * REPORT_COST
    if used + additional_cost > limit:
        raise HTTPException(
            status_code=402,
            detail=(
                f"Monthly credit limit reached ({used}/{limit} credits used on the {plan} plan). "
                "Upgrade your plan to continue."
            ),
        )
