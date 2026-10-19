import asyncio
import json
import os

import pytest
from sqlalchemy import select
from sqlmodel import Session as DbSession, SQLModel

from app.automatic_validation import run_automatic_validation, validation_for_run
from app.config import get_settings
from app.db_migrations import prepare_database
from app.db_engine import create_runtime_engine as create_engine
from app.schema_contract import HEAD
from app.models import Agent, Session, Task, TaskRun, TaskRunEvent, Workspace, utc_now
from app.validation_policy import platform_root
from migration_fixtures import populate_complete
from test_requirement_validation import copy_app


def old_rows(engine):
    with engine.connect() as connection:
        return {table.name: {str(row['id']): dict(row) for row in connection.execute(select(table)).mappings()}
                for table in SQLModel.metadata.sorted_tables}


@pytest.mark.parametrize("backend", ["native", "docker"])
def test_existing_rows_blob_schema_and_legacy_receipt_survive_new_validation(tmp_path, monkeypatch, backend):
    if backend == "docker" and os.environ.get("AGENTHUB_TEST_CONTAINER_VALIDATION") != "1":
        pytest.skip("Real Docker data compatibility requires sandbox:verify")
    monkeypatch.setenv("AGENTHUB_VALIDATION_BACKEND", backend)
    get_settings.cache_clear()
    engine = create_engine('sqlite:///' + (tmp_path / 'existing-current.sqlite3').as_posix())
    try:
        prepare_database(engine)
        populate_complete(engine)
        with engine.begin() as connection:
            assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar() == 1
            connection.execute(TaskRunEvent.__table__.update().values(event_type="validation.completed", payload_json=json.dumps({
                "schemaVersion": "agenthub.validation.v1", "profile": "vite-build-smoke-v1", "status": "passed",
                "taskRunId": "taskrun-id", "adapterRunId": "old-adapter", "sourceFingerprint": "old-source"})))
            schema = connection.exec_driver_sql("SELECT type,name,sql FROM sqlite_master ORDER BY type,name").all()
            head = connection.exec_driver_sql("SELECT version_num FROM alembic_version").scalar()
        before = old_rows(engine)
        target = tmp_path / "new-target"
        copy_app(target)
        with DbSession(engine) as db:
            workspace = Workspace(name="新增验证工作区", root_path="apps/demo", repo_url="local://demo", default_branch="main")
            agent = Agent(name="用户自定义前端", role="frontend", adapter_type="scripted_mock", provider="local")
            db.add_all([workspace, agent]); db.commit()
            session = Session(workspace_id=workspace.id, title="New validation", worktree_path=str(target), bound_branch="main")
            db.add(session); db.commit()
            task = Task(session_id=session.id, title="Validate", intent_type="coding", assigned_agent_id=agent.id,
                        plan_json=json.dumps({"targetId": "demo-frontend"}))
            db.add(task); db.commit()
            run = TaskRun(task_id=task.id, agent_id=agent.id, state="collecting_diff", worktree_path=str(target),
                          started_at=utc_now(), adapter_run_id="new-adapter", runner_id="new-runner")
            run.metrics_json = json.dumps({"taskRunExecutionAccessBinding": {"taskRunId": run.id, "taskId": task.id,
                "sessionId": session.id, "queueEntryId": "new-queue", "accessMode": "write", "runnerId": run.runner_id,
                "executionAttemptId": "new-attempt"}})
            db.add(run); db.commit()
            legacy = validation_for_run(db, "taskrun-id")
            assert legacy["status"] == "passed" and "execution" not in legacy
            asyncio.run(run_automatic_validation(db, run))
            receipt = validation_for_run(db, run.id)
            assert receipt["status"] == "passed", receipt
            assert receipt["execution"]["commandsBackend"] == backend
            assert validation_for_run(db, "taskrun-id") == legacy
        after = old_rows(engine)
        for table, rows in before.items():
            for key, row in rows.items(): assert after[table][key] == row, (table, key)
        with engine.connect() as connection:
            assert connection.exec_driver_sql("SELECT type,name,sql FROM sqlite_master ORDER BY type,name").all() == schema
            assert connection.exec_driver_sql("SELECT version_num FROM alembic_version").scalar() == head == HEAD
            assert connection.exec_driver_sql("PRAGMA integrity_check").scalar() == "ok"
            assert connection.exec_driver_sql("PRAGMA foreign_key_check").all() == []
    finally:
        engine.dispose()
        get_settings.cache_clear()
