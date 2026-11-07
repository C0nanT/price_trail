"""Log do servidor: JSON, uma linha por evento. INFO vai para o stdout, WARNING+ para o stderr."""
import json
import logging
import os
import sys
from datetime import datetime, timezone

_STANDARD = set(vars(logging.LogRecord("", 0, "", 0, "", (), None))) | {"message", "asctime"}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        event = {
            "ts": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            event["exc_info"] = self.formatException(record.exc_info)
        event.update({key: value for key, value in vars(record).items() if key not in _STANDARD})
        return json.dumps(event, ensure_ascii=False, default=str)


def configure_server_logging(level: str | None = None) -> logging.Logger:
    """Nível: o argumento, senão LOG_LEVEL, senão INFO."""
    name = (level or os.environ.get("LOG_LEVEL") or "INFO").upper()
    log = logging.getLogger("pricetrail")
    for handler in list(log.handlers):
        log.removeHandler(handler)
        handler.close()
    formatter = JsonFormatter()
    out = logging.StreamHandler(sys.stdout)
    out.addFilter(lambda record: record.levelno < logging.WARNING)
    err = logging.StreamHandler(sys.stderr)
    err.setLevel(logging.WARNING)
    for handler in (out, err):
        handler.setFormatter(formatter)
        log.addHandler(handler)
    log.setLevel(getattr(logging, name, logging.INFO))
    log.propagate = False
    return log
