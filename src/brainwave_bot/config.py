from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    root: Path = ROOT
    database_path: Path = ROOT / "brainwave.db"
    business_context_path: Path = ROOT / "data" / "business_context.yaml"
    knowledge_path: Path = ROOT / "knowledge"
    fiscal_start_month: int = 4
    allowed_markets: tuple[str, ...] = ("EMEA", "AMERICAS", "APAC")
    openrouter_api_key: str | None = None
    openrouter_model: str = "openai/gpt-4.1-mini"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"

    @property
    def llm_enabled(self) -> bool:
        return bool(self.openrouter_api_key)


def load_settings() -> Settings:
    db_value = os.getenv("BRAINWAVE_DB_PATH", "brainwave.db")
    db_path = Path(db_value)
    if not db_path.is_absolute():
        db_path = ROOT / db_path
    markets = tuple(
        item.strip().upper()
        for item in os.getenv("BRAINWAVE_ALLOWED_MARKETS", "EMEA,AMERICAS,APAC").split(",")
        if item.strip()
    )
    return Settings(
        database_path=db_path,
        fiscal_start_month=int(os.getenv("BRAINWAVE_FISCAL_START_MONTH", "4")),
        allowed_markets=markets,
        openrouter_api_key=os.getenv("OPENROUTER_API_KEY") or None,
        openrouter_model=os.getenv("OPENROUTER_MODEL", "openai/gpt-4.1-mini"),
        openrouter_base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
    )


def load_business_context(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)

