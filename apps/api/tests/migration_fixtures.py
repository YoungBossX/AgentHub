"""Independent historical input and representative persisted values, not migrations."""
from datetime import datetime
import importlib
import importlib.util

from sqlalchemy import Boolean, DateTime, Integer, LargeBinary, create_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel
import app.models  # Register ORM only; never import app.db.


LEGACY_COLUMNS = {
    'message': ('context_json', 'regeneration_json', 'pinned_at'),
    'session': ('active_frontend_target_id', 'active_backend_target_id', 'memory_snapshot_id', 'pinned_at', 'archived_at'),
    'externalprojecttarget': ('staging_output_dir', 'staging_serve_command', 'deploy_provider_ids_json'),
    'artifactversion': ('parent_version_id', 'content_md', 'content_hash', 'editor_source'),
    'taskrun': ('runner_id', 'last_heartbeat_at', 'lease_expires_at', 'stale_detected_at', 'stale_reason'),
    'agentprofiledraft': ('system_prompt', 'mention_alias', 'tool_policy'),
}


def feature(name):
    assert importlib.util.find_spec(name) is not None, f'Missing planned feature: {name}'
    return importlib.import_module(name)


def memory_engine():
    return create_engine('sqlite://', poolclass=StaticPool, connect_args={'check_same_thread': False})


def current_unversioned(engine):
    SQLModel.metadata.create_all(engine)


def populate_complete(engine):
    """Every ORM table has one row; raw old values and BLOBs can be projected."""
    with engine.begin() as connection:
        for table in SQLModel.metadata.sorted_tables:
            values = {}
            for column in table.columns:
                if column.name == 'id':
                    value = table.name + '-id'
                elif column.foreign_keys:
                    value = next(iter(column.foreign_keys)).column.table.name + '-id'
                elif isinstance(column.type, LargeBinary):
                    value = b'\x00\xff\x01\x80' + table.name.encode()
                elif isinstance(column.type, Boolean):
                    value = False
                elif isinstance(column.type, Integer):
                    value = 1
                elif isinstance(column.type, DateTime):
                    value = datetime(2026, 10, 18, 1, 2, 3, 456789)
                else:
                    value = '{ "original": "原值", "approval": true }' if column.name.endswith('_json') else '旧值-' + column.name
                if column.name == 'state':
                    value = 'released' if table.name == 'targetlock' else 'completed'
                if column.name == 'health_status':
                    value = 'stopped'
                if column.name == 'process_id':
                    value = None
                values[column.name] = value
            connection.execute(table.insert().values(**values))


def legacy_table(engine, table_name):
    """Static old DDL copied from the repository's compatibility evidence."""
    from pathlib import Path
    import json
    statements = json.loads((Path(__file__).parent / 'fixtures/migration_legacy_v1.json').read_text(encoding='utf-8'))
    with engine.begin() as connection:
        for statement in statements[table_name]:
            connection.exec_driver_sql(statement)


def migrate_engine(engine):
    """Unit-level runner on an owned transaction; operator tests use backup CLI."""
    from app.schema_contract import capture_rows
    from app.migration_runtime import run_baseline_upgrade
    with engine.connect() as connection:
        connection.exec_driver_sql('BEGIN IMMEDIATE')
        try:
            run_baseline_upgrade(connection, before=capture_rows(connection))
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
