"""Offline local SQLite schema management; importing this module opens no DB."""
import argparse
import json
import socket
import sqlite3
import sys
from contextlib import closing
from dataclasses import asdict, dataclass
from pathlib import Path
from sqlalchemy import Connection, Engine, create_engine, inspect
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.pool import NullPool
from app.maintenance_lease import MaintenanceBusy, database_lease
from app.schema_contract import SchemaReport, capture_rows, inspect_schema
from app.local_data import canonical, regular, git, DataMaintenanceError
from app import migration_backup, migration_runtime


class MigrationError(ValueError):
    def __init__(self, code: str, stage: str, detail: str):
        self.code, self.stage = code, stage
        super().__init__(f'{code} ({stage}): {detail}')


@dataclass(frozen=True)
class UpgradeResult:
    state: str
    revision: str
    backup_dir: Path | None = None


def database_path(database_url: str) -> Path | None:
    url = make_url(database_url)
    if url.drivername not in {'sqlite', 'sqlite+pysqlite'} or url.query:
        raise MigrationError('unsupported-database', 'inspect', 'Only local SQLite file URLs without query options are supported.')
    if not url.database or url.database == ':memory:':
        return None
    try:
        path = canonical(Path(url.database))
        if path.exists():
            regular(path)
    except DataMaintenanceError as exc:
        raise MigrationError('unsafe-path', 'inspect', str(exc)) from exc
    return path


def _readonly_engine(path):
    # A creator prevents #, %, Unicode or spaces from being reparsed as URL data.
    return create_engine('sqlite://', poolclass=NullPool,
        creator=lambda: sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, timeout=1))


def read_status(database_url: str) -> SchemaReport:
    path = database_path(database_url)
    if path is None:
        raise MigrationError('unsupported-database', 'inspect', 'The developer CLI requires a SQLite file, not a transient memory database.')
    if not path.exists():
        return SchemaReport('empty')
    engine = _readonly_engine(path)
    try:
        with engine.connect() as connection:
            return inspect_schema(connection)
    except (SQLAlchemyError, sqlite3.Error) as exc:
        raise MigrationError('database-unavailable', 'inspect', 'SQLite is busy, corrupt or unreadable.') from exc
    finally:
        engine.dispose()


def _backup_destination(path, destination, repo_root, connection):
    if destination is None:
        raise MigrationError('backup-required', 'preflight', 'An existing database requires --backup-dir pointing to a new external directory.')
    if not destination.is_absolute():
        raise MigrationError('backup-path', 'preflight', 'Use an absolute new external backup directory.')
    destination = canonical(destination)
    if destination.exists() or not destination.parent.is_dir():
        raise MigrationError('backup-path', 'preflight', 'The backup directory must be new and its parent must exist.')
    roots = {canonical(repo_root)}
    if (repo_root / '.git').exists():
        for line in git(repo_root, 'worktree', 'list', '--porcelain').decode('utf-8').splitlines():
            if line.startswith('worktree '):
                roots.add(canonical(Path(line[9:])))
    tables = set(inspect(connection).get_table_names())
    for table, column in [('session', 'worktree_path'), ('externalprojecttarget', 'root_path')]:
        if table in tables:
            for value in connection.exec_driver_sql(f'SELECT {column} FROM {table}').scalars():
                if value and Path(value).is_absolute():
                    roots.add(Path(value).resolve())
    if any(destination == root or destination.is_relative_to(root) for root in roots):
        raise MigrationError('backup-path', 'preflight', 'Backup must be external to every repo, managed worktree and registered target.')
    return destination


def _require_offline(connection: Connection, api_port: int):
    from app.local_data import _check_idle
    if not 1 <= api_port <= 65535:
        raise MigrationError('api-port', 'preflight', 'Invalid configured API port.')
    with socket.socket() as probe:
        probe.settimeout(.2)
        if probe.connect_ex(('127.0.0.1', api_port)) == 0:
            raise MigrationError('runtime-active', 'preflight', 'API port is listening; stop the configured API first.')
    # Conservative pre-existing activity guard, never mutate states to pass it.
    _check_idle(connection.connection.driver_connection)
    if connection.exec_driver_sql('PRAGMA foreign_key_check').first():
        raise MigrationError('foreign-key-violation', 'preflight', 'Existing declared foreign keys are violated; no data was repaired.')


def upgrade_database(database_url: str, *, backup_dir: Path | None, repo_root: Path, api_port: int = 8000) -> UpgradeResult:
    path = database_path(database_url)
    if path is None:
        raise MigrationError('unsupported-database', 'inspect', 'Offline migration requires a local SQLite file.')
    report = read_status(database_url)
    if report.state == 'incompatible':
        raise MigrationError('incompatible-schema', 'inspect', '; '.join(report.issues))
    if report.state == 'current':
        return UpgradeResult('current', report.head)
    backup, committed, stage = None, False, 'preflight'
    try:
        with database_lease(path, exclusive=True):
            canonical(path)
            if path.exists(): regular(path)
            engine = create_engine('sqlite://', poolclass=NullPool,
                creator=lambda: sqlite3.connect(path, timeout=1))
            try:
                with engine.connect() as connection:
                    connection.exec_driver_sql('BEGIN IMMEDIATE')
                    try:
                        report = inspect_schema(connection)
                        if report.state == 'incompatible':
                            raise MigrationError('incompatible-schema', stage, '; '.join(report.issues))
                        if report.state == 'current':
                            connection.rollback()
                            return UpgradeResult('current', report.head)
                        identity = path.stat().st_dev, path.stat().st_ino
                        before = capture_rows(connection)
                        if report.state != 'empty':
                            _require_offline(connection, api_port)
                            destination = _backup_destination(path, backup_dir, repo_root, connection)
                            stage = 'backup'
                            backup = migration_backup.create_backup(path, destination, before=before, report=report)
                            stage = 'rehearsal'
                            migration_backup.rehearse_backup(backup)
                            migration_backup.write_receipt(backup, phase='rehearsal-passed')
                        stage = 'upgrade'
                        regular(path)
                        if (path.stat().st_dev, path.stat().st_ino) != identity:
                            raise MigrationError('identity-changed', stage, 'Source file identity changed after backup.')
                        migration_runtime.run_baseline_upgrade(connection, before=before)
                        if backup: migration_backup.write_receipt(backup, phase='upgrade-prepared')
                        connection.commit()
                        committed = True
                        if backup:
                            migration_backup.write_receipt(backup, phase='database-committed')
                            migration_backup.write_receipt(backup, phase='verified')
                        return UpgradeResult('upgraded', report.head, backup.root if backup else None)
                    except BaseException:
                        connection.rollback()
                        raise
            finally:
                engine.dispose()
    except Exception as exc:
        code = 'commit-uncertain' if committed else 'migration-failed'
        if backup:
            try: migration_backup.write_receipt(backup, phase=code if committed else 'failed', detail=stage)
            except OSError: pass  # stderr still reports the true committed/uncertain state.
        if isinstance(exc, MigrationError): raise
        if isinstance(exc, (MaintenanceBusy, DataMaintenanceError, SQLAlchemyError, sqlite3.Error)):
            detail = 'SQLite busy/locked or runtime active; stop writers first.' if isinstance(exc, (SQLAlchemyError, sqlite3.Error, MaintenanceBusy)) else str(exc)
        else:
            detail = 'Operation failed; keep the verified backup and inspect the recorded phase.'
        raise MigrationError(code, stage, detail) from exc


def require_current_schema(db_engine: Engine) -> None:
    with db_engine.connect() as connection:
        report = inspect_schema(connection)
    if report.state != 'current':
        raise MigrationError('schema-upgrade-required', 'startup',
            'Stop the API and use offline pnpm db:migrate --backup-dir <new-external-directory>. '
            + '; '.join(report.issues))


def _initialize_empty(db_engine: Engine) -> None:
    with db_engine.connect() as connection:
        connection.exec_driver_sql('BEGIN IMMEDIATE')
        try:
            report = inspect_schema(connection)
            if report.state not in {'empty', 'current'}:
                raise MigrationError('schema-upgrade-required', 'startup', 'Existing database requires offline db:migrate with a new backup directory.')
            migration_runtime.run_baseline_upgrade(connection, before=capture_rows(connection))
            connection.commit()
        except BaseException:
            connection.rollback()
            raise


def prepare_database(db_engine: Engine) -> None:
    path = database_path(str(db_engine.url))
    if path is None:
        _initialize_empty(db_engine)
        return
    report = read_status(str(db_engine.url))
    if report.state == 'current':
        return
    if report.state != 'empty':
        raise MigrationError('schema-upgrade-required', 'startup',
            'Existing database requires offline pnpm db:migrate --backup-dir <new-external-directory>. ' + '; '.join(report.issues))
    try:
        with database_lease(path, exclusive=True):
            canonical(path)
            if path.exists(): regular(path)
            _initialize_empty(db_engine)
    except MaintenanceBusy:
        # Another initializer may already be serving this newly current DB.
        if read_status(str(db_engine.url)).state != 'current':
            raise MigrationError('runtime-active', 'startup', 'Another initializer owns this database; retry after it finishes.')


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='Offline local SQLite migrations; preserve existing data')
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('status')
    upgrade = sub.add_parser('upgrade')
    upgrade.add_argument('--backup-dir', type=Path)
    upgrade.add_argument('--api-port', type=int, default=8000)
    args = parser.parse_args(argv)
    from app.config import get_settings
    database_url = get_settings().database_url
    try:
        if args.command == 'status':
            report = read_status(database_url)
            print(json.dumps(asdict(report), ensure_ascii=False))
            return 0 if report.state in {'empty', 'current'} else 2 if report.state in {'legacy-compatible', 'upgrade-required'} else 1
        result = upgrade_database(database_url, backup_dir=args.backup_dir,
            repo_root=Path(__file__).resolve().parents[3], api_port=args.api_port)
        print(json.dumps(asdict(result), ensure_ascii=False, default=str))
        return 0
    except (ValueError, OSError, DataMaintenanceError) as exc:
        print(json.dumps({'state': 'refused', 'code': getattr(exc, 'code', 'migration-failed'),
            'stage': getattr(exc, 'stage', 'preflight'), 'detail': str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
