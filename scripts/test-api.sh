#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "$0")/python-env.sh"
agenthub_configure_pytest_basetemp api
AGENTHUB_API_TEST_RUN_ROOT="$AGENTHUB_PYTEST_BASETEMP"
AGENTHUB_PYTEST_BASETEMP="$AGENTHUB_API_TEST_RUN_ROOT/pytest"
AGENTHUB_API_TEST_DATABASE="$AGENTHUB_API_TEST_RUN_ROOT/runtime.sqlite3"
if command -v cygpath >/dev/null 2>&1; then
  AGENTHUB_API_TEST_DATABASE="$(cygpath -m "$AGENTHUB_API_TEST_DATABASE")"
fi
# Never inherit a product URL, even from an otherwise valid developer shell.
export AGENTHUB_DATABASE_URL="sqlite:///$AGENTHUB_API_TEST_DATABASE"
trap 'AGENTHUB_API_TEST_EXIT=$?; trap - EXIT; echo "API test evidence retained: $AGENTHUB_API_TEST_RUN_ROOT" >&2; exit "$AGENTHUB_API_TEST_EXIT"' ERR
cd "$(dirname "$0")/../apps/api"
"$AGENTHUB_PYTHON_BIN" -m app.db
"$AGENTHUB_PYTHON_BIN" -m pytest --basetemp="$AGENTHUB_PYTEST_BASETEMP" --junitxml="$AGENTHUB_API_TEST_RUN_ROOT/results.xml" "$@"
echo "API test database and JUnit evidence: $AGENTHUB_API_TEST_RUN_ROOT"
