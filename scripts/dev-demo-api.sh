#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "$0")/python-env.sh"
cd "$(dirname "$0")/../apps/demo-api"
exec "$AGENTHUB_PYTHON_BIN" -m uvicorn app.main:app --host 127.0.0.1 --port "${AGENTHUB_DEMO_API_PORT:-5174}" --reload
