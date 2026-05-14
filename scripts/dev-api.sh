#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../apps/api"
../../.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port "${AGENTHUB_API_PORT:-8000}" --reload
