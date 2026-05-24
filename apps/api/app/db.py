from sqlmodel import Session as DbSession
from sqlmodel import SQLModel, create_engine
from sqlalchemy import inspect, text

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
    if not settings.database_url.startswith("sqlite"):
        return

    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    if "session" not in table_names:
        return

    existing_columns = {column["name"] for column in inspector.get_columns("session")}
    missing_columns = [
        column_name
        for column_name in ("active_frontend_target_id", "active_backend_target_id")
        if column_name not in existing_columns
    ]
    if missing_columns:
        with engine.begin() as connection:
            for column_name in missing_columns:
                connection.execute(
                    text(f"ALTER TABLE session ADD COLUMN {column_name} TEXT")
                )

    if "taskrun" not in table_names:
        return

    task_run_columns = {column["name"] for column in inspector.get_columns("taskrun")}
    task_run_column_definitions = {
        "runner_id": "TEXT",
        "last_heartbeat_at": "DATETIME",
        "lease_expires_at": "DATETIME",
        "stale_detected_at": "DATETIME",
        "stale_reason": "TEXT",
    }
    missing_task_run_columns = [
        (column_name, column_type)
        for column_name, column_type in task_run_column_definitions.items()
        if column_name not in task_run_columns
    ]
    if not missing_task_run_columns:
        return

    with engine.begin() as connection:
        for column_name, column_type in missing_task_run_columns:
            connection.execute(
                text(f"ALTER TABLE taskrun ADD COLUMN {column_name} {column_type}")
            )


def init_database(seed: bool = True) -> None:
    create_db_and_tables()
    if seed:
        with DbSession(engine) as session:
            seed_demo_data(session)


if __name__ == "__main__":
    init_database(seed=True)
    print(f"Initialized and seeded database at {settings.database_url}")
