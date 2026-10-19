#!/usr/bin/env bash
set -euo pipefail

# Developer-only utilities: no app.db, installation, or daemon startup.
source "$(dirname "$0")/python-env.sh"
if [[ "${1:-}" == "verify" ]]; then
  shift
  export AGENTHUB_TEST_CONTAINER_VALIDATION=1
  cd "$AGENTHUB_REPO_ROOT"
  exec bash scripts/test-api.sh tests/test_container_validation_real.py tests/test_container_validation_data.py -q -o junit_family=xunit1 "$@"
fi
cd "$AGENTHUB_REPO_ROOT/apps/api"
"$AGENTHUB_PYTHON_BIN" -m app.sandbox_cli "$@"
