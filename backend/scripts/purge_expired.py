"""Delete documents and conversations past retention. Run daily from cron or a scheduler.

    python scripts/purge_expired.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.retention import purge_expired  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402


def main() -> None:
    db = SessionLocal()
    try:
        print(purge_expired(db))
    finally:
        db.close()


if __name__ == "__main__":
    main()
