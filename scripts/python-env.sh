#!/usr/bin/env bash

# Resolve the project virtual environment on Unix and Windows Git Bash.
AGENTHUB_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENTHUB_REPO_ROOT="$(cd "$AGENTHUB_SCRIPT_DIR/.." && pwd)"
AGENTHUB_PYTHON_OVERRIDE="${AGENTHUB_PYTHON_BIN:-}"
AGENTHUB_COMMON_ROOT=""

if command -v git >/dev/null 2>&1; then
  AGENTHUB_COMMON_GIT_DIR="$(git -C "$AGENTHUB_REPO_ROOT" rev-parse --git-common-dir 2>/dev/null || true)"
  if [[ -n "$AGENTHUB_COMMON_GIT_DIR" ]]; then
    AGENTHUB_COMMON_GIT_DIR="$(cd "$AGENTHUB_REPO_ROOT" && cd "$AGENTHUB_COMMON_GIT_DIR" && pwd)"
    AGENTHUB_COMMON_ROOT="$(cd "$AGENTHUB_COMMON_GIT_DIR/.." && pwd)"
  fi
fi

if [[ -n "$AGENTHUB_PYTHON_OVERRIDE" && -x "$AGENTHUB_PYTHON_OVERRIDE" ]]; then
  AGENTHUB_PYTHON_BIN="$AGENTHUB_PYTHON_OVERRIDE"
elif [[ -x "$AGENTHUB_REPO_ROOT/.venv/bin/python" ]]; then
  AGENTHUB_PYTHON_BIN="$AGENTHUB_REPO_ROOT/.venv/bin/python"
elif [[ -x "$AGENTHUB_REPO_ROOT/.venv/Scripts/python.exe" ]]; then
  AGENTHUB_PYTHON_BIN="$AGENTHUB_REPO_ROOT/.venv/Scripts/python.exe"
elif [[ -n "$AGENTHUB_COMMON_ROOT" && -x "$AGENTHUB_COMMON_ROOT/.venv/bin/python" ]]; then
  AGENTHUB_PYTHON_BIN="$AGENTHUB_COMMON_ROOT/.venv/bin/python"
elif [[ -n "$AGENTHUB_COMMON_ROOT" && -x "$AGENTHUB_COMMON_ROOT/.venv/Scripts/python.exe" ]]; then
  AGENTHUB_PYTHON_BIN="$AGENTHUB_COMMON_ROOT/.venv/Scripts/python.exe"
elif [[ -n "${CONDA_PREFIX:-}" && -x "$CONDA_PREFIX/bin/python" ]]; then
  AGENTHUB_PYTHON_BIN="$CONDA_PREFIX/bin/python"
elif [[ -n "${CONDA_PREFIX:-}" && -x "$CONDA_PREFIX/python.exe" ]]; then
  AGENTHUB_PYTHON_BIN="$CONDA_PREFIX/python.exe"
else
  echo "Missing a usable AgentHub Python environment." >&2
  echo "Create .venv, activate the conda environment, or set AGENTHUB_PYTHON_BIN." >&2
  return 1 2>/dev/null || exit 1
fi

agenthub_configure_pytest_basetemp() {
  local label="$1"

  case "$label" in
    api|demo-api) ;;
    *)
      echo "Unsupported pytest temp label: $label" >&2
      return 1
      ;;
  esac

  AGENTHUB_PYTEST_TEMP_ROOT="$(cd "${AGENTHUB_PYTEST_TEMP_ROOT:-${TMPDIR:-${TEMP:-/tmp}}}" && pwd -P)"
  AGENTHUB_PYTEST_BASETEMP="$(mktemp -d "$AGENTHUB_PYTEST_TEMP_ROOT/agenthub-pytest-$label.XXXXXX")"

  case "$AGENTHUB_PYTEST_BASETEMP" in
    "$AGENTHUB_PYTEST_TEMP_ROOT"/agenthub-pytest-"$label".*) ;;
    *)
      echo "Refusing unexpected pytest temp path: $AGENTHUB_PYTEST_BASETEMP" >&2
      return 1
      ;;
  esac

  agenthub_cleanup_pytest_basetemp() {
    case "$AGENTHUB_PYTEST_BASETEMP" in
      "$AGENTHUB_PYTEST_TEMP_ROOT"/agenthub-pytest-*)
        rm -rf -- "$AGENTHUB_PYTEST_BASETEMP" || true
        ;;
    esac
  }

  trap agenthub_cleanup_pytest_basetemp EXIT
}
