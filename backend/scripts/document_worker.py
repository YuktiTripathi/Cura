"""Document extraction worker (readiness plan 5.2). Run one or more alongside the API:

    python scripts/document_worker.py

Workers claim jobs atomically, so several can run at once. A job whose worker dies is
reclaimed after DOCUMENT_JOB_LEASE_SECONDS and failed after DOCUMENT_JOB_MAX_ATTEMPTS.
"""

from __future__ import annotations

import logging
import signal
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.core.logging import configure_logging  # noqa: E402
from app.documents.jobs import run_worker_once  # noqa: E402

_running = True


def _stop(*_args) -> None:
    global _running
    _running = False


def main(poll_seconds: float = 2.0) -> None:
    configure_logging()
    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    log = logging.getLogger("cura.documents")
    log.info("document_worker status=started")
    while _running:
        try:
            worked = run_worker_once()
        except Exception:
            log.exception("document_worker status=error")
            worked = False
        if not worked:
            time.sleep(poll_seconds)
    log.info("document_worker status=stopped")


if __name__ == "__main__":
    main()
