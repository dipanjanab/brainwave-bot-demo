from __future__ import annotations

import calendar
import re
from dataclasses import dataclass
from datetime import date
from typing import Any


@dataclass(frozen=True)
class FiscalPeriod:
    label: str
    start_date: date
    end_date: date


class BusinessContextResolver:
    def __init__(self, context: dict[str, Any], fiscal_start_month: int = 4):
        self.context = context
        self.fiscal_start_month = fiscal_start_month
        self.terms = {str(k).lower(): v for k, v in context.get("terms", {}).items()}

    def fiscal_year_for(self, value: date) -> int:
        if self.fiscal_start_month == 1:
            return value.year
        return value.year + 1 if value.month >= self.fiscal_start_month else value.year

    def fiscal_period(self, fiscal_year: int) -> FiscalPeriod:
        start_year = fiscal_year if self.fiscal_start_month == 1 else fiscal_year - 1
        start = date(start_year, self.fiscal_start_month, 1)
        end_month = self.fiscal_start_month - 1 or 12
        end_year = fiscal_year
        end = date(end_year, end_month, calendar.monthrange(end_year, end_month)[1])
        return FiscalPeriod(f"FY{str(fiscal_year)[-2:]}", start, end)

    def resolve(self, question: str, today: date | None = None) -> dict[str, Any]:
        today = today or date.today()
        normalized = question.lower()
        replacements: dict[str, Any] = {}
        for phrase, canonical in sorted(self.terms.items(), key=lambda item: -len(item[0])):
            if re.search(rf"\b{re.escape(phrase)}\b", normalized):
                replacements[phrase] = canonical

        match = re.search(r"\bfy\s*['-]?(\d{2,4})\b", normalized, re.I)
        if match:
            raw = int(match.group(1))
            year = 2000 + raw if raw < 100 else raw
        elif re.search(r"\b(current|this)\s+(fiscal\s+)?year\b", normalized):
            year = self.fiscal_year_for(today)
        else:
            year = self.fiscal_year_for(today)
        period = self.fiscal_period(year)

        markets = self.context.get("dimensions", {}).get("market", [])
        market = next((m for m in markets if re.search(rf"\b{re.escape(m.lower())}\b", normalized)), None)
        for source, target in replacements.items():
            if str(target).upper() in markets:
                market = str(target).upper()

        return {
            "normalized_question": normalized,
            "term_replacements": replacements,
            "market": market,
            "fiscal_year": period.label,
            "start_date": period.start_date.isoformat(),
            "end_date": period.end_date.isoformat(),
        }
