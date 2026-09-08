from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient

from brainwave_bot.config import Settings, load_business_context
from brainwave_bot.context import BusinessContextResolver
from brainwave_bot.models import QueryPlan, SQLRequest
from brainwave_bot.orchestrator import BrainwaveOrchestrator
from brainwave_bot.sql_tool import GuardedSQLTool, SQLGuardError
from brainwave_bot.app import create_api


def settings(tmp_path) -> Settings:
    root = Settings().root
    return Settings(
        database_path=tmp_path / "test.db",
        business_context_path=root / "data" / "business_context.yaml",
        knowledge_path=root / "knowledge",
        allowed_markets=("EMEA",),
    )


def test_fy26_and_current_year_resolve_to_april_march():
    base = Settings()
    resolver = BusinessContextResolver(load_business_context(base.business_context_path), 4)
    explicit = resolver.resolve("stories in NEMIA during FY26", date(2025, 9, 1))
    current = resolver.resolve("ideas in EMEA this year", date(2025, 9, 1))
    assert explicit["market"] == "EMEA"
    assert explicit["start_date"] == "2025-04-01"
    assert explicit["end_date"] == "2026-03-31"
    assert current["fiscal_year"] == "FY26"


def test_calendar_year_configuration():
    base = Settings()
    resolver = BusinessContextResolver(load_business_context(base.business_context_path), 1)
    resolved = resolver.resolve("ideas this year", date(2026, 9, 8))
    assert resolved["fiscal_year"] == "FY26"
    assert resolved["start_date"] == "2026-01-01"
    assert resolved["end_date"] == "2026-12-31"


def test_end_to_end_sql_count(tmp_path):
    result = BrainwaveOrchestrator(settings(tmp_path)).ask(
        "How many stories were submitted in NEMIA during FY26?"
    )
    assert result.route.value == "sql"
    assert result.data == [{"submission_count": 3}]
    assert ":market" in result.generated_sql
    assert result.sql_params["market"] == "EMEA"


def test_rag_route(tmp_path):
    result = BrainwaveOrchestrator(settings(tmp_path)).ask("What is BrainWave?")
    assert result.route.value == "rag"
    assert "discovery and insights" in result.answer


def test_hybrid_route_calls_rag_and_sql(tmp_path):
    result = BrainwaveOrchestrator(settings(tmp_path)).ask(
        "What is BrainWave, and how many ideas were submitted in EMEA in FY26?"
    )
    assert result.route.value == "hybrid"
    assert result.data == [{"submission_count": 3}]
    assert result.retrieved_context
    assert "discovery and insights" in result.answer
    assert "3 unique submissions" in result.answer


def test_sql_tool_blocks_mutation_and_unauthorized_market(tmp_path):
    bot = BrainwaveOrchestrator(settings(tmp_path))
    plan = QueryPlan(market="APAC", start_date="2025-04-01", end_date="2026-03-31")
    request = SQLRequest(
        sql="SELECT COUNT(*) FROM submissions WHERE market = :market",
        params={"market": "APAC"},
        plan=plan,
    )
    with pytest.raises(SQLGuardError):
        bot.sql_tool.run(request)

    malicious = SQLRequest(sql="DELETE FROM submissions", params={}, plan=QueryPlan())
    with pytest.raises(SQLGuardError):
        GuardedSQLTool(tmp_path / "test.db", ("EMEA",)).validate(malicious)


def test_http_api_contract():
    client = TestClient(create_api())
    response = client.post(
        "/ask", json={"question": "How many ideas were submitted in EMEA in FY26?"}
    )
    assert response.status_code == 200
    assert response.json()["data"] == [{"submission_count": 3}]
