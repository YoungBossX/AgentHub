"""Restore recognized historical constraints without rewriting records."""
from alembic import op

from app.migration_runtime import require_owned_connection
from migrations.integrity_v2 import apply_integrity_upgrade, plan_integrity_upgrade

revision = '0002_database_integrity'
down_revision = '0001_local_baseline'
branch_labels = depends_on = None


def upgrade():
    connection = require_owned_connection(op.get_context().config)
    apply_integrity_upgrade(connection, plan_integrity_upgrade(connection))


def downgrade():
    raise ValueError('Automatic destructive downgrade is disabled; use a verified backup.')
