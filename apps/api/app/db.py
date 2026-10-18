from sqlmodel import Session as DbSession
from sqlmodel import create_engine

from app.config import get_settings, sqlite_path_from_url
from app.seed import seed_demo_data
from app.db_migrations import prepare_database, require_current_schema

settings = get_settings()
sqlite_path = sqlite_path_from_url(settings.database_url)

engine = create_engine(
    settings.database_url,
    echo=False,
    connect_args={"check_same_thread": False}
    if settings.database_url.startswith("sqlite")
    else {},
)


def create_db_and_tables() -> None:
    prepare_database(engine)


def init_database(seed: bool = True) -> None:
    require_current_schema(engine)
    if seed:
        with DbSession(engine) as session:
            seed_demo_data(session)


def initialize_database_cli() -> None:
    from contextlib import nullcontext
    from app.maintenance_lease import database_lease
    prepare_database(engine)
    with database_lease(sqlite_path, exclusive=False) if sqlite_path else nullcontext():
        init_database(seed=True)


if __name__ == "__main__":
    initialize_database_cli()
    print("Initialized current database and preserved existing seed records.")
