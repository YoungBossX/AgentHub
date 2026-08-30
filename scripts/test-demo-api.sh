#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "$0")/python-env.sh"
agenthub_configure_pytest_basetemp demo-api
cd "$(dirname "$0")/../apps/demo-api"
"$AGENTHUB_PYTHON_BIN" -m pytest tests --basetemp="$AGENTHUB_PYTEST_BASETEMP"
