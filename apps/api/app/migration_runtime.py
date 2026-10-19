"""Internal Alembic runner; lease and transaction ownership belong to callers."""
from pathlib import Path
try:
    from alembic import command
    from alembic.config import Config
except ImportError as exc:
    raise RuntimeError('Migration dependencies are unavailable. Install the declared API requirements before running database commands; runtime never installs them.') from exc
from sqlalchemy import Connection
from app.schema_contract import RowEvidence, inspect_schema, assert_rows_preserved
from migrations.integrity_v2 import audit_integrity, plan_integrity_upgrade, IntegrityViolation

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


def begin_schema_upgrade(connection: Connection) -> None:
    """Prepare only an operator-owned connection, then reserve the SQLite writer."""
    if connection.in_transaction():
        raise ValueError('Prepare migration before starting a transaction')
    report = inspect_schema(connection)
    plan = plan_integrity_upgrade(connection)
    connection.rollback()
    if report.state == 'incompatible':
        raise ValueError('Incompatible database schema: ' + '; '.join(report.issues))
    enabled = 0 if plan.rebuild_tables else 1
    connection.exec_driver_sql(f'PRAGMA foreign_keys={"ON" if enabled else "OFF"}')
    if connection.exec_driver_sql('PRAGMA foreign_keys').scalar_one() != enabled:
        raise ValueError('Migration connection foreign key setting did not take effect')
    connection.rollback()
    connection.exec_driver_sql('BEGIN IMMEDIATE')
    if inspect_schema(connection) != report or plan_integrity_upgrade(connection) != plan:
        raise ValueError('Migration schema or rebuild plan changed before write ownership')
    issues = audit_integrity(connection)
    if issues:
        raise IntegrityViolation(issues)


def restore_upgrade_connection(connection: Connection) -> None:
    if connection.closed or connection.invalidated:
        return
    connection.exec_driver_sql('PRAGMA foreign_keys=ON')
    if connection.exec_driver_sql('PRAGMA foreign_keys').scalar_one() != 1:
        raise ValueError('Could not restore migration connection foreign key enforcement')
    connection.rollback()


def run_schema_upgrade(connection: Connection, *, before: RowEvidence) -> None:
    report = inspect_schema(connection)
    if report.state == 'incompatible':
        raise ValueError('Incompatible database schema: ' + '; '.join(report.issues))
    issues = audit_integrity(connection)
    if issues:
        raise IntegrityViolation(issues)
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
    if audit_integrity(connection) or connection.exec_driver_sql('PRAGMA foreign_key_check').first():
        raise ValueError('Foreign key integrity verification failed')
    if connection.exec_driver_sql('PRAGMA integrity_check').scalar() != 'ok':
        raise ValueError('SQLite integrity verification failed')
