"""Versioned, data-preserving integrity contracts, independent of product DB."""
import hashlib
import json
from pathlib import Path

import pytest
from alembic import command
from sqlalchemy import inspect

from migration_fixtures import feature, legacy_table, memory_engine, populate_complete

V1 = '0001_local_baseline'
V2 = '0002_database_integrity'


def frozen_v1(engine):
    contract = feature('app.schema_contract')
    runtime = feature('app.migration_runtime')
    with engine.connect() as connection:
        connection.exec_driver_sql('BEGIN IMMEDIATE')
        config = runtime.controlled_config(connection)
        config.attributes['baseline_changes'] = contract.inspect_schema(connection).changes
        command.upgrade(config, V1)
        connection.commit()


def test_v1_is_upgrade_required_but_unknown_revision_is_refused():
    engine = memory_engine()
    frozen_v1(engine)
    contract = feature('app.schema_contract')
    assert hasattr(contract, 'inspect_target_schema'), 'Missing version-aware schema inspection'
    with engine.begin() as connection:
        report = contract.inspect_target_schema(connection, target_revision=V2)
        assert (report.state, report.revision, report.head) == ('upgrade-required', V1, V2)
        connection.exec_driver_sql("UPDATE alembic_version SET version_num='unknown'")
        assert contract.inspect_target_schema(connection, target_revision=V2).state == 'incompatible'


def test_frozen_v1_revision_still_executes_unchanged():
    root = Path(__file__).parents[3]
    receipt = Path('E:/Docker/AgentHub/database-integrity-20261019-implementation/frozen-v1.json')
    # Portable source contract; the operator receipt is extra evidence on this host.
    if receipt.is_file():
        for relative, digest in json.loads(receipt.read_text(encoding='utf-8')).items():
            assert hashlib.sha256((root / relative).read_bytes()).hexdigest() == digest
    engine = memory_engine()
    frozen_v1(engine)
    with engine.connect() as connection:
        assert connection.exec_driver_sql('SELECT version_num FROM alembic_version').scalar_one() == V1
        assert 'ux_taskrunevent_run_sequence' not in {i['name'] for i in inspect(connection).get_indexes('taskrunevent')}


def test_legacy_orphans_are_reported_without_creating_parents():
    engine = memory_engine()
    legacy_table(engine, 'externalprojecttarget')
    integrity = feature('migrations.integrity_v2')
    contract = feature('app.schema_contract')
    with engine.connect() as connection:
        before = contract.capture_rows(connection)
        issues = integrity.audit_integrity(connection)
        assert any(i.kind == 'orphan-reference' and i.table == 'externalprojecttarget' and i.column == 'workspace_id' and i.count == 1 for i in issues)
        contract.assert_rows_preserved(connection, before)
        assert 'workspace' not in inspect(connection).get_table_names()


def test_plan_predicts_foreign_keys_missing_after_legacy_additions():
    engine = memory_engine()
    legacy_table(engine, 'session')
    integrity = feature('migrations.integrity_v2')
    with engine.connect() as connection:
        assert integrity.plan_integrity_upgrade(connection).rebuild_tables == ('session',)


def test_complete_v1_does_not_need_table_rebuilds():
    engine = memory_engine()
    frozen_v1(engine)
    integrity = feature('migrations.integrity_v2')
    with engine.connect() as connection:
        assert integrity.audit_integrity(connection) == ()
        plan = integrity.plan_integrity_upgrade(connection)
        assert plan.rebuild_tables == ()
        assert plan.create_event_unique_index is True


@pytest.mark.parametrize('value', [0, -1, 1.5, 'not-an-integer'])
def test_invalid_event_sequences_are_audited(value):
    engine = memory_engine()
    frozen_v1(engine)
    integrity = feature('migrations.integrity_v2')
    with engine.begin() as connection:
        connection.exec_driver_sql('INSERT INTO taskrunevent VALUES (?,?,?,?,?,?)', ('event', 'missing-run', 'state', '{}', value, '2026-01-01 00:00:00.000000'))
        assert any(i.kind == 'invalid-event-sequence' and i.count == 1 for i in integrity.audit_integrity(connection))


def test_duplicate_event_sequences_are_audited_without_renumbering():
    engine = memory_engine()
    frozen_v1(engine)
    integrity = feature('migrations.integrity_v2')
    with engine.begin() as connection:
        for event_id in ('a', 'b'):
            connection.exec_driver_sql('INSERT INTO taskrunevent VALUES (?,?,?,?,?,?)', (event_id, 'missing-run', 'state', '{}', 1, '2026-01-01 00:00:00.000000'))
        assert any(i.kind == 'duplicate-event-sequence' and i.count == 1 for i in integrity.audit_integrity(connection))
        assert connection.exec_driver_sql('SELECT sequence FROM taskrunevent ORDER BY id').scalars().all() == [1, 1]


def test_supported_legacy_constraints_restore_all_values_and_blobs():
    engine = memory_engine()
    frozen_v1(engine)
    populate_complete(engine)
    with engine.begin() as connection:
        original = tuple(connection.exec_driver_sql('SELECT * FROM taskrunevent').one())
        connection.exec_driver_sql('DROP TABLE taskrunevent')
    legacy_table(engine, 'taskrunevent')
    with engine.begin() as connection:
        connection.exec_driver_sql('INSERT INTO taskrunevent VALUES (?,?,?,?,?,?)', original)
    integrity = feature('migrations.integrity_v2')
    assert hasattr(integrity, 'apply_integrity_upgrade'), 'Missing frozen integrity migration'
    contract = feature('app.schema_contract')
    with engine.connect() as connection:
        connection.exec_driver_sql('BEGIN IMMEDIATE')
        before = contract.capture_rows(connection)
        plan = integrity.plan_integrity_upgrade(connection)
        assert plan.rebuild_tables == ('taskrunevent',)
        integrity.apply_integrity_upgrade(connection, plan)
        assert integrity.audit_integrity(connection) == ()
        contract.assert_rows_preserved(connection, before)
        assert inspect(connection).get_foreign_keys('taskrunevent')[0]['referred_table'] == 'taskrun'
        assert any(i['name'] == integrity.EVENT_INDEX and i['unique'] for i in inspect(connection).get_indexes('taskrunevent'))
        connection.commit()


def test_complete_v1_tables_are_not_rebuilt():
    from sqlalchemy import event
    engine = memory_engine()
    frozen_v1(engine)
    integrity = feature('migrations.integrity_v2')
    assert hasattr(integrity, 'apply_integrity_upgrade'), 'Missing frozen integrity migration'
    statements = []
    event.listen(engine, 'before_cursor_execute', lambda c, cursor, sql, *args: statements.append(sql))
    with engine.connect() as connection:
        connection.exec_driver_sql('BEGIN IMMEDIATE')
        integrity.apply_integrity_upgrade(connection, integrity.plan_integrity_upgrade(connection))
        connection.commit()
    assert not any(sql.upper().startswith(('DROP TABLE', 'CREATE TABLE', 'ALTER TABLE')) for sql in statements)


def test_orphan_data_refuses_before_rebuild_without_repair():
    engine = memory_engine()
    legacy_table(engine, 'externalprojecttarget')
    integrity = feature('migrations.integrity_v2')
    assert hasattr(integrity, 'apply_integrity_upgrade'), 'Missing frozen integrity migration'
    with engine.connect() as connection:
        connection.exec_driver_sql('BEGIN IMMEDIATE')
        before = feature('app.schema_contract').capture_rows(connection)
        with pytest.raises(ValueError, match='integrity'):
            integrity.apply_integrity_upgrade(connection, integrity.plan_integrity_upgrade(connection))
        feature('app.schema_contract').assert_rows_preserved(connection, before)
        connection.rollback()


def file_v1(tmp_path, *, missing_event_fk=False):
    from sqlalchemy import create_engine
    path = tmp_path / 'existing.sqlite3'
    engine = create_engine('sqlite:///' + path.as_posix())
    frozen_v1(engine)
    populate_complete(engine)
    if missing_event_fk:
        with engine.begin() as connection:
            original = tuple(connection.exec_driver_sql('SELECT * FROM taskrunevent').one())
            connection.exec_driver_sql('DROP TABLE taskrunevent')
        legacy_table(engine, 'taskrunevent')
        with engine.begin() as connection:
            connection.exec_driver_sql('INSERT INTO taskrunevent VALUES (?,?,?,?,?,?)', original)
            for index in feature('migrations.baseline_v1').frozen_metadata().tables['taskrunevent'].indexes:
                index.create(connection)
    engine.dispose()
    return path


def offline_upgrade(path, backup):
    import socket
    from app.db_migrations import upgrade_database
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        port = probe.getsockname()[1]
    repo = path.parent / 'checkout'
    repo.mkdir(exist_ok=True)
    return upgrade_database('sqlite:///' + path.as_posix(), backup_dir=backup,
                            repo_root=repo, api_port=port)


def test_offline_v1_upgrade_uses_v2_and_preserves_rows(tmp_path):
    from sqlalchemy import create_engine
    path = file_v1(tmp_path)
    engine = create_engine('sqlite:///' + path.as_posix())
    with engine.connect() as connection:
        before = feature('app.schema_contract').capture_rows(connection)
    result = offline_upgrade(path, tmp_path / 'backup')
    assert result.revision == V2
    with engine.connect() as connection:
        feature('app.schema_contract').assert_rows_preserved(connection, before)
        assert feature('app.schema_contract').inspect_schema(connection).state == 'current'
    engine.dispose()


def test_legacy_rebuild_disables_foreign_keys_before_begin_only(tmp_path, monkeypatch):
    from sqlalchemy import Connection, create_engine
    path = file_v1(tmp_path, missing_event_fk=True)
    statements = []
    original = Connection.exec_driver_sql

    def trace(connection, sql, *args, **kwargs):
        statements.append((id(connection), sql, connection.connection.driver_connection.in_transaction))
        return original(connection, sql, *args, **kwargs)

    monkeypatch.setattr(Connection, 'exec_driver_sql', trace)
    result = offline_upgrade(path, tmp_path / 'backup')
    assert result.revision == V2
    off = [(i, row) for i, row in enumerate(statements) if row[1].upper().replace(' ', '') == 'PRAGMAFOREIGN_KEYS=OFF']
    assert off
    for index, (identity, _, in_transaction) in off:
        assert in_transaction is False
        assert any(key == identity and sql == 'BEGIN IMMEDIATE' for key, sql, _ in statements[index + 1:])
    with create_engine('sqlite:///' + path.as_posix()).connect() as connection:
        assert inspect(connection).get_foreign_keys('taskrunevent')


def test_migration_rehearsal_uses_backup_directory_not_system_temp(tmp_path, monkeypatch):
    from app import migration_backup
    path = file_v1(tmp_path)
    directories = []
    original = migration_backup.tempfile.TemporaryDirectory

    def temporary(*args, **kwargs):
        directories.append(kwargs.get('dir'))
        return original(*args, **kwargs)

    monkeypatch.setattr(migration_backup.tempfile, 'TemporaryDirectory', temporary)
    offline_upgrade(path, tmp_path / 'backup')
    assert directories and all(Path(p).is_relative_to(tmp_path / 'backup') for p in directories if p is not None)
    assert None not in directories


def test_changed_rebuild_plan_refuses_before_ddl(tmp_path, monkeypatch):
    from app import migration_runtime
    from app.db_migrations import MigrationError
    from migrations.integrity_v2 import IntegrityUpgradePlan
    path = file_v1(tmp_path)
    original = migration_runtime.plan_integrity_upgrade
    calls = []

    def changed(connection):
        plan = original(connection)
        calls.append(plan)
        return plan if len(calls) == 1 else IntegrityUpgradePlan(('message',), True)

    monkeypatch.setattr(migration_runtime, 'plan_integrity_upgrade', changed)
    with pytest.raises(MigrationError):
        offline_upgrade(path, tmp_path / 'backup')
    assert not (tmp_path / 'backup').exists()
    from sqlalchemy import create_engine
    with create_engine('sqlite:///' + path.as_posix()).connect() as connection:
        assert connection.exec_driver_sql('SELECT version_num FROM alembic_version').scalar_one() == V1


@pytest.mark.parametrize('phase', ['copy', 'replace', 'index', 'verify'])
def test_rebuild_failure_keeps_old_rows_and_revision(tmp_path, monkeypatch, phase):
    from sqlalchemy import Connection, create_engine
    from app.db_migrations import MigrationError
    path = file_v1(tmp_path, missing_event_fk=True)
    contract = feature('app.schema_contract')
    engine = create_engine('sqlite:///' + path.as_posix())
    with engine.connect() as connection:
        before = contract.capture_rows(connection)
    original = Connection.exec_driver_sql
    copied = set()
    injected = []

    def fail(connection, sql, *args, **kwargs):
        relevant = sql.startswith(('INSERT INTO "_agenthub_v2_', 'DROP TABLE ', 'CREATE UNIQUE INDEX ', 'PRAGMA foreign_key_check'))
        source = relevant and Path(original(connection, 'PRAGMA database_list').all()[0][2]).resolve() == path.resolve()
        result = original(connection, sql, *args, **kwargs)
        if source and sql.startswith('INSERT INTO "_agenthub_v2_'):
            copied.add(id(connection))
        marker = {'copy': 'INSERT INTO "_agenthub_v2_', 'replace': 'DROP TABLE ', 'index': 'CREATE UNIQUE INDEX ', 'verify': 'PRAGMA foreign_key_check'}[phase]
        if source and id(connection) in copied and sql.startswith(marker) and not injected:
            injected.append(True)
            raise RuntimeError('injected after ' + phase)
        return result

    monkeypatch.setattr(Connection, 'exec_driver_sql', fail)
    with pytest.raises(MigrationError):
        offline_upgrade(path, tmp_path / 'backup')
    assert injected
    with engine.connect() as connection:
        contract.assert_rows_preserved(connection, before)
        assert connection.exec_driver_sql('SELECT version_num FROM alembic_version').scalar_one() == V1
        assert inspect(connection).get_foreign_keys('taskrunevent') == []
        assert not any(t.startswith('_agenthub_v2_') for t in inspect(connection).get_table_names())
    assert (tmp_path / 'backup/database.sqlite3').is_file()
    assert any((tmp_path / 'backup').glob('*-failed.json'))
    engine.dispose()


def test_commit_acknowledgement_failure_is_uncertain_not_rollback(tmp_path, monkeypatch):
    from sqlalchemy import Connection, create_engine
    from app.db_migrations import MigrationError
    path = file_v1(tmp_path)
    original = Connection.commit
    injected = []

    def commit(connection):
        source = Path(connection.exec_driver_sql('PRAGMA database_list').all()[0][2]).resolve() == path.resolve()
        original(connection)
        if source and not injected:
            injected.append(True)
            raise OSError('commit completed but acknowledgement failed')

    monkeypatch.setattr(Connection, 'commit', commit)
    with pytest.raises(MigrationError) as error:
        offline_upgrade(path, tmp_path / 'backup')
    assert error.value.code == 'commit-uncertain'
    with create_engine('sqlite:///' + path.as_posix()).connect() as connection:
        assert connection.exec_driver_sql('SELECT version_num FROM alembic_version').scalar_one() == V2
    assert any((tmp_path / 'backup').glob('*-commit-uncertain.json'))
