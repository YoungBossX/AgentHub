"""Consistent, new-only database snapshots and isolated migration rehearsals."""
import hashlib
import json
import os
import shutil
import sqlite3
import tempfile
import time
from contextlib import closing
from dataclasses import asdict, dataclass
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool
from app.schema_contract import RowEvidence, SchemaReport, capture_rows, assert_rows_preserved

BACKUP_TIMEOUT_SECONDS = 30.0


@dataclass(frozen=True)
class MigrationBackup:
    root: Path
    database: Path
    manifest: Path
    sha256: str
    before: RowEvidence


def _write_new(path: Path, value: dict) -> None:
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.flush()
        os.fsync(stream.fileno())


def sha256(path: Path) -> str:
    result = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def _schema_fingerprint(connection: sqlite3.Connection) -> str:
    rows = connection.execute("SELECT type,name,tbl_name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name").fetchall()
    return hashlib.sha256(json.dumps(rows, ensure_ascii=False, separators=(',', ':')).encode('utf-8')).hexdigest()


def create_backup(source: Path, destination: Path, *, before: RowEvidence, report: SchemaReport) -> MigrationBackup:
    destination.mkdir()  # Exclusive new directory; never reuse or overwrite.
    path = destination / 'database.sqlite3'
    path.touch(exist_ok=False)
    deadline = time.monotonic() + BACKUP_TIMEOUT_SECONDS
    def progress(status, remaining, total):
        if time.monotonic() >= deadline:
            raise TimeoutError('SQLite backup exceeded its bounded deadline')
    # The caller's separate write reservation remains held. Backing up from
    # that same connection can wait on its own transaction indefinitely.
    with closing(sqlite3.connect(source.as_uri() + '?mode=ro', uri=True, timeout=1)) as reader:
        schema_fingerprint = _schema_fingerprint(reader)
        with closing(sqlite3.connect(path, timeout=1)) as output:
            reader.backup(output, pages=256, progress=progress, sleep=.05)
            output.execute('PRAGMA journal_mode=DELETE')
            if output.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise ValueError('SQLite backup integrity verification failed')
            if _schema_fingerprint(output) != schema_fingerprint:
                raise ValueError('SQLite backup schema fingerprint differs from source')
    checksum = sha256(path)
    record = MigrationBackup(destination, path, destination / 'manifest.json', checksum, before)
    identity = source.stat()
    _write_new(record.manifest, {'schema': 'agenthub.db-migration.v1', 'source': str(source),
        'sourceIdentity': [identity.st_dev, identity.st_ino], 'revision': report.revision,
        'backupSha256': checksum, 'schemaFingerprint': schema_fingerprint,
        'rows': asdict(before), 'status': 'backup-verified'})
    write_receipt(record, phase='backup-created')
    write_receipt(record, phase='backup-verified')
    return record


def write_receipt(backup: MigrationBackup, *, phase: str, detail: str | None = None) -> None:
    # Immutable, sequenced records retain incomplete attempts and prior errors.
    allowed = {'backup-created', 'backup-verified', 'rehearsal-passed', 'upgrade-prepared',
        'database-committed', 'verified', 'failed', 'commit-uncertain'}
    if phase not in allowed:
        raise ValueError('Unknown migration receipt phase')
    sequence = len(list(backup.root.glob('[0-9][0-9][0-9][0-9]-*.json'))) + 1
    _write_new(backup.root / f'{sequence:04d}-{phase}.json', {'phase': phase, 'detail': detail})


def rehearse_backup(backup: MigrationBackup) -> None:
    from app import migration_runtime
    if sha256(backup.database) != backup.sha256:
        raise ValueError('Backup hash changed before rehearsal')
    with tempfile.TemporaryDirectory(prefix='agenthub-db-rehearsal-', dir=backup.root) as directory:
        copy = Path(directory) / 'rehearsal.sqlite3'
        shutil.copyfile(backup.database, copy)
        engine = create_engine('sqlite:///' + copy.as_posix(), poolclass=NullPool)
        try:
            with engine.connect() as connection:
                try:
                    migration_runtime.begin_schema_upgrade(connection)
                    assert_rows_preserved(connection, backup.before)
                    migration_runtime.run_schema_upgrade(connection, before=capture_rows(connection))
                    connection.commit()
                except BaseException:
                    connection.rollback()
                    raise
                finally:
                    migration_runtime.restore_upgrade_connection(connection)
        finally:
            engine.dispose()
    if sha256(backup.database) != backup.sha256:
        raise ValueError('Sealed backup changed during rehearsal')
