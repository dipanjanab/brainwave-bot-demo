from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

if __package__ in (None, ""):
    root = Path(__file__).resolve().parents[2]
    src_dir = root / "src"
    if str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))
    from brainwave_bot.config import load_settings
    from brainwave_bot.orchestrator import BrainwaveOrchestrator
else:
    from .config import load_settings
    from .orchestrator import BrainwaveOrchestrator


def _reset_chat_history() -> None:
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []


def _append_chat_history(question: str, result: object) -> None:
    _reset_chat_history()
    st.session_state.chat_history.append(
        {
            "question": question,
            "answer": getattr(result, "answer", str(result)),
            "route": getattr(getattr(result, "route", None), "value", None),
        }
    )


def _render_result(result: object) -> None:
    st.subheader("Answer")
    st.write(getattr(result, "answer", str(result)))

    if getattr(result, "route", None):
        st.caption(f"Route: {result.route.value}")

    with st.expander("Resolved terms"):
        st.json(getattr(result, "resolved_terms", {}))

    if getattr(result, "generated_sql", None):
        with st.expander("Generated SQL"):
            st.code(result.generated_sql)
            if result.sql_params:
                st.json(result.sql_params)

    if getattr(result, "data", None):
        with st.expander("Query data"):
            st.json(result.data)

    if getattr(result, "trace", None):
        with st.expander("Execution trace"):
            st.json(result.trace)


@st.cache_resource
def get_bot(knowledge_signature: tuple[tuple[str, int], ...]):
    settings = load_settings()
    return BrainwaveOrchestrator(settings=settings)


def _knowledge_signature(knowledge_path: Path) -> tuple[tuple[str, int], ...]:
    return tuple(
        sorted(
            (path.name, path.stat().st_mtime_ns)
            for path in knowledge_path.glob("*.md")
        )
    )


def _render_chat_history() -> None:
    _reset_chat_history()
    if not st.session_state.chat_history:
        st.info("No chat history yet. Submit a question to start the conversation.")
        return

    for entry in st.session_state.chat_history:
        with st.chat_message("user"):
            st.write(entry["question"])
        with st.chat_message("assistant"):
            st.write(entry["answer"])
            if entry.get("route"):
                st.caption(f"Route: {entry['route']}")


def run_app() -> None:
    st.set_page_config(page_title="BrainWave Bot", page_icon="🧠", layout="wide")
    st.title("BrainWave Bot")
    st.caption("Natural-language business analytics over a governed SQL layer")

    settings = load_settings()
    bot = get_bot(_knowledge_signature(settings.knowledge_path))
    _render_chat_history()

    with st.form("brainwave_form"):
        question = st.text_area(
            "Ask a question",
            value="How many stories were submitted in EMIA during FY26?",
            height=120,
        )
        submitted = st.form_submit_button("Submit")

    if submitted and question.strip():
        with st.spinner("Resolving business context and running the guarded query..."):
            result = bot.ask(question)
        _append_chat_history(question, result)
        _render_result(result)


if __name__ == "__main__":
    run_app()
