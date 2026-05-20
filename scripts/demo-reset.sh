#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
API_DIR="$ROOT_DIR/apps/api"
DATA_DIR="$API_DIR/data"
DB_PATH="$DATA_DIR/agenthub.sqlite3"
BACKUP_ROOT="$DATA_DIR/backups"
STAMP="$(date +"%Y%m%d-%H%M%S")"
BACKUP_DIR="$BACKUP_ROOT/demo-reset-$STAMP"
PYTHON_BIN="$ROOT_DIR/.venv/bin/python"

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "Missing backend Python environment at $PYTHON_BIN"
  echo "Create it first:"
  echo "  python3 -m venv .venv"
  echo "  .venv/bin/python -m pip install -r apps/api/requirements.txt"
  exit 1
fi

if [[ -e "$DB_PATH" ]] && command -v lsof >/dev/null 2>&1; then
  if lsof "$DB_PATH" >/dev/null 2>&1; then
    echo "Refusing to reset while SQLite is open:"
    lsof "$DB_PATH" || true
    echo
    echo "Stop the API/dev server first, then rerun:"
    echo "  pnpm demo:reset"
    exit 1
  fi
fi

mkdir -p "$DATA_DIR" "$BACKUP_DIR"

BACKED_UP=0
for suffix in "" "-wal" "-shm"; do
  source="$DB_PATH$suffix"
  if [[ -e "$source" ]]; then
    cp -p "$source" "$BACKUP_DIR/$(basename "$source")"
    rm -f "$source"
    BACKED_UP=1
  fi
done

if [[ "$BACKED_UP" -eq 0 ]]; then
  echo "No existing SQLite database found at $DB_PATH"
  echo "Created empty backup directory: $BACKUP_DIR"
else
  echo "Backed up SQLite database files to:"
  echo "  $BACKUP_DIR"
fi

(
  cd "$API_DIR"
  "$PYTHON_BIN" -m app.db
)

cat <<EOF

Demo database reset complete.

New SQLite database:
  $DB_PATH

Existing git worktrees were not deleted:
  $ROOT_DIR/.worktrees

Running preview or dev-server processes were not stopped. Stop stale preview
processes manually if they are still listening on old ports.

Restore the previous database by stopping the API and running:
  cp "$BACKUP_DIR/agenthub.sqlite3" "$DB_PATH"

If the backup contains WAL/SHM files, restore those too:
  cp "$BACKUP_DIR/agenthub.sqlite3-wal" "$DB_PATH-wal" 2>/dev/null || true
  cp "$BACKUP_DIR/agenthub.sqlite3-shm" "$DB_PATH-shm" 2>/dev/null || true

After reset, start the app with:
  pnpm dev:api
  pnpm dev:web

Then create a fresh session in the UI and send:
  @orchestrator build a login page for the demo app
EOF
