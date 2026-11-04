from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    telegram_bot_token: SecretStr = SecretStr("")
    openai_api_key: SecretStr = SecretStr("")
    openai_model: str = "gpt-6.1-sol"
    openai_reasoning_effort: str = "medium"
    database_path: Path = Path("data/registry.duckdb")
    state_path: Path = Path("var/state.sqlite3")
    answer_timeout_seconds: float = Field(default=75, ge=5, le=80)
    max_concurrent_questions: int = Field(default=4, ge=1, le=16)


def require_credentials(settings: Settings) -> None:
    missing = [
        name
        for name in ("telegram_bot_token", "openai_api_key")
        if not getattr(settings, name).get_secret_value()
    ]
    if missing:
        raise ValueError("Missing settings: " + ", ".join(missing))
