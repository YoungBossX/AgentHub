"""Frozen v2 relationship and event preflight; never repairs user records."""
from dataclasses import dataclass

from sqlalchemy import Connection, inspect

from migrations.baseline_v2 import SCHEMA

EVENT_INDEX = 'ux_taskrunevent_run_sequence'


@dataclass(frozen=True)
class IntegrityIssue:
    kind: str
    table: str
    column: str
    count: int


@dataclass(frozen=True)
class IntegrityUpgradePlan:
    rebuild_tables: tuple[str, ...]
    create_event_unique_index: bool


class IntegrityViolation(ValueError):
    def __init__(self, issues: tuple[IntegrityIssue, ...]):
        self.issues = issues
        summary = '; '.join(f'{i.kind} {i.table}.{i.column}: {i.count}' for i in issues)
        super().__init__('Existing integrity violations; no records were repaired: ' + summary)


def _quote(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def audit_integrity(connection: Connection) -> tuple[IntegrityIssue, ...]:
    inspector = inspect(connection)
    tables = set(inspector.get_table_names())
    columns = {t: {c['name'] for c in inspector.get_columns(t)} for t in tables & SCHEMA.keys()}
    issues = []
    for table in sorted(tables & SCHEMA.keys()):
        for column in SCHEMA[table]['columns']:
            name = column['name']
            if name not in columns[table]:
                continue
            if column['primary_key']:
                count = connection.exec_driver_sql(f'SELECT count(*) FROM {_quote(table)} WHERE {_quote(name)} IS NULL').scalar_one()
                if count:
                    issues.append(IntegrityIssue('null-primary-key', table, name, count))
            for reference in column['references']:
                parent, key = reference.split('.')
                condition = f'child.{_quote(name)} IS NOT NULL'
                if key in columns.get(parent, set()):
                    condition += f' AND NOT EXISTS (SELECT 1 FROM {_quote(parent)} AS parent WHERE parent.{_quote(key)}=child.{_quote(name)})'
                count = connection.exec_driver_sql(f'SELECT count(*) FROM {_quote(table)} AS child WHERE {condition}').scalar_one()
                if count:
                    issues.append(IntegrityIssue('orphan-reference', table, name, count))
    if {'task_run_id', 'sequence'} <= columns.get('taskrunevent', set()):
        count = connection.exec_driver_sql("SELECT count(*) FROM taskrunevent WHERE sequence IS NULL OR typeof(sequence) != 'integer' OR sequence < 1").scalar_one()
        if count:
            issues.append(IntegrityIssue('invalid-event-sequence', 'taskrunevent', 'sequence', count))
        count = connection.exec_driver_sql('SELECT count(*) FROM (SELECT task_run_id,sequence FROM taskrunevent GROUP BY task_run_id,sequence HAVING count(*) > 1)').scalar_one()
        if count:
            issues.append(IntegrityIssue('duplicate-event-sequence', 'taskrunevent', 'sequence', count))
    return tuple(issues)


def plan_integrity_upgrade(connection: Connection) -> IntegrityUpgradePlan:
    inspector = inspect(connection)
    tables = set(inspector.get_table_names())
    rebuild = []
    for table in sorted(tables & SCHEMA.keys()):
        expected = {(c['name'], ref) for c in SCHEMA[table]['columns'] for ref in c['references']}
        actual = {(col, fk['referred_table'] + '.' + key)
                  for fk in inspector.get_foreign_keys(table)
                  for col, key in zip(fk['constrained_columns'], fk['referred_columns'])}
        nullable_pk = any(c['primary_key'] and c['nullable'] for c in inspector.get_columns(table))
        if actual != expected or nullable_pk:
            rebuild.append(table)
    indexes = {i['name'] for i in inspector.get_indexes('taskrunevent')} if 'taskrunevent' in tables else set()
    return IntegrityUpgradePlan(tuple(rebuild), EVENT_INDEX not in indexes)


def apply_integrity_upgrade(connection: Connection, plan: IntegrityUpgradePlan) -> None:
    if not connection.in_transaction() or not connection.connection.driver_connection.in_transaction:
        raise ValueError('The integrity coordinator must own an explicit transaction')
    if plan != plan_integrity_upgrade(connection):
        raise ValueError('The integrity migration plan changed')
    issues = audit_integrity(connection)
    if issues:
        raise IntegrityViolation(issues)
    if plan.rebuild_tables and connection.exec_driver_sql('PRAGMA foreign_keys').scalar_one() != 0:
        raise ValueError('Prepare the dedicated rebuild connection before starting its transaction')
    objects = {row[0] for row in connection.exec_driver_sql('SELECT name FROM sqlite_master')}
    for name in plan.rebuild_tables:
        temporary = '_agenthub_v2_' + name
        if temporary in objects:
            raise ValueError('Integrity rebuild temporary name is already occupied')
        table = SCHEMA[name]
        definitions = []
        foreign_keys = []
        for column in table['columns']:
            definition = _quote(column['name']) + ' ' + column['type']
            if not column['nullable']:
                definition += ' NOT NULL'
            if column['primary_key']:
                definition += ' PRIMARY KEY'
            definitions.append(definition)
            for reference in column['references']:
                parent, key = reference.split('.')
                foreign_keys.append(f'FOREIGN KEY ({_quote(column["name"])}) REFERENCES {_quote(parent)} ({_quote(key)})')
        definitions.extend(foreign_keys)
        fields = ','.join(_quote(c['name']) for c in table['columns'])
        connection.exec_driver_sql(f'CREATE TABLE {_quote(temporary)} ({",".join(definitions)})')
        connection.exec_driver_sql(f'INSERT INTO {_quote(temporary)} ({fields}) SELECT {fields} FROM {_quote(name)}')
        connection.exec_driver_sql(f'DROP TABLE {_quote(name)}')
        connection.exec_driver_sql(f'ALTER TABLE {_quote(temporary)} RENAME TO {_quote(name)}')
        for index in table['indexes']:
            _create_index(connection, name, index)
    # Rebuilding taskrunevent already restores this index.
    indexes = {i['name'] for i in inspect(connection).get_indexes('taskrunevent')}
    if EVENT_INDEX not in indexes:
        index = next(i for i in SCHEMA['taskrunevent']['indexes'] if i['name'] == EVENT_INDEX)
        _create_index(connection, 'taskrunevent', index)
    if audit_integrity(connection) or connection.exec_driver_sql('PRAGMA foreign_key_check').first():
        raise ValueError('Integrity verification failed after constraint restoration')


def _create_index(connection: Connection, table: str, index: dict) -> None:
    unique = 'UNIQUE ' if index['unique'] else ''
    fields = ','.join(_quote(c) for c in index['columns'])
    connection.exec_driver_sql(f'CREATE {unique}INDEX {_quote(index["name"])} ON {_quote(table)} ({fields})')
