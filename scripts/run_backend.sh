#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/backend"
# shellcheck disable=SC1091
source "$ROOT/backend/.venv/bin/activate"
exec uvicorn app.main:app --reload --port 8000 --app-dir "$ROOT/backend"
