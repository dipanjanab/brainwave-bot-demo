import re


FORBIDDEN = re.compile(r"\b(ALTER|ATTACH|CREATE|DELETE|DETACH|DROP|INSERT|PRAGMA|REINDEX|REPLACE|UPDATE|VACUUM)\b", re.I)
ALLOWED_TABLES = {"stories"}


def validate_sql(sql: str) -> str:
    candidate = sql.strip()
    if not candidate:
        raise ValueError("SQL cannot be empty.")
    if ";" in candidate.rstrip(";") or FORBIDDEN.search(candidate):
        raise ValueError("Only one read-only SELECT query is allowed.")
    if not re.match(r"^(SELECT|WITH)\b", candidate, re.I):
        raise ValueError("Only SELECT or CTE queries are allowed.")
    tables = {name.lower() for name in re.findall(r"\b(?:FROM|JOIN)\s+([a-zA-Z_][\w]*)", candidate, re.I)}
    if not tables.issubset(ALLOWED_TABLES):
        raise ValueError("The query references a table outside the approved allowlist.")
    return candidate.rstrip(";")
