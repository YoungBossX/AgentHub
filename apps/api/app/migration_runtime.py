"""Internal Alembic runner; lease and transaction ownership belong to callers."""
from pathlib import Path
try:
    from alembic import command
    from alembic.config import Config
except ImportError as exc:
    raise RuntimeError('Migration dependencies are unavailable. Install the declared API requirements before running database commands; runtime never installs them.') from exc
from sqlalchemy import Connection
from app.schema_contract import RowEvidence, inspect_schema, assert_rows_preserved

_PERMIT = object()


def controlled_config(connection: Connection) -> Config:
    if not connection.in_transaction():
        raise ValueError('The controlled coordinator must own an active transaction.')
    config = Config(str(Path(__file__).resolve().parents[1] / 'alembic.ini'))
    config.attributes.update(connection=connection, migration_permit=_PERMIT)
    return config


def require_owned_connection(config: Config) -> Connection:
    connection = config.attributes.get('connection')
    if config.attributes.get('migration_permit') is not _PERMIT or not isinstance(connection, Connection) or not connection.in_transaction():
        raise ValueError('Use the controlled migration coordinator, not the bare Alembic CLI.')
    return connection


def run_baseline_upgrade(connection: Connection, *, before: RowEvidence) -> None:
    report = inspect_schema(connection)
    if report.state == 'incompatible':
        raise ValueError('Incompatible database schema: ' + '; '.join(report.issues))
    if report.state == 'current':
        assert_rows_preserved(connection, before)
        return
    config = controlled_config(connection)
    config.attributes['baseline_changes'] = report.changes
    command.upgrade(config, 'head')
    final = inspect_schema(connection)
    if final.state != 'current':
        raise ValueError('Schema verification failed: ' + '; '.join(final.issues))
    assert_rows_preserved(connection, before)
    if connection.exec_driver_sql('PRAGMA integrity_check').scalar() != 'ok':
        raise ValueError('SQLite integrity verification failed')
