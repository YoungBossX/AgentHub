"""Read-only, frozen schema compatibility and exact old-value evidence."""
import hashlib
import json
from dataclasses import dataclass
from typing import Literal
from sqlalchemy import Connection, inspect
from migrations.baseline_v1 import HEAD, SCHEMA, LEGACY_COLUMNS, LEGACY_WITHOUT_FKS


@dataclass(frozen=True)
class SchemaChange:
    kind: Literal['create_table', 'add_column', 'create_index']
    table: str
    name: str


@dataclass(frozen=True)
class SchemaReport:
    state: str
    revision: str | None = None
    head: str = HEAD
    issues: tuple[str, ...] = ()
    changes: tuple[SchemaChange, ...] = ()


@dataclass(frozen=True)
class RowEvidence:
    projection: dict[str, tuple[str, ...]]
    digests: dict[str, tuple[int, str]]


def quote(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _type(value):
    value = str(value).upper()
    return 'TEXT' if any(part in value for part in ('CHAR', 'CLOB', 'TEXT')) else value


def _default(value):
    if value is None:
        return None
    value = str(value).strip()
    while value.startswith('(') and value.endswith(')'):
        value = value[1:-1].strip()
    return value


def inspect_schema(connection: Connection) -> SchemaReport:
    inspector = inspect(connection)
    tables = set(inspector.get_table_names()) - {t for t in inspector.get_table_names() if t.startswith('sqlite_')}
    issues, changes, revision = [], [], None
    objects = connection.exec_driver_sql("SELECT name FROM sqlite_master WHERE type IN ('view','trigger')").all()
    issues.extend('Unexpected view/trigger: ' + row[0] for row in objects)
    if 'alembic_version' in tables:
        columns = inspector.get_columns('alembic_version')
        if [(c['name'], str(c['type']), c['nullable']) for c in columns] != [('version_num', 'VARCHAR(32)', False)]:
            issues.append('Invalid version table structure')
        else:
            versions = connection.exec_driver_sql('SELECT version_num FROM alembic_version').scalars().all()
            if len(versions) != 1 or versions[0] != HEAD:
                issues.append('Unknown, empty or multiple revision records')
            else:
                revision = versions[0]
        if (inspector.get_pk_constraint('alembic_version')['constrained_columns'] != ['version_num']
                or inspector.get_foreign_keys('alembic_version')
                or inspector.get_unique_constraints('alembic_version')
                or inspector.get_check_constraints('alembic_version')
                or inspector.get_indexes('alembic_version')):
            issues.append('Invalid version table primary key or constraints')
    unknown = tables - set(SCHEMA) - {'alembic_version'}
    issues.extend('Unexpected table: ' + name for name in sorted(unknown))
    for name, expected in SCHEMA.items():
        if name not in tables:
            changes.append(SchemaChange('create_table', name, name))
            continue
        columns = {c['name']: c for c in inspector.get_columns(name)}
        target_columns = {c['name']: c for c in expected['columns']}
        # The original session-organization fixture used TEXT PRIMARY KEY
        # without NOT NULL or FK clauses. Accept this exact historical family
        # only with non-null persisted IDs; do not relax canonical FK checks.
        legacy_nullable_pk = (name in {'session', 'message'} and columns.get('id', {}).get('nullable') is True
            and _type(columns['id']['type']) == 'TEXT'
            and connection.exec_driver_sql(f'SELECT 1 FROM {quote(name)} WHERE id IS NULL LIMIT 1').first() is None)
        for extra in columns.keys() - target_columns.keys():
            issues.append(f'Unexpected column: {name}.{extra}')
        for column, target in target_columns.items():
            actual = columns.get(column)
            if actual is None:
                if column in LEGACY_COLUMNS.get(name, {}):
                    changes.append(SchemaChange('add_column', name, column))
                else:
                    issues.append(f'Missing required legacy column: {name}.{column}')
                continue
            nullable_matches = actual['nullable'] == target['nullable'] or (column == 'id' and legacy_nullable_pk)
            if actual.get('computed') or actual.get('identity'):
                issues.append(f'Unexpected generated column: {name}.{column}')
            if (_type(actual['type']) != _type(target['type']) or not nullable_matches):
                issues.append(f'Incompatible column: {name}.{column}')
            allowed_defaults = {None}
            if column in LEGACY_COLUMNS.get(name, {}):
                allowed_defaults.add(LEGACY_COLUMNS[name][column])
            if _default(actual.get('default')) not in allowed_defaults:
                issues.append(f'Unexpected default: {name}.{column}')
        expected_pk = [c['name'] for c in expected['columns'] if c['primary_key']]
        if inspector.get_pk_constraint(name)['constrained_columns'] != expected_pk:
            issues.append(f'Incompatible primary key: {name}')
        expected_fks = {(c['name'], ref) for c in expected['columns'] for ref in c['references'] if c['name'] in columns}
        actual_fks = set()
        for fk in inspector.get_foreign_keys(name):
            if fk.get('options') or len(fk['constrained_columns']) != 1:
                issues.append(f'Incompatible foreign key: {name}')
            actual_fks.update((c, fk['referred_table'] + '.' + r) for c, r in zip(fk['constrained_columns'], fk['referred_columns']))
        # Session.memory_snapshot_id and ArtifactVersion.parent_version_id were
        # historically plain TEXT additions; no table rebuild is necessary.
        allowed_fks = expected_fks - {(c, ref) for c, ref in expected_fks if c in LEGACY_COLUMNS.get(name, {})}
        if actual_fks != expected_fks and actual_fks != allowed_fks and not (not actual_fks and (name in LEGACY_WITHOUT_FKS or legacy_nullable_pk)):
            issues.append(f'Incompatible foreign keys: {name}')
        if inspector.get_check_constraints(name) or inspector.get_unique_constraints(name):
            issues.append(f'Unexpected table constraints: {name}')
        actual_indexes = {i['name']: i for i in inspector.get_indexes(name)}
        index_names = {r[1] for r in connection.exec_driver_sql(f'PRAGMA index_list({quote(name)})') if not r[1].startswith('sqlite_autoindex_')}
        if index_names - actual_indexes.keys():
            issues.append(f'Unexpected unsupported expression index: {name}')
        target_indexes = {i['name']: i for i in expected['indexes']}
        for extra in actual_indexes.keys() - target_indexes.keys():
            issues.append(f'Unexpected index: {name}.{extra}')
        for index_name, index in target_indexes.items():
            actual = actual_indexes.get(index_name)
            if actual is None:
                changes.append(SchemaChange('create_index', name, index_name))
                if index['unique'] and all(c in columns for c in index['columns']):
                    fields = ','.join(quote(c) for c in index['columns'])
                    not_null = ' AND '.join(quote(c) + ' IS NOT NULL' for c in index['columns'])
                    if connection.exec_driver_sql(f'SELECT 1 FROM {quote(name)} WHERE {not_null} GROUP BY {fields} HAVING count(*) > 1 LIMIT 1').first():
                        issues.append(f'Duplicate values prevent unique index: {name}.{index_name}')
            elif (actual['column_names'] != index['columns'] or bool(actual['unique']) != index['unique'] or actual.get('dialect_options')):
                issues.append(f'Incompatible index: {name}.{index_name}')
            else:
                keys = [row for row in connection.exec_driver_sql(f'PRAGMA index_xinfo({quote(index_name)})') if row[5]]
                if ([row[2] for row in keys] != index['columns']
                        or any(row[3] != 0 or row[4] != 'BINARY' for row in keys)):
                    issues.append(f'Incompatible index ordering or collation: {name}.{index_name}')
    if revision == HEAD and changes:
        issues.append('Current revision has schema drift')
    if issues:
        return SchemaReport('incompatible', revision, issues=tuple(issues))
    if revision:
        return SchemaReport('current', revision)
    return SchemaReport('legacy-compatible' if tables else 'empty', changes=tuple(changes))


def _rows_digest(connection, table, columns):
    result, count = hashlib.sha256(), 0
    cursor = connection.exec_driver_sql(f'SELECT {",".join(quote(c) for c in columns)} FROM {quote(table)} ORDER BY id COLLATE BINARY')
    while rows := cursor.fetchmany(256):
        for row in rows:
            values = [(type(value).__name__, value.hex() if isinstance(value, bytes) else value) for value in row]
            data = json.dumps(values, ensure_ascii=False, allow_nan=False, separators=(',', ':')).encode('utf-8')
            result.update(len(data).to_bytes(8, 'big') + data)
            count += 1
    return count, result.hexdigest()


def capture_rows(connection: Connection) -> RowEvidence:
    inspector = inspect(connection)
    projection = {name: tuple(c['name'] for c in inspector.get_columns(name)) for name in sorted(set(inspector.get_table_names()) & set(SCHEMA))}
    return RowEvidence(projection, {t: _rows_digest(connection, t, c) for t, c in projection.items()})


def assert_rows_preserved(connection: Connection, before: RowEvidence) -> None:
    for table, columns in before.projection.items():
        if _rows_digest(connection, table, columns) != before.digests[table]:
            raise ValueError('Data preservation check failed: ' + table)
