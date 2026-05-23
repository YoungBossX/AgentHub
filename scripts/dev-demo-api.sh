#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../apps/demo-api"
exec ../../.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port "${AGENTHUB_DEMO_API_PORT:-5174}" --reload
