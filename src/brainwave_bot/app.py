from __future__ import annotations

import argparse
import json

from dotenv import load_dotenv
from pydantic import BaseModel

from .orchestrator import BrainwaveOrchestrator


class Question(BaseModel):
    question: str


def create_api():
    from fastapi import FastAPI

    app = FastAPI(title="BrainWave Bot", version="0.1.0")
    bot = BrainwaveOrchestrator()

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "llm_enabled": bot.settings.llm_enabled}

    @app.post("/ask")
    def ask(payload: Question) -> dict:
        return bot.ask(payload.question).model_dump()

    return app


def main() -> None:
    load_dotenv(".env.local")
    load_dotenv()
    parser = argparse.ArgumentParser(description="Ask the BrainWave analytics bot")
    parser.add_argument("question", nargs="*", help="Natural-language business question")
    parser.add_argument("--json", action="store_true", help="Show the complete execution trace")
    args = parser.parse_args()
    question = " ".join(args.question) or input("Ask BrainWave: ")
    result = BrainwaveOrchestrator().ask(question)
    print(json.dumps(result.model_dump(), indent=2, default=str) if args.json else result.answer)


api = create_api()


if __name__ == "__main__":
    main()
