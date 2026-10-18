"""Schema mutations require the offline coordinator's owned connection."""
from alembic import context
from app.migration_runtime import require_owned_connection

connection = require_owned_connection(context.config)
if context.is_offline_mode():
    raise ValueError('Use the controlled migration coordinator; offline SQL is disabled.')
context.configure(connection=connection, transactional_ddl=True)
with context.begin_transaction():
    context.run_migrations()
