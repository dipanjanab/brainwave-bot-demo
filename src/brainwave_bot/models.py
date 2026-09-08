from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class Route(str, Enum):
    SQL = "sql"
    RAG = "rag"
    HYBRID = "hybrid"


class QueryPlan(BaseModel):
    metric: Literal["submission_count", "approved_submission_count", "revenue"] = "submission_count"
    market: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    group_by: Literal["market", "status"] | None = None
    limit: int = Field(default=20, ge=1, le=100)


class SQLRequest(BaseModel):
    sql: str
    params: dict[str, Any]
    plan: QueryPlan


class SQLResult(BaseModel):
    columns: list[str]
    rows: list[dict[str, Any]]
    row_count: int


class Answer(BaseModel):
    question: str
    route: Route
    answer: str
    resolved_terms: dict[str, Any] = Field(default_factory=dict)
    retrieved_context: list[str] = Field(default_factory=list)
    generated_sql: str | None = None
    sql_params: dict[str, Any] = Field(default_factory=dict)
    data: list[dict[str, Any]] = Field(default_factory=list)
    trace: list[str] = Field(default_factory=list)

