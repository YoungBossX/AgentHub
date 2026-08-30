#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "$0")/python-env.sh"
cd "$(dirname "$0")/../apps/api"
"$AGENTHUB_PYTHON_BIN" -m uvicorn app.main:app --host 127.0.0.1 --port "${AGENTHUB_API_PORT:-8000}" --reload
