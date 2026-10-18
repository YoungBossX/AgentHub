"""Frozen local baseline. Never import evolving application models here."""
from alembic import op
import sqlalchemy as sa
from migrations.baseline_v1 import HEAD, LEGACY_COLUMNS, frozen_metadata
from app.schema_contract import inspect_schema

revision = HEAD
down_revision = None
branch_labels = depends_on = None


def upgrade():
    connection = op.get_bind()
    report = inspect_schema(connection)
    # Alembic creates its (initially empty) version table before calling upgrade.
    if report.state == 'incompatible':
        issues = [i for i in report.issues if i != 'Unknown, empty or multiple revision records']
        if issues:
            raise ValueError('Incompatible baseline: ' + '; '.join(issues))
        # The coordinator inspected the schema before Alembic created the table.
        changes = op.get_context().config.attributes['baseline_changes']
    else:
        changes = report.changes
    selected = {(c.kind, c.table, c.name) for c in changes}
    metadata = frozen_metadata()
    for table in metadata.sorted_tables:
        if ('create_table', table.name, table.name) in selected:
            columns = [sa.Column(c.name, c.type, *[sa.ForeignKey(f.target_fullname) for f in c.foreign_keys],
                nullable=c.nullable, primary_key=c.primary_key) for c in table.columns]
            op.create_table(table.name, *columns)
            for index in sorted(table.indexes, key=lambda i: i.name):
                op.create_index(index.name, table.name, [c.name for c in index.columns], unique=index.unique)
        else:
            for column in table.columns:
                if ('add_column', table.name, column.name) in selected:
                    default = LEGACY_COLUMNS[table.name][column.name]
                    op.add_column(table.name, sa.Column(column.name, column.type, nullable=column.nullable,
                        server_default=sa.text(default) if default is not None else None))
            for index in sorted(table.indexes, key=lambda i: i.name):
                if ('create_index', table.name, index.name) in selected:
                    op.create_index(index.name, table.name, [c.name for c in index.columns], unique=index.unique)


def downgrade():
    raise ValueError('Automatic destructive downgrade is disabled; use a verified backup.')
