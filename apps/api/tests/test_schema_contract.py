import pytest
from sqlalchemy import inspect
from migration_fixtures import feature, memory_engine, current_unversioned, populate_complete, legacy_table, LEGACY_COLUMNS


def test_empty_schema():
    with memory_engine().connect() as connection:
        assert feature('app.schema_contract').inspect_schema(connection).state == 'empty'


def test_unversioned_current_is_legacy():
    engine = memory_engine()
    current_unversioned(engine)
    with engine.connect() as connection:
        report = feature('app.schema_contract').inspect_schema(connection)
        assert report.state == 'legacy-compatible' and report.revision is None
        assert report.changes == ()
    assert set(feature('migrations.baseline_v1').frozen_metadata().tables) == set(inspect(engine).get_table_names())


@pytest.mark.parametrize('table_name', LEGACY_COLUMNS)
def test_six_known_legacy_column_groups(table_name):
    engine = memory_engine()
    legacy_table(engine, table_name)
    with engine.connect() as connection:
        report = feature('app.schema_contract').inspect_schema(connection)
        assert report.state == 'legacy-compatible', report.issues
        assert {change.name for change in report.changes if change.kind == 'add_column'} == set(LEGACY_COLUMNS[table_name])


def test_text_varchar_and_known_defaults_are_compatible():
    engine = memory_engine()
    current_unversioned(engine)
    with engine.begin() as connection:
        connection.exec_driver_sql('ALTER TABLE message RENAME COLUMN context_json TO temporary_context')
        connection.exec_driver_sql('ALTER TABLE message DROP COLUMN temporary_context')
        connection.exec_driver_sql("ALTER TABLE message ADD COLUMN context_json TEXT NOT NULL DEFAULT '{}'")
        assert feature('app.schema_contract').inspect_schema(connection).state == 'legacy-compatible'


@pytest.mark.parametrize('mutation', [
    'CREATE TABLE unknown_table (id TEXT)',
    'ALTER TABLE message ADD COLUMN unknown_column TEXT',
    'CREATE VIEW malicious_view AS SELECT 1',
    'CREATE TRIGGER surprise AFTER INSERT ON message BEGIN SELECT 1; END',
    'CREATE INDEX unexpected_expression ON message (lower(content_md))',
    'CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL PRIMARY KEY); INSERT INTO alembic_version VALUES (\'future\')',
])
def test_unknown_revision_and_schema_drift_refuse(mutation):
    engine = memory_engine()
    current_unversioned(engine)
    with engine.begin() as connection:
        connection.connection.driver_connection.executescript(mutation)
        assert feature('app.schema_contract').inspect_schema(connection).state == 'incompatible'


def test_same_name_wrong_index_refuses():
    engine = memory_engine()
    current_unversioned(engine)
    with engine.begin() as connection:
        connection.exec_driver_sql('DROP INDEX ix_message_session_order')
        connection.exec_driver_sql('CREATE INDEX ix_message_session_order ON message (id)')
        assert feature('app.schema_contract').inspect_schema(connection).state == 'incompatible'


def test_unrecognized_missing_foreign_keys_refuse():
    import json
    from pathlib import Path
    ddl = json.loads((Path(__file__).parent / 'fixtures/migration_legacy_v1.json').read_text())['message'][0]
    ddl = ddl.replace(', \n\tFOREIGN KEY(session_id) REFERENCES session (id)', '')
    ddl = ddl.replace(', \n\tFOREIGN KEY(parent_message_id) REFERENCES message (id)', '')
    engine = memory_engine()
    with engine.begin() as connection:
        connection.exec_driver_sql(ddl)
        assert feature('app.schema_contract').inspect_schema(connection).state == 'incompatible'


def test_all_old_values_and_blobs_are_compared():
    engine = memory_engine()
    current_unversioned(engine)
    populate_complete(engine)
    contract = feature('app.schema_contract')
    with engine.begin() as connection:
        before = contract.capture_rows(connection)
        assert len(before.digests) == 26
        contract.assert_rows_preserved(connection, before)
        connection.exec_driver_sql("UPDATE messageattachment SET payload = x'00ff00'")
        with pytest.raises(ValueError, match='preserv'):
            contract.assert_rows_preserved(connection, before)


@pytest.mark.parametrize('versioned', [False, True])
def test_generated_columns_are_not_legacy_compatible(versioned):
    engine = memory_engine()
    current_unversioned(engine)
    if versioned:
        from migration_fixtures import migrate_engine
        migrate_engine(engine)
    with engine.begin() as connection:
        connection.exec_driver_sql('ALTER TABLE user DROP COLUMN name')
        connection.exec_driver_sql("ALTER TABLE user ADD COLUMN name VARCHAR GENERATED ALWAYS AS ('fixed-name') STORED NOT NULL")
        assert feature('app.schema_contract').inspect_schema(connection).state == 'incompatible'


@pytest.mark.parametrize('suffix', ['COLLATE NOCASE', 'DESC'])
@pytest.mark.parametrize('versioned', [False, True])
def test_index_collation_and_direction_must_match(suffix, versioned):
    engine = memory_engine()
    current_unversioned(engine)
    if versioned:
        from migration_fixtures import migrate_engine
        migrate_engine(engine)
    with engine.begin() as connection:
        connection.exec_driver_sql('DROP INDEX ux_workspace_skill_name')
        connection.exec_driver_sql(f'CREATE UNIQUE INDEX ux_workspace_skill_name ON workspaceskill (workspace_id,name {suffix})')
        assert feature('app.schema_contract').inspect_schema(connection).state == 'incompatible'


@pytest.mark.parametrize('definition', [
    'version_num VARCHAR(32) NOT NULL',
    "version_num VARCHAR(32) NOT NULL PRIMARY KEY CHECK (version_num != '')",
])
def test_version_table_requires_primary_key_and_only_known_constraints(definition):
    engine = memory_engine()
    current_unversioned(engine)
    with engine.begin() as connection:
        connection.exec_driver_sql(f'CREATE TABLE alembic_version ({definition})')
        connection.exec_driver_sql("INSERT INTO alembic_version VALUES ('0001_local_baseline')")
        assert feature('app.schema_contract').inspect_schema(connection).state == 'incompatible'
