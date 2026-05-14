from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AgentHub API"
    database_url: str = "sqlite:///data/agenthub.sqlite3"
    frontend_origin: str = "http://127.0.0.1:3000"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="AGENTHUB_",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


def sqlite_path_from_url(database_url: str) -> Optional[Path]:
    if not database_url.startswith("sqlite:///"):
        return None
    return Path(database_url.removeprefix("sqlite:///"))
