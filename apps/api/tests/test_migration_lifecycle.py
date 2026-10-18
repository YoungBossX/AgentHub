from pathlib import Path
import os
import subprocess
import sys
import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.pool import NullPool
from migration_fixtures import feature, memory_engine, current_unversioned
from app.maintenance_lease import database_lease

API = Path(__file__).parents[1]


def test_empty_startup_initializes_then_rechecks_under_shared_lease(tmp_path):
    engine = create_engine('sqlite:///' + (tmp_path / 'runtime.sqlite3').as_posix(), poolclass=NullPool)
    migrations = feature('app.db_migrations')
    assert hasattr(migrations, 'prepare_database'), 'Missing planned prepare_database'
    migrations.prepare_database(engine)
    with database_lease(tmp_path / 'runtime.sqlite3', exclusive=False):
        migrations.require_current_schema(engine)
        migrations.prepare_database(engine)  # Current fast path needs no exclusive lease.
    assert len(inspect(engine).get_table_names()) == 27


def test_legacy_startup_fails_before_seed_recovery_and_workers(tmp_path, monkeypatch):
    from app import main
    from fastapi.testclient import TestClient
    engine = create_engine('sqlite:///' + (tmp_path / 'legacy.sqlite3').as_posix())
    current_unversioned(engine)
    monkeypatch.setattr(main, 'engine', engine)
    def forbidden(*args, **kwargs): raise AssertionError('Must fail before side effects')
    monkeypatch.setattr(main, 'init_database', forbidden)
    monkeypatch.setattr(main, 'recover_interrupted_requests', forbidden)
    monkeypatch.setattr(main, 'get_preview_service', forbidden)
    with pytest.raises(ValueError, match='offline|migrate'):
        with TestClient(main.app): pass
    assert 'alembic_version' not in inspect(engine).get_table_names()
    engine.dispose()


def test_memory_engine_uses_fixed_revision():
    migrations = feature('app.db_migrations')
    assert hasattr(migrations, 'prepare_database'), 'Missing planned prepare_database'
    engine = memory_engine()
    migrations.prepare_database(engine)
    migrations.require_current_schema(engine)


def test_api_shared_lease_blocks_offline_upgrade(tmp_path):
    path = tmp_path / 'legacy.sqlite3'
    engine = create_engine('sqlite:///' + path.as_posix())
    current_unversioned(engine); engine.dispose()
    script = "from app.db_migrations import upgrade_database; from pathlib import Path; import sys; upgrade_database(sys.argv[1], backup_dir=Path(sys.argv[2]), repo_root=Path(sys.argv[3]))"
    with database_lease(path, exclusive=False):
        result = subprocess.run([sys.executable, '-c', script, 'sqlite:///' + path.as_posix(), str(tmp_path / 'backup'), str(API.parents[1])], cwd=API, capture_output=True, text=True, timeout=15)
    assert result.returncode != 0
    assert 'busy' in result.stderr or 'owns' in result.stderr
    assert not (tmp_path / 'backup').exists()


def test_two_initializers_never_mutate_concurrently(tmp_path):
    feature('app.db_migrations')
    script = 'from sqlalchemy import create_engine; from app.db_migrations import prepare_database; import sys; prepare_database(create_engine(sys.argv[1]))'
    path = tmp_path / 'first-run.sqlite3'
    args = [sys.executable, '-c', script, 'sqlite:///' + path.as_posix()]
    workers = [subprocess.Popen(args, cwd=API, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for _ in range(2)]
    results = [(worker, worker.communicate(timeout=20)) for worker in workers]
    assert any(worker.returncode == 0 for worker, _ in results), results
    assert feature('app.db_migrations').read_status('sqlite:///' + path.as_posix()).state == 'current'


def test_path_with_spaces_and_unicode_uses_same_database_identity(tmp_path):
    path = tmp_path / '数据库 # % space.sqlite3'
    migrations = feature('app.db_migrations')
    assert hasattr(migrations, 'prepare_database'), 'Missing planned prepare_database'
    migrations.prepare_database(create_engine('sqlite:///' + path.as_posix(), poolclass=NullPool))
    assert migrations.read_status('sqlite:///' + path.as_posix()).state == 'current'


def test_current_schema_drift_blocks_recovery(tmp_path):
    migrations = feature('app.db_migrations')
    assert hasattr(migrations, 'prepare_database'), 'Missing planned prepare_database'
    engine = create_engine('sqlite:///' + (tmp_path / 'drift.sqlite3').as_posix())
    migrations.prepare_database(engine)
    with engine.begin() as connection: connection.exec_driver_sql('DROP INDEX ix_message_session_order')
    with pytest.raises(ValueError, match='schema|drift'):
        migrations.require_current_schema(engine)
    engine.dispose()


def test_current_startup_preserves_customized_seed_records(tmp_path, monkeypatch):
    import asyncio
    from types import SimpleNamespace
    from fastapi.testclient import TestClient
    from sqlmodel import Session
    from app import main, db as database_module
    from app.seed import seed_demo_data
    migrations = feature('app.db_migrations')
    engine = create_engine('sqlite:///' + (tmp_path / 'current.sqlite3').as_posix(), poolclass=NullPool)
    migrations.prepare_database(engine)
    with Session(engine) as db: seed_demo_data(db)
    with engine.begin() as connection:
        connection.exec_driver_sql("UPDATE agent SET name='我的前端',enabled=0,system_prompt='原提示' WHERE role='frontend'")
        connection.exec_driver_sql("UPDATE workspace SET root_path='my-project',default_branch='custom'")
        before = feature('app.schema_contract').capture_rows(connection)
    monkeypatch.setattr(main, 'engine', engine)
    monkeypatch.setattr(database_module, 'engine', engine)
    monkeypatch.setattr(main, 'get_preview_service', lambda: SimpleNamespace(startup=lambda: None, shutdown=lambda: None))
    async def idle(): await asyncio.Event().wait()
    monkeypatch.setattr('app.group_execution.group_execution_loop', idle)
    with TestClient(main.app): pass
    with engine.connect() as connection: feature('app.schema_contract').assert_rows_preserved(connection, before)


def test_lifespan_failure_releases_lease_and_restores_windows_handler(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from app import main
    path = tmp_path / 'failed-start.sqlite3'
    engine = create_engine('sqlite:///' + path.as_posix(), poolclass=NullPool)
    feature('app.db_migrations').prepare_database(engine)
    restored = []
    monkeypatch.setattr(main, 'engine', engine)
    monkeypatch.setattr(main, 'install_windows_connection_cleanup', lambda loop: lambda: restored.append(True))
    def fail(**kwargs): raise RuntimeError('injected initialization error')
    monkeypatch.setattr(main, 'init_database', fail)
    with pytest.raises(RuntimeError, match='injected'):
        with TestClient(main.app): pass
    assert restored == [True]
    with database_lease(path, exclusive=True): pass
