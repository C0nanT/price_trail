"""Backup consistente do SQLite com o app rodando: VACUUM INTO, nunca cópia do arquivo."""
import logging
import os
import re
import sqlite3
import time
from contextlib import closing
from datetime import datetime
from pathlib import Path

from .db import BUSY_TIMEOUT_MS

DEFAULT_KEEP = 14
NAME = re.compile(r"^app-\d{8}-\d{6}\.db$")
log = logging.getLogger("pricetrail.backup")


class BackupError(Exception):
    pass


def keep_from_env() -> int:
    raw = os.environ.get("BACKUP_KEEP") or str(DEFAULT_KEEP)
    try:
        keep = int(raw)
    except ValueError:
        keep = 0
    if keep < 1:
        raise BackupError(f"BACKUP_KEEP inválido: {raw!r} (use um inteiro maior que 0)")
    return keep


def run_backup(db: Path, keep: int, now: datetime | None = None) -> dict:
    """Grava backups/app-AAAAMMDD-HHMMSS.db ao lado do banco e apaga os mais antigos além de `keep`."""
    db = Path(db)
    if not db.is_file():
        raise BackupError(f"banco não encontrado: {db}")
    started = time.monotonic()
    folder = db.parent / "backups"
    folder.mkdir(exist_ok=True)
    name = f"app-{(now or datetime.now()).strftime('%Y%m%d-%H%M%S')}.db"
    partial = folder / f".{name}.partial"
    partial.unlink(missing_ok=True)
    try:
        with closing(sqlite3.connect(db)) as conn:
            conn.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}")
            conn.execute("VACUUM INTO ?", (str(partial),))
        with closing(sqlite3.connect(partial)) as copy:
            result = copy.execute("PRAGMA integrity_check").fetchone()[0]
        if result != "ok":
            raise BackupError("o backup gerado não passou no integrity_check")
        os.replace(partial, folder / name)
    except sqlite3.Error as error:
        raise BackupError(f"falha ao gerar o backup: {error}") from error
    finally:
        partial.unlink(missing_ok=True)
    old = sorted(p for p in folder.iterdir() if NAME.match(p.name))[:-keep]
    for path in old:
        path.unlink()
    event = {"file": name, "bytes": (folder / name).stat().st_size, "deleted": len(old),
             "seconds": round(time.monotonic() - started, 3)}
    log.info("backup", extra=event)
    return event
