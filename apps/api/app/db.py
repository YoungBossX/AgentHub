from sqlmodel import Session as DbSession
from sqlmodel import SQLModel, create_engine

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


def init_database(seed: bool = True) -> None:
    create_db_and_tables()
    if seed:
        with DbSession(engine) as session:
            seed_demo_data(session)


if __name__ == "__main__":
    init_database(seed=True)
    print(f"Initialized and seeded database at {settings.database_url}")
