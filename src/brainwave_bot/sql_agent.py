from __future__ import annotations

import re
from typing import Any

from .models import QueryPlan, SQLRequest


class SQLAgent:
    def __init__(self, llm: Any | None = None):
        self.llm = llm

    @staticmethod
    def has_time_filter(question: str) -> bool:
        return bool(
            re.search(
                r"\b(fy\s*['-]?\d{2,4}|this year|current year|during|in \d{4})\b",
                question.lower(),
            )
        )

    def make_plan(self, question: str, resolved: dict[str, Any]) -> QueryPlan:
        if self.llm:
            prompt = (
                "You plan governed analytics queries. Return only the structured QueryPlan. "
                "Allowed metrics: submission_count, approved_submission_count, revenue. "
                "Allowed group_by: market, status, or null. Never invent dimensions.\n"
                f"Question: {question}\nResolved context: {resolved}"
            )
            planned = self.llm.with_structured_output(QueryPlan).invoke(prompt)
            planned.market = planned.market or resolved.get("market")
            planned.start_date = planned.start_date or resolved.get("start_date")
            planned.end_date = planned.end_date or resolved.get("end_date")
            return planned

        lower = question.lower()
        revenue_matches = re.search(r"\b(revenue|value|worth|sales)\b", lower)
        highest_revenue_by_market = bool(
            re.search(
                r"\b(which|what)\s+market\b.*\b(highest|most|largest|top)\s+(revenue|value|worth|sales)\b"
                r"|\b(highest|most|largest|top)\s+(revenue|value|worth|sales)\b.*\b(by|per|each)\s+market\b"
                r"|\bmarket\b.*\b(highest|most|largest|top)\s+(revenue|value|worth|sales)\b"
                r"|\b(show|shows|showing)\s+(highest|most|largest|top)\s+(revenue|value|worth|sales)\b",
                lower,
            )
        )
        metric = "revenue" if revenue_matches else (
            "approved_submission_count" if "approved" in lower else "submission_count"
        )
        group_by = None
        if highest_revenue_by_market or re.search(
            r"\b(by|per|each)\s+market\b|highest\s+market|most\s+(stories|submissions)|which\s+market",
            lower,
        ):
            group_by = "market"
        elif re.search(r"\b(by|per|each)\s+status\b", lower):
            group_by = "status"
        return QueryPlan(
            metric=metric,
            market=resolved.get("market"),
            start_date=resolved.get("start_date") if self.has_time_filter(question) else None,
            end_date=resolved.get("end_date") if self.has_time_filter(question) else None,
            group_by=group_by,
        )

    def compile(self, plan: QueryPlan) -> SQLRequest:
        params: dict[str, Any] = {
            "start_date": plan.start_date,
            "end_date": plan.end_date,
        }
        where = []
        if plan.start_date:
            where.append("submitted_at >= :start_date")
        if plan.end_date:
            where.append("submitted_at <= :end_date")
        if plan.market:
            where.append("market = :market")
            params["market"] = plan.market
        if plan.metric == "approved_submission_count":
            where.append("status = :status")
            params["status"] = "Approved"

        select = (
            "SUM(revenue) AS total_revenue"
            if plan.metric == "revenue"
            else "COUNT(DISTINCT submission_id) AS submission_count"
        )
        group = ""
        order = ""
        if plan.group_by:
            select = f"{plan.group_by}, {select}"
            group = f" GROUP BY {plan.group_by}"
            order_column = "total_revenue" if plan.metric == "revenue" else "submission_count"
            order = f" ORDER BY {order_column} DESC"
        where_sql = f" WHERE {' AND '.join(where)}" if where else ""
        sql = f"SELECT {select} FROM submissions{where_sql}{group}{order}"
        return SQLRequest(sql=sql, params=params, plan=plan)

