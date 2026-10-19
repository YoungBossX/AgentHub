from pathlib import Path
import json
import socket
import sqlite3
import subprocess
import sys
import pytest
from sqlalchemy import create_engine, inspect
from migration_fixtures import feature, current_unversioned, populate_complete

API = Path(__file__).parents[1]
REPO = API.parents[1]


def unused_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


@pytest.fixture
def legacy(tmp_path):
    path = tmp_path / 'legacy.sqlite3'
    engine = create_engine('sqlite:///' + path.as_posix())
    current_unversioned(engine)
    populate_complete(engine)
    engine.dispose()
    return path


def run_upgrade(path, dest, port=None):
    return feature('app.db_migrations').upgrade_database('sqlite:///' + path.as_posix(),
        backup_dir=dest, repo_root=REPO, api_port=port or unused_port())


def test_status_missing_creates_nothing(tmp_path):
    missing = tmp_path / 'not-created' / 'db.sqlite3'
    report = feature('app.db_migrations').read_status('sqlite:///' + missing.as_posix())
    assert report.state == 'empty' and not missing.parent.exists()


def test_existing_legacy_requires_new_external_backup_dir(legacy, tmp_path):
    with pytest.raises(ValueError, match='backup'):
        run_upgrade(legacy, None)
    with pytest.raises(ValueError, match='new|exist'):
        run_upgrade(legacy, tmp_path)
    assert feature('app.db_migrations').read_status('sqlite:///' + legacy.as_posix()).state == 'legacy-compatible'


def test_backup_contains_committed_wal_and_blob_bytes(legacy, tmp_path):
    writer = sqlite3.connect(legacy)
    writer.execute('PRAGMA journal_mode=WAL')
    writer.execute("UPDATE message SET content_md='WAL 原文'")
    writer.commit()
    destination = tmp_path / 'backup'
    try:
        result = run_upgrade(legacy, destination)
        assert result.state == 'upgraded'
        with sqlite3.connect(destination / 'database.sqlite3') as backup:
            assert backup.execute('SELECT content_md FROM message').fetchone()[0] == 'WAL 原文'
            assert backup.execute('SELECT payload FROM messageattachment').fetchone()[0].startswith(b'\x00\xff')
            assert backup.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
        manifest = json.loads((destination / 'manifest.json').read_text())
        assert manifest['schema'] == 'agenthub.db-migration.v1'
        assert len(manifest['schemaFingerprint']) == 64
        assert list(destination.glob('*-verified.json'))
    finally:
        writer.close()


def test_busy_api_or_sqlite_writer_refuses_before_ddl(legacy, tmp_path):
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0)); listener.listen()
        with pytest.raises(ValueError, match='API|listening'):
            run_upgrade(legacy, tmp_path / 'backup', listener.getsockname()[1])
    with sqlite3.connect(legacy) as writer:
        writer.execute('BEGIN IMMEDIATE')
        with pytest.raises(ValueError, match='busy|locked'):
            run_upgrade(legacy, tmp_path / 'backup')
    assert not (tmp_path / 'backup').exists()


def test_rehearsal_failure_keeps_original_unmodified(legacy, tmp_path, monkeypatch):
    backup = feature('app.migration_backup')
    def fail(*args): raise RuntimeError('injected rehearsal failure')
    monkeypatch.setattr(backup, 'rehearse_backup', fail)
    with pytest.raises(ValueError, match='rehearsal'):
        run_upgrade(legacy, tmp_path / 'backup')
    assert feature('app.db_migrations').read_status('sqlite:///' + legacy.as_posix()).state == 'legacy-compatible'
    assert (tmp_path / 'backup' / 'database.sqlite3').exists()


def test_mid_upgrade_failure_keeps_revision_and_backup(legacy, tmp_path, monkeypatch):
    runtime = feature('app.migration_runtime')
    original = runtime.run_schema_upgrade
    count = []
    def fail(connection, **kwargs):
        original(connection, **kwargs)
        count.append(1)
        if len(count) == 2: raise RuntimeError('injected original failure')
    monkeypatch.setattr(runtime, 'run_schema_upgrade', fail)
    with pytest.raises(ValueError, match='upgrade'):
        run_upgrade(legacy, tmp_path / 'backup')
    assert feature('app.db_migrations').read_status('sqlite:///' + legacy.as_posix()).state == 'legacy-compatible'
    monkeypatch.setattr(runtime, 'run_schema_upgrade', original)
    assert run_upgrade(legacy, tmp_path / 'retry').state == 'upgraded'


def test_commit_success_receipt_failure_is_not_reported_as_rollback(legacy, tmp_path, monkeypatch):
    backup = feature('app.migration_backup')
    original = backup.write_receipt
    def fail(record, *, phase, detail=None):
        if phase == 'database-committed': raise OSError('injected disk full')
        return original(record, phase=phase, detail=detail)
    monkeypatch.setattr(backup, 'write_receipt', fail)
    with pytest.raises(ValueError, match='commit-uncertain'):
        run_upgrade(legacy, tmp_path / 'backup')
    assert feature('app.db_migrations').read_status('sqlite:///' + legacy.as_posix()).state == 'current'
    assert run_upgrade(legacy, None).state == 'current'


def test_paths_and_destination_conflicts_refuse(legacy, tmp_path):
    with pytest.raises(ValueError, match='external|repo'):
        run_upgrade(legacy, REPO / 'unsafe-backup')
    linked = tmp_path / 'linked.sqlite3'
    try: linked.hardlink_to(legacy)
    except OSError: pytest.skip('Hard links unavailable')
    with pytest.raises(ValueError, match='regular|link'):
        run_upgrade(linked, tmp_path / 'backup')


def test_cli_status_does_not_import_runtime_database(tmp_path):
    feature('app.db_migrations')
    import os
    env = dict(os.environ, AGENTHUB_DATABASE_URL='sqlite:///' + (tmp_path / 'missing' / 'db.sqlite3').as_posix())
    result = subprocess.run([sys.executable, '-m', 'app.db_migrations', 'status'], cwd=API, env=env, capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)['state'] == 'empty'
    assert not (tmp_path / 'missing').exists()


def test_backup_progress_timeout_is_bounded(legacy, tmp_path, monkeypatch):
    monkeypatch.setattr(feature('app.migration_backup'), 'BACKUP_TIMEOUT_SECONDS', -1)
    with pytest.raises(ValueError, match='backup'):
        run_upgrade(legacy, tmp_path / 'timeout')
    assert feature('app.db_migrations').read_status('sqlite:///' + legacy.as_posix()).state == 'legacy-compatible'
    assert not (tmp_path / 'timeout' / 'manifest.json').exists()


def test_rehearsal_corruption_refuses(legacy, tmp_path, monkeypatch):
    backup = feature('app.migration_backup')
    original = backup.rehearse_backup
    def tamper(record):
        with record.database.open('ab') as stream: stream.write(b'tampered')
        original(record)
    monkeypatch.setattr(backup, 'rehearse_backup', tamper)
    with pytest.raises(ValueError, match='rehearsal'):
        run_upgrade(legacy, tmp_path / 'backup')
    assert feature('app.db_migrations').read_status('sqlite:///' + legacy.as_posix()).state == 'legacy-compatible'


def test_backup_read_is_from_separate_connection(legacy, tmp_path, monkeypatch):
    backup = feature('app.migration_backup')
    original = backup.sqlite3.connect
    readers = []
    def connect(database, *args, **kwargs):
        if str(database).endswith('?mode=ro'): readers.append(str(database))
        return original(database, *args, **kwargs)
    monkeypatch.setattr(backup.sqlite3, 'connect', connect)
    run_upgrade(legacy, tmp_path / 'backup')
    assert readers.count(legacy.as_uri() + '?mode=ro') >= 2


def test_duplicate_unique_values_refuse_without_deleting(legacy, tmp_path):
    with sqlite3.connect(legacy) as connection:
        connection.execute('DROP INDEX ux_workspace_skill_name')
        connection.execute("INSERT INTO workspaceskill SELECT 'duplicate', workspace_id,name,package_json,revision,updated_at FROM workspaceskill")
    with pytest.raises(ValueError, match='Duplicate'):
        run_upgrade(legacy, tmp_path / 'backup')
    with sqlite3.connect(legacy) as connection:
        assert connection.execute('SELECT count(*) FROM workspaceskill').fetchone()[0] == 2
    assert not (tmp_path / 'backup').exists()


def test_source_identity_change_refuses(legacy, tmp_path, monkeypatch):
    import os
    backup = feature('app.migration_backup')
    original_rehearsal, original_stat = backup.rehearse_backup, Path.stat
    altered = []
    def rehearse(record):
        original_rehearsal(record)
        altered.append(True)
    def changed_stat(path, *args, **kwargs):
        result = original_stat(path, *args, **kwargs)
        if altered and path == legacy:
            class ChangedIdentity:
                st_ino = result.st_ino + 1
                def __getattr__(self, name): return getattr(result, name)
            return ChangedIdentity()
        return result
    with monkeypatch.context() as patch:
        patch.setattr(backup, 'rehearse_backup', rehearse)
        patch.setattr(Path, 'stat', changed_stat)
        with pytest.raises(ValueError, match='identity'):
            run_upgrade(legacy, tmp_path / 'backup')
    assert feature('app.db_migrations').read_status('sqlite:///' + legacy.as_posix()).state == 'legacy-compatible'
