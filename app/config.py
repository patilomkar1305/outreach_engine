"""
app/config.py
─────────────
Single source of truth for every configuration value.
Reads from environment (and .env via python-dotenv).
"""

from __future__ import annotations
from pydantic import Field
from pydantic_settings import BaseSettings


# ---------------------------------------------------------------------------
# Sub-settings  (grouped for clarity)
# ---------------------------------------------------------------------------

class PostgresSettings(BaseSettings):
    user:     str = "outreach"
    password: str = "changeme"
    db:       str = "outreach_db"
    host:     str = "localhost"
    port:     int = 5432

    @property
    def async_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.user}:{self.password}"
            f"@{self.host}:{self.port}/{self.db}"
        )

    @property
    def sync_url(self) -> str:                  # Alembic needs sync driver
        return (
            f"postgresql+psycopg2://{self.user}:{self.password}"
            f"@{self.host}:{self.port}/{self.db}"
        )

    model_config = {"env_prefix": "POSTGRES_", "env_file": ".env", "extra": "ignore"}


class OllamaSettings(BaseSettings):
    base_url: str = "http://localhost:11434"
    model:    str = "llama3:8b"

    model_config = {"env_prefix": "OLLAMA_", "env_file": ".env", "extra": "ignore"}


class ChromaSettings(BaseSettings):
    host:       str = "localhost"
    port:       int = 8000
    collection: str = "outreach_personas"

    model_config = {"env_prefix": "CHROMADB_", "env_file": ".env", "extra": "ignore"}


class GmailSettings(BaseSettings):
    credentials_path: str = "./credentials.json"
    token_path:       str = "./token.json"

    model_config = {"env_prefix": "GMAIL_", "env_file": ".env", "extra": "ignore"}


class TwilioSettings(BaseSettings):
    account_sid:  str = ""
    auth_token:   str = ""
    from_number:  str = ""

    model_config = {"env_prefix": "TWILIO_", "env_file": ".env", "extra": "ignore"}


# ---------------------------------------------------------------------------
# Root settings  – the only object the rest of the app imports
# ---------------------------------------------------------------------------

class Settings(BaseSettings):
    postgres: PostgresSettings = PostgresSettings()
    ollama:   OllamaSettings   = OllamaSettings()
    chroma:   ChromaSettings   = ChromaSettings()
    gmail:    GmailSettings    = GmailSettings()
    twilio:   TwilioSettings   = TwilioSettings()

    log_level: str = "INFO"

    model_config = {"env_file": ".env", "extra": "ignore"}


# ---------------------------------------------------------------------------
# Module-level singleton  –  `from app.config import settings`
# ---------------------------------------------------------------------------
settings = Settings()
