from pathlib import Path

from fastapi.testclient import TestClient
from sqlmodel import SQLModel

from app.db import create_db_and_tables, engine
from app.main import app


def test_health_endpoint_reports_database_ready() -> None:
    create_db_and_tables()

    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "agenthub-api",
        "database": "ready",
    }


def test_sqlmodel_initializes_sqlite_database() -> None:
    create_db_and_tables()

    database_url = str(engine.url)
    assert database_url.startswith("sqlite:///")
    assert SQLModel.metadata.tables
    assert Path(database_url.removeprefix("sqlite:///")).exists()
