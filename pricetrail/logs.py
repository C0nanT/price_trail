"""Log do servidor: JSON, uma linha por evento. INFO vai para o stdout, WARNING+ para o stderr."""
import json
import logging
import os
import sys
import traceback
from datetime import datetime, timezone

_STANDARD = set(vars(logging.LogRecord("", 0, "", 0, "", (), None))) | {"message", "asctime"}


def exception_chain(error: BaseException) -> list[BaseException]:
    """A exceção e suas causas, da mais antiga para a mais nova, como o traceback padrão mostra."""
    chain, seen = [], set()
    while error is not None and id(error) not in seen:
        seen.add(id(error))
        chain.append(error)
        error = error.__cause__ or (None if error.__suppress_context__ else error.__context__)
    return chain[::-1]


def traceback_without_messages(error: BaseException) -> str:
    """Arquivo, linha, função e tipo de cada exceção da cadeia, sem o texto delas nem o código.

    O texto de um erro do parser ou do SQLite pode trazer nome de loja, de item ou de arquivo.
    """
    parts = []
    for index, link in enumerate(exception_chain(error)):
        if index:
            parts.append("\nA exceção acima levou a esta:\n\n")
        parts.append("Traceback (most recent call last):\n")
        for frame in traceback.extract_tb(link.__traceback__):
            parts.append(f'  File "{frame.filename}", line {frame.lineno}, in {frame.name}\n')
        kind = type(link)
        parts.append(f"{kind.__module__}.{kind.__qualname__} (mensagem omitida)\n")
    return "".join(parts).rstrip("\n")


class JsonFormatter(logging.Formatter):
    """Formato dos logs do servidor e do gunicorn. O traceback vai sem o texto das exceções."""

    def formatException(self, ei) -> str:
        return traceback_without_messages(ei[1])

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
