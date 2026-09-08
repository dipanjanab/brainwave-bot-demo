from __future__ import annotations

import json
import re
from typing import Any

from .config import Settings, load_business_context, load_settings
from .context import BusinessContextResolver
from .models import Answer, QueryPlan, Route, SQLRequest
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

    model_name = settings.openrouter_model
    if model_name in {"openai/gpt-4.1-mini", "openai/gpt-4.1", "openai/gpt-4o-mini"}:
        model_name = "openai/gpt-4o-mini"

    return ChatOpenAI(
        model=model_name,
        api_key=settings.openrouter_api_key,
        base_url=settings.openrouter_base_url,
        temperature=0,
        max_tokens=300,
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

    @staticmethod
    def is_market_count_question(question: str) -> bool:
        lower = question.lower()
        return bool(
            re.search(
                r"\b(how many|count)\s+(markets?|market regions?)\b|\bmarkets?\s+(are|is)\s+there\b|\bhow many\s+regions\b",
                lower,
            )
        )

    @staticmethod
    def is_category_count_question(question: str) -> bool:
        lower = question.lower()
        return bool(
            re.search(
                r"\b(how many|count)\s+(categories|themes)\b|\b(categories|themes)\s+(are|is)\s+there\b|\b(list|name)\s+(the\s+)?(categories|themes)\b",
                lower,
            )
        )

    @staticmethod
    def is_business_data_question(question: str) -> bool:
        lower = question.lower()
        return bool(
            re.search(
                r"\b(how many|count|total|revenue|highest|lowest|most|least)\b|\b(show|list)\b.*\b(stories?|ideas?|submissions?)\b|\b(submissions?|stories?|ideas?)\s+by\s+(market|status)\b|\b(submitted|approved)\b.*\b(in|during|this year|fy\d+)\b",
                lower,
            )
        )

    @staticmethod
    def is_knowledge_definition_question(question: str) -> bool:
        return bool(
            re.search(
                r"\b(what does|what is|define|definition of|what qualifies|what fiscal calendar|how does)\b",
                question.lower(),
            )
        )

    def route(self, question: str) -> Route:
        lower = question.lower()
        if self.is_market_count_question(question):
            return Route.SQL
        if self.is_category_count_question(question):
            return Route.SQL
        has_data_intent = self.is_business_data_question(question)
        has_context_intent = bool(re.search(r"\b(what is|explain|define|how does|what can)\b", lower))
        if self.is_knowledge_definition_question(question) and not re.search(
            r"\b(how many|count|total|highest|lowest|during|this year|fy\d+)\b",
            lower,
        ):
            return Route.RAG
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

        if self.is_market_count_question(question):
            markets = list(self.settings.allowed_markets)
            resolved = {
                **resolved,
                "market_count": len(markets),
                "markets": markets,
            }
            data = [{"market_count": len(markets)}]
            answer_text = (
                f"There are {len(markets)} markets configured: " + ", ".join(markets) + "."
            )
            trace.append("orchestrator: resolved configured market list")
            trace.append("orchestrator: formulated final answer")
            return Answer(
                question=question,
                route=route,
                answer=answer_text,
                resolved_terms=resolved,
                retrieved_context=contexts,
                generated_sql=None,
                sql_params=params,
                data=data,
                trace=trace,
            )

        if self.is_category_count_question(question):
            request = SQLRequest(
                sql="SELECT DISTINCT theme AS category FROM submissions ORDER BY theme",
                params={},
                plan=QueryPlan(),
            )
            result = self.sql_tool.run(request)
            categories = [row["category"] for row in result.rows]
            resolved = {
                **resolved,
                "category_count": len(categories),
                "categories": categories,
            }
            data = [{"category_count": len(categories), "categories": categories}]
            answer_text = (
                f"There are {len(categories)} categories: " + ", ".join(categories) + "."
            )
            trace.append("orchestrator: queried distinct theme categories")
            trace.append("orchestrator: formulated final answer")
            return Answer(
                question=question,
                route=route,
                answer=answer_text,
                resolved_terms=resolved,
                retrieved_context=contexts,
                generated_sql=request.sql,
                sql_params=request.params,
                data=data,
                trace=trace,
            )

        if route in (Route.RAG, Route.HYBRID):
            knowledge_question = question
            for source, target in resolved.get("term_replacements", {}).items():
                knowledge_question = re.sub(
                    rf"\b{re.escape(source)}\b",
                    str(target),
                    knowledge_question,
                    flags=re.IGNORECASE,
                )
            contexts = (
                self.rag_chain.invoke(knowledge_question)
                if self.rag_chain
                else self.retriever.retrieve(knowledge_question)
            )
            trace.append(f"rag: retrieved {len(contexts)} knowledge document(s)")

        if route == Route.RAG and not contexts:
            answer_text = "Please reframe the question."
            trace.append("rag: no matching knowledge found")
            return Answer(
                question=question,
                route=route,
                answer=answer_text,
                resolved_terms=resolved,
                retrieved_context=contexts,
                generated_sql=None,
                sql_params=params,
                data=data,
                trace=trace,
            )

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
                return "Please reframe the question."
            return self._best_knowledge_paragraph(question, contexts)
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
        if data and data[0].get("market") and re.search(r"\b(most|highest|largest|top)\b", question.lower()):
            top = data[0]
            if "total_revenue" in top:
                amount = top["total_revenue"]
                return (
                    f"{top['market']} had the highest revenue in {resolved.get('fiscal_year', 'the selected period')} "
                    f"at {amount:,.2f}."
                )
            return (
                f"{top['market']} submitted the most stories in {resolved.get('fiscal_year', 'the selected period')} "
                f"with {top['submission_count']} submissions."
            )
        if data and data[0].get("total_revenue") is not None:
            amount = data[0]["total_revenue"]
            market = f" for {resolved['market']}" if resolved.get("market") else ""
            return f"The total revenue{market} was {amount:,.2f} during {resolved['fiscal_year']}."
        lines = [", ".join(f"{key}={value}" for key, value in row.items()) for row in data]
        return f"Results for {resolved['fiscal_year']}: " + "; ".join(lines)

    @staticmethod
    def _best_knowledge_paragraph(question: str, contexts: list[str]) -> str:
        stop_words = {
            "a", "an", "and", "are", "can", "does", "how", "is", "of", "the", "what",
        }
        query_words = {
            word
            for word in re.findall(r"[a-z0-9]+", question.lower())
            if word not in stop_words
        }
        candidates = [
            line.strip()
            for context in contexts
            for line in context.splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]
        if not candidates:
            return "Please reframe the question."
        best = max(
            candidates,
            key=lambda line: len(query_words & set(re.findall(r"[a-z0-9]+", line.lower()))),
        )
        if not query_words or not query_words & set(re.findall(r"[a-z0-9]+", best.lower())):
            return "Please reframe the question."
        return best
