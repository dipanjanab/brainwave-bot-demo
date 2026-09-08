from __future__ import annotations

import json
import re
from typing import Any

from .config import Settings, load_business_context, load_settings
from .context import BusinessContextResolver
from .models import Answer, Route
from .rag import KnowledgeRetriever
from .sql_agent import SQLAgent
from .sql_tool import GuardedSQLTool, initialize_demo_database

try:
    from langchain_core.runnables import RunnableLambda
except ImportError:
    RunnableLambda = None


def build_llm(settings: Settings) -> Any | None:
    if not settings.llm_enabled:
        return None
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=settings.openrouter_model,
        api_key=settings.openrouter_api_key,
        base_url=settings.openrouter_base_url,
        temperature=0,
        default_headers={
            "HTTP-Referer": "https://example.local/brainwave",
            "X-Title": "BrainWave Bot Prototype",
        },
    )


class BrainwaveOrchestrator:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or load_settings()
        initialize_demo_database(self.settings.database_path)
        context = load_business_context(self.settings.business_context_path)
        self.resolver = BusinessContextResolver(context, self.settings.fiscal_start_month)
        self.retriever = KnowledgeRetriever(self.settings.knowledge_path)
        self.llm = build_llm(self.settings)
        self.sql_agent = SQLAgent(self.llm)
        self.sql_tool = GuardedSQLTool(self.settings.database_path, self.settings.allowed_markets)
        # LCEL runnables make component hand-offs explicit and independently testable.
        self.context_chain = RunnableLambda(self.resolver.resolve) if RunnableLambda else None
        self.rag_chain = RunnableLambda(self.retriever.retrieve) if RunnableLambda else None

    def route(self, question: str) -> Route:
        lower = question.lower()
        has_data_intent = bool(re.search(r"\b(how many|count|total|highest|lowest|by market|by status)\b", lower))
        has_context_intent = bool(re.search(r"\b(what is|explain|define|how does|what can)\b", lower))
        if has_data_intent and has_context_intent:
            return Route.HYBRID
        if has_data_intent:
            return Route.SQL
        return Route.RAG

    def ask(self, question: str) -> Answer:
        route = self.route(question)
        trace = ["orchestrator: received question", f"orchestrator: route={route.value}"]
        resolved = self.context_chain.invoke(question) if self.context_chain else self.resolver.resolve(question)
        trace.append("context: business terms and fiscal dates resolved")
        contexts: list[str] = []
        data: list[dict[str, Any]] = []
        sql = None
        params: dict[str, Any] = {}

        if route in (Route.RAG, Route.HYBRID):
            contexts = self.rag_chain.invoke(question) if self.rag_chain else self.retriever.retrieve(question)
            trace.append(f"rag: retrieved {len(contexts)} knowledge document(s)")

        if route in (Route.SQL, Route.HYBRID):
            plan = self.sql_agent.make_plan(question, resolved)
            trace.append("sql_agent: created typed query plan")
            request = self.sql_agent.compile(plan)
            sql, params = request.sql, request.params
            trace.append("sql_agent: compiled parameterized SQL")
            result = self.sql_tool.run(request)
            data = result.rows
            trace.append("sql_tool: validated AST/access scope and executed query")

        answer_text = self._formulate(question, route, resolved, contexts, data)
        trace.append("orchestrator: formulated final answer")
        return Answer(
            question=question,
            route=route,
            answer=answer_text,
            resolved_terms=resolved,
            retrieved_context=contexts,
            generated_sql=sql,
            sql_params=params,
            data=data,
            trace=trace,
        )

    def _formulate(
        self,
        question: str,
        route: Route,
        resolved: dict[str, Any],
        contexts: list[str],
        data: list[dict[str, Any]],
    ) -> str:
        if self.llm:
            prompt = (
                "Answer the business user's question concisely. Use only the supplied context and data. "
                "Never change numeric values. If data is empty, say no matching data was found.\n"
                f"Question: {question}\nResolved: {json.dumps(resolved)}\n"
                f"Knowledge: {json.dumps(contexts)}\nData: {json.dumps(data)}"
            )
            return str(self.llm.invoke(prompt).content)

        if route == Route.RAG:
            if not contexts:
                return "I could not find that information in the BrainWave knowledge base."
            paragraphs = [line.strip() for line in contexts[0].splitlines() if line.strip() and not line.startswith("#")]
            return paragraphs[0]
        if not data:
            return "No matching data was found for the resolved filters."
        if len(data) == 1 and "submission_count" in data[0] and len(data[0]) == 1:
            market = f" in {resolved['market']}" if resolved.get("market") else ""
            data_answer = (
                f"There were {data[0]['submission_count']} unique submissions{market} "
                f"during {resolved['fiscal_year']}."
            )
            if route == Route.HYBRID and contexts:
                paragraphs = [
                    line.strip()
                    for line in contexts[0].splitlines()
                    if line.strip() and not line.startswith("#")
                ]
                return f"{paragraphs[0]} {data_answer}"
            return data_answer
        lines = [", ".join(f"{key}={value}" for key, value in row.items()) for row in data]
        return f"Results for {resolved['fiscal_year']}: " + "; ".join(lines)
