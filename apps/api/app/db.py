from sqlmodel import Session as DbSession
from sqlmodel import SQLModel, create_engine
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from app.config import get_settings, sqlite_path_from_url
from app.seed import seed_demo_data

settings = get_settings()
sqlite_path = sqlite_path_from_url(settings.database_url)
if sqlite_path is not None:
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(
    settings.database_url,
    echo=False,
    connect_args={"check_same_thread": False}
    if settings.database_url.startswith("sqlite")
    else {},
)


def create_db_and_tables() -> None:
    SQLModel.metadata.create_all(engine)
    ensure_demo_schema_columns()


def ensure_demo_schema_columns() -> None:
    _ensure_sqlite_demo_schema_columns(engine)


def _ensure_sqlite_demo_schema_columns(db_engine: Engine) -> None:
    if not str(db_engine.url).startswith("sqlite"):
        return

    inspector = inspect(db_engine)
    table_names = set(inspector.get_table_names())

    _ensure_table_columns(
        db_engine,
        inspector,
        table_names,
        "message",
        {
            "context_json": "TEXT NOT NULL DEFAULT '{}'",
        },
    )
    _ensure_table_columns(
        db_engine,
        inspector,
        table_names,
        "session",
        {
            "active_frontend_target_id": "TEXT",
            "active_backend_target_id": "TEXT",
            "memory_snapshot_id": "TEXT",
        },
    )
    _ensure_table_columns(
        db_engine,
        inspector,
        table_names,
        "externalprojecttarget",
        {
            "staging_output_dir": "TEXT",
            "staging_serve_command": "TEXT",
            "deploy_provider_ids_json": "TEXT NOT NULL DEFAULT '[]'",
        },
    )
    _ensure_table_columns(
        db_engine,
        inspector,
        table_names,
        "artifactversion",
        {
            "parent_version_id": "TEXT",
            "content_md": "TEXT NOT NULL DEFAULT ''",
            "content_hash": "TEXT NOT NULL DEFAULT ''",
            "editor_source": "TEXT NOT NULL DEFAULT 'system'",
        },
    )
    _ensure_table_columns(
        db_engine,
        inspector,
        table_names,
        "taskrun",
        {
            "runner_id": "TEXT",
            "last_heartbeat_at": "DATETIME",
            "lease_expires_at": "DATETIME",
            "stale_detected_at": "DATETIME",
            "stale_reason": "TEXT",
        },
    )


def _ensure_table_columns(
    db_engine: Engine,
    inspector,
    table_names: set[str],
    table_name: str,
    column_definitions: dict[str, str],
) -> None:
    if table_name not in table_names:
        return

    existing_columns = {
        column["name"] for column in inspector.get_columns(table_name)
    }
    missing_columns = [
        (column_name, column_type)
        for column_name, column_type in column_definitions.items()
        if column_name not in existing_columns
    ]
    if not missing_columns:
        return

    with db_engine.begin() as connection:
        for column_name, column_type in missing_columns:
            connection.execute(
                text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")
            )


def init_database(seed: bool = True) -> None:
    create_db_and_tables()
    if seed:
        with DbSession(engine) as session:
            seed_demo_data(session)


if __name__ == "__main__":
    init_database(seed=True)
    print(f"Initialized and seeded database at {settings.database_url}")
