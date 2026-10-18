# Alembic migration evidence

Only bounded synthetic/test evidence belongs here. Never add a database, backup,
attachment payload, credentials or real user records. Final summary hashes and
test counts are published in [verification.json](verification.json) after the completed final run.
The source manifest binds 39 runtime/test files to the uncommitted implementation;
prior failures remain recorded separately and are not combined into the final totals.

Implementation scratch and full test logs live in this worktree's ignored
`.superpowers/sdd/2026-10-18-alembic-migrations/`. External test batch paths and
their JUnit files are reported by `scripts/test-api.sh`; pytest trees on successful
runs may be cleaned, but failed runs and separate JUnit evidence are retained.

See [review](../../alembic-migrations-review.md),
[plan](../../superpowers/plans/2026-10-18-alembic-migrations.md),
[design](../../../openspec/changes/agenthub-alembic-migrations/design.md).
