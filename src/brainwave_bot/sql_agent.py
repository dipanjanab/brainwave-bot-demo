from __future__ import annotations

import re
from typing import Any

from .models import QueryPlan, SQLRequest


class SQLAgent:
    def __init__(self, llm: Any | None = None):
        self.llm = llm

    def make_plan(self, question: str, resolved: dict[str, Any]) -> QueryPlan:
        if self.llm:
            prompt = (
                "You plan governed analytics queries. Return only the structured QueryPlan. "
                "Allowed metrics: submission_count, approved_submission_count. "
                "Allowed group_by: market, status, or null. Never invent dimensions.\n"
                f"Question: {question}\nResolved context: {resolved}"
            )
            planned = self.llm.with_structured_output(QueryPlan).invoke(prompt)
            planned.market = planned.market or resolved.get("market")
            planned.start_date = planned.start_date or resolved.get("start_date")
            planned.end_date = planned.end_date or resolved.get("end_date")
            return planned

        lower = question.lower()
        metric = "approved_submission_count" if "approved" in lower else "submission_count"
        group_by = None
        if re.search(r"\b(by|per|each)\s+market\b|highest\s+market", lower):
            group_by = "market"
        elif re.search(r"\b(by|per|each)\s+status\b", lower):
            group_by = "status"
        return QueryPlan(
            metric=metric,
            market=resolved.get("market"),
            start_date=resolved.get("start_date"),
            end_date=resolved.get("end_date"),
            group_by=group_by,
        )

    def compile(self, plan: QueryPlan) -> SQLRequest:
        params: dict[str, Any] = {
            "start_date": plan.start_date,
            "end_date": plan.end_date,
        }
        where = ["submitted_at >= :start_date", "submitted_at <= :end_date"]
        if plan.market:
            where.append("market = :market")
            params["market"] = plan.market
        if plan.metric == "approved_submission_count":
            where.append("status = :status")
            params["status"] = "Approved"

        select = "COUNT(DISTINCT submission_id) AS submission_count"
        group = ""
        order = ""
        if plan.group_by:
            select = f"{plan.group_by}, {select}"
            group = f" GROUP BY {plan.group_by}"
            order = " ORDER BY submission_count DESC"
        sql = f"SELECT {select} FROM submissions WHERE {' AND '.join(where)}{group}{order}"
        return SQLRequest(sql=sql, params=params, plan=plan)

