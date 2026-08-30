#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "$0")/python-env.sh"
agenthub_configure_pytest_basetemp api
cd "$(dirname "$0")/../apps/api"
"$AGENTHUB_PYTHON_BIN" -m pytest --basetemp="$AGENTHUB_PYTEST_BASETEMP"
