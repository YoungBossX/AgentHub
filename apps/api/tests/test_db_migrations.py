from pathlib import Path
import pytest
from sqlalchemy import inspect
from migration_fixtures import feature, memory_engine, current_unversioned, populate_complete, legacy_table, LEGACY_COLUMNS


def apply(engine):
    contract = feature('app.schema_contract')
    with engine.connect() as connection:
        connection.exec_driver_sql('BEGIN IMMEDIATE')
        try:
            feature('app.migration_runtime').run_baseline_upgrade(connection, before=contract.capture_rows(connection))
            connection.commit()
        except BaseException:
            connection.rollback()
            raise


def test_fixed_revision_initializes_empty():
    engine = memory_engine()
    apply(engine)
    with engine.connect() as connection:
        assert feature('app.schema_contract').inspect_schema(connection).state == 'current'
        assert connection.exec_driver_sql('SELECT version_num FROM alembic_version').scalar_one() == '0001_local_baseline'
    assert len(inspect(engine).get_table_names()) == 27


def test_frozen_history_ignores_runtime_model_changes(monkeypatch):
    from sqlmodel import SQLModel
    def forbidden(*args, **kwargs):
        raise AssertionError('Historical revision must not use runtime create_all')
    monkeypatch.setattr(SQLModel.metadata, 'create_all', forbidden)
    apply(memory_engine())


@pytest.mark.parametrize('table_name', (*LEGACY_COLUMNS, 'taskrunevent'))
def test_supported_legacy_additions_preserve_values(table_name):
    engine = memory_engine()
    legacy_table(engine, table_name)
    contract = feature('app.schema_contract')
    with engine.connect() as connection:
        before = contract.capture_rows(connection)
    apply(engine)
    with engine.connect() as connection:
        contract.assert_rows_preserved(connection, before)
        assert contract.inspect_schema(connection).state == 'current'
        if table_name == 'externalprojecttarget':
            assert tuple(connection.exec_driver_sql('SELECT staging_output_dir,staging_serve_command,deploy_provider_ids_json FROM externalprojecttarget').one()) == (None, None, '[]')
        if table_name == 'artifactversion':
            assert tuple(connection.exec_driver_sql('SELECT parent_version_id,content_md,content_hash,editor_source FROM artifactversion').one()) == (None, '', '', 'system')
        if table_name == 'taskrunevent':
            assert 'ix_taskrunevent_created_at' in {i['name'] for i in inspect(connection).get_indexes('taskrunevent')}


def test_current_repeated_upgrade_is_noop():
    engine = memory_engine()
    current_unversioned(engine)
    populate_complete(engine)
    apply(engine)
    with engine.connect() as connection:
        before = feature('app.schema_contract').capture_rows(connection)
    apply(engine)
    with engine.connect() as connection:
        feature('app.schema_contract').assert_rows_preserved(connection, before)


@pytest.mark.parametrize('command_name', ['upgrade', 'stamp', 'downgrade'])
def test_raw_alembic_invocation_is_refused(command_name):
    from alembic import command
    from alembic.config import Config
    cfg = Config(str(Path(__file__).parents[1] / 'alembic.ini'))
    with pytest.raises((ValueError, RuntimeError), match='coordinator|controlled'):
        getattr(command, command_name)(cfg, 'head' if command_name != 'downgrade' else 'base')


def test_baseline_downgrade_does_not_drop_tables():
    from alembic import command
    engine = memory_engine()
    apply(engine)
    runtime = feature('app.migration_runtime')
    with engine.begin() as connection:
        with pytest.raises(ValueError, match='downgrade'):
            command.downgrade(runtime.controlled_config(connection), 'base')
        assert len(inspect(connection).get_table_names()) == 27


def test_failed_ddl_rolls_back_revision_and_can_retry(monkeypatch):
    from alembic.operations import Operations
    engine = memory_engine()
    legacy_table(engine, 'message')
    original = Operations.add_column
    calls = []
    def fail_after_ddl(self, *args, **kwargs):
        original(self, *args, **kwargs)
        calls.append(1)
        raise RuntimeError('injected after real DDL')
    with monkeypatch.context() as patch:
        patch.setattr(Operations, 'add_column', fail_after_ddl)
        with pytest.raises(RuntimeError, match='injected'):
            apply(engine)
    assert calls
    assert 'alembic_version' not in inspect(engine).get_table_names()
    apply(engine)


def test_missing_dependency_has_actionable_error():
    import subprocess
    import sys
    result = subprocess.run([sys.executable, '-c', "import sys; sys.modules['alembic']=None; import app.migration_runtime"],
        cwd=Path(__file__).parents[1], capture_output=True, text=True, timeout=15)
    assert result.returncode != 0
    assert 'Install the declared API requirements' in result.stderr
