from __future__ import annotations

import sqlite3
from pathlib import Path

from .models import SQLRequest, SQLResult

try:
    import sqlglot
    from sqlglot import exp
except ImportError:
    sqlglot = None
    exp = None


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS submissions (
  submission_id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  market TEXT NOT NULL,
  client TEXT NOT NULL,
  theme TEXT NOT NULL,
  program TEXT NOT NULL,
  status TEXT NOT NULL,
  submitted_at TEXT NOT NULL
);
"""

SAMPLE_ROWS = [
    ("I001", "AI service assistant", "EMEA", "Contoso", "AI", "Accelerate", "Approved", "2025-05-12"),
    ("I002", "Green logistics", "EMEA", "Fabrikam", "Sustainability", "Elevate", "Submitted", "2025-07-03"),
    ("I003", "Smart factory alerts", "EMEA", "Contoso", "Automation", "Accelerate", "Approved", "2026-01-18"),
    ("I004", "Claims copilot", "AMERICAS", "Northwind", "AI", "Elevate", "Approved", "2025-08-09"),
    ("I005", "Retail demand sensing", "APAC", "Adventure", "Analytics", "Accelerate", "Submitted", "2025-11-22"),
    ("I006", "Knowledge graph", "EMEA", "Fabrikam", "AI", "Discover", "Rejected", "2024-09-15"),
    ("I007", "Circular packaging", "APAC", "Adventure", "Sustainability", "Elevate", "Approved", "2026-02-02"),
]


def initialize_demo_database(path: Path) -> None:
    with sqlite3.connect(path) as connection:
        connection.executescript(SCHEMA_SQL)
        connection.executemany(
            "INSERT OR IGNORE INTO submissions VALUES (?, ?, ?, ?, ?, ?, ?, ?)", SAMPLE_ROWS
        )


class SQLGuardError(ValueError):
    pass


class GuardedSQLTool:
    ALLOWED_TABLES = {"submissions"}

    def __init__(self, database_path: Path, allowed_markets: tuple[str, ...]):
        self.database_path = database_path
        self.allowed_markets = set(allowed_markets)

    def validate(self, request: SQLRequest) -> None:
        sql = request.sql.strip()
        if sqlglot is None:
            lowered = sql.lower()
            blocked = ("insert ", "update ", "delete ", "drop ", "alter ", "pragma ", ";")
            if not lowered.startswith("select ") or any(word in lowered for word in blocked):
                raise SQLGuardError("Only one read-only SELECT statement is allowed")
            if " submissions " not in f" {lowered} ":
                raise SQLGuardError("Query references a non-allowlisted table")
        else:
            statements = sqlglot.parse(sql, read="sqlite")
            if len(statements) != 1 or not isinstance(statements[0], exp.Select):
                raise SQLGuardError("Only one SELECT statement is allowed")
            tree = statements[0]
            prohibited = (exp.Insert, exp.Update, exp.Delete, exp.Drop, exp.Alter, exp.Command)
            if any(tree.find(node_type) for node_type in prohibited):
                raise SQLGuardError("Mutation and command nodes are prohibited")
            tables = {table.name.lower() for table in tree.find_all(exp.Table)}
            if not tables or not tables <= self.ALLOWED_TABLES:
                raise SQLGuardError(f"Tables are not allowlisted: {sorted(tables)}")

        market = request.params.get("market")
        if market and market not in self.allowed_markets:
            raise SQLGuardError(f"Market {market!r} is outside this user's access scope")
        if request.plan.market and ":market" not in request.sql:
            raise SQLGuardError("Market-scoped query must use the bound :market parameter")

    def run(self, request: SQLRequest) -> SQLResult:
        self.validate(request)
        connection = sqlite3.connect(f"file:{self.database_path}?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
        try:
            rows = connection.execute(request.sql, request.params).fetchmany(request.plan.limit)
        finally:
            connection.close()
        records = [dict(row) for row in rows]
        columns = list(records[0]) if records else []
        return SQLResult(columns=columns, rows=records, row_count=len(records))

