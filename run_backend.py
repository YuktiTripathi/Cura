#!/usr/bin/env python3
"""Start Cura API from the repo root or from backend/."""

from pathlib import Path
import os
import sys

BACKEND = Path(__file__).resolve().parent / "backend"
os.chdir(BACKEND)
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(BACKEND.parent))

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=int(os.getenv("PORT", "8000")),
        reload=True,
        reload_dirs=[str(BACKEND), str(BACKEND.parent / "integrations")],
    )
