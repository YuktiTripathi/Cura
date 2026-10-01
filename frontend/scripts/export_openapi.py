#!/usr/bin/env python3
"""Write the Cura API's live OpenAPI schema to frontend/openapi/cura.json.

The schema comes from FastAPI (app.openapi()), so it always matches the backend code;
contracts/openapi.yaml is hand-maintained and can lag behind. Run from anywhere with the
backend's virtualenv active:

    python frontend/scripts/export_openapi.py
"""

import json
import logging
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
OUT = ROOT / "frontend" / "openapi" / "cura.json"

sys.path[:0] = [str(BACKEND), str(ROOT)]
os.chdir(BACKEND)
# Importing the app must not need real credentials or services.
os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault("AUTH_PROVIDER", "mock")
os.environ.setdefault("HEALTH_PROVIDER", "mock")
os.environ.setdefault("ENABLE_LLM", "false")
logging.disable(logging.CRITICAL)

from app.main import app  # noqa: E402

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n")
print(f"wrote {OUT.relative_to(ROOT)}")
