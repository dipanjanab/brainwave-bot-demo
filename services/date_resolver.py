from datetime import date
import re


FISCAL_YEAR_START_MONTH = 4


def resolve_fiscal_year(fy: str) -> dict:
    match = re.fullmatch(r"FY(\d{2})", fy.strip().upper())
    if not match:
        raise ValueError("Fiscal year must be formatted like FY26.")
    end_year = 2000 + int(match.group(1))
    return {
        "label": f"FY{match.group(1)}",
        "start_date": date(end_year - 1, FISCAL_YEAR_START_MONTH, 1),
        "end_date": date(end_year, FISCAL_YEAR_START_MONTH, 1),
    }


def get_current_fiscal_year(today: date | None = None) -> str:
    today = today or date.today()
    end_year = today.year + 1 if today.month >= FISCAL_YEAR_START_MONTH else today.year
    return f"FY{end_year % 100:02d}"


def resolve_period(expression: str, today: date | None = None) -> dict | None:
    """Resolve supported fiscal expressions to a half-open date interval."""
    today = today or date.today()
    normalized = expression.strip().lower()
    fy_match = re.search(r"\bfy\s?(\d{2})\b", normalized)
    if fy_match:
        return resolve_fiscal_year(f"FY{fy_match.group(1)}")
    if any(term in normalized for term in ("this year", "current year")):
        return resolve_fiscal_year(get_current_fiscal_year(today))
    if "last year" in normalized or "previous year" in normalized:
        current = resolve_fiscal_year(get_current_fiscal_year(today))
        return resolve_fiscal_year(f"FY{(int(current['label'][-2:]) - 1) % 100:02d}")
    if "ytd" in normalized or "year to date" in normalized:
        current = resolve_fiscal_year(get_current_fiscal_year(today))
        return {**current, "label": f"{current['label']} YTD", "end_date": today}
    return None
