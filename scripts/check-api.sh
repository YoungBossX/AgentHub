#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../apps/api"
../../.venv/bin/python -m compileall app tests
