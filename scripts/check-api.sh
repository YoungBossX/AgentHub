#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "$0")/python-env.sh"
cd "$(dirname "$0")/../apps/api"
"$AGENTHUB_PYTHON_BIN" -m compileall app tests
