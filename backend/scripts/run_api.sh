#!/usr/bin/env bash
# Always use the project venv. System uvicorn may lack psycopg and fail IHR reads.
set -euo pipefail
cd "$(dirname "$0")/.."
exec .venv/bin/uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
