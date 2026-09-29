import logging
import re
import sys

from app.core.config import settings

_SECRET = re.compile(r"(api[_-]?key|password|secret|authorization|sk-[A-Za-z0-9]+)", re.I)
_PROMPT = re.compile(r"(PERSONAL HEALTH CONTEXT JSON|UNTRUSTED USER-PROVIDED)", re.I)


class CuraLogFilter(logging.Filter):
    """Drop credentials and full LLM/health prompt dumps from Cura loggers."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            msg = record.getMessage()
        except Exception:
            return True
        if _SECRET.search(msg) or _PROMPT.search(msg):
            record.msg = "log_redacted category=%s" % (record.name,)
            record.args = ()
        return True


def configure_logging() -> None:
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        stream=sys.stdout,
        force=True,
    )
    filt = CuraLogFilter()
    for name in ("cura", "cura.pipeline", "cura.documents", "cura.supershyft", "cura.voice", "cura.routing"):
        logging.getLogger(name).addFilter(filt)
