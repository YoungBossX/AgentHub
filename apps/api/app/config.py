from functools import lru_cache
from pathlib import Path
from typing import Literal, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url


class Settings(BaseSettings):
    app_name: str = "AgentHub API"
    database_url: str = "sqlite:///data/agenthub.sqlite3"
    frontend_origin: str = "http://127.0.0.1:3000"
    llm_planner_enabled: bool = False
    llm_planner_provider: str = "disabled"
    llm_planner_timeout_sec: int = 60
    validation_backend: Literal["native", "docker"] = "native"
    validation_frontend_image_id: str | None = None
    validation_backend_image_id: str | None = None
    validation_docker_context: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="AGENTHUB_",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


def sqlite_path_from_url(database_url: str) -> Optional[Path]:
    url = make_url(database_url)
    if url.drivername not in {"sqlite", "sqlite+pysqlite"} or not url.database or url.database == ":memory:":
        return None
    return Path(url.database)
