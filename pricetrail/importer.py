"""Importa PDFs de NFC-e: encontra, extrai o texto, chama o parser e grava."""
import json
import logging
import sqlite3
import subprocess
import sys
from pathlib import Path

from .db import connect
from .nfce import Note, NoteError, parse_note


def extract_text(path: Path) -> str:
    """Extrai o texto na ordem visual.

    Não usar -raw: ele separa rótulos de valores nos totais e joga esses valores
    no meio dos itens, na quebra de página.
    """
    result = subprocess.run(
        ["pdftotext", "-layout", str(path), "-"],
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        raise NoteError(f"pdftotext falhou: {result.stderr.strip()}")
    return result.stdout


def save_note(conn: sqlite3.Connection, note: Note, source_file: str) -> bool:
    """Grava a nota e seus itens atomicamente. Retorna False se ela já existia."""
    with conn:
        cursor = conn.execute(
            "INSERT OR IGNORE INTO notes VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                note.access_key,
                note.seller_cnpj,
                note.seller_name,
                note.seller_address,
                note.number,
                note.series,
                note.issued_at,
                len(note.items),
                note.total_cents,
                note.discount_cents,
                note.paid_cents,
                source_file,
            ),
        )
        if cursor.rowcount == 0:
            return False
        conn.executemany(
            "INSERT INTO items VALUES (?,?,?,?,?,?,?,?,?,?)",
            [
                (
                    note.access_key,
                    item.seq,
                    item.product_code,
                    item.description,
                    float(item.quantity),
                    item.unit_raw,
                    item.unit,
                    float(item.unit_price),
                    None if item.price_per_kg is None else round(float(item.price_per_kg), 2),
                    item.total_cents,
                )
                for item in note.items
            ],
        )
    return True


def load_known_stores(path: Path) -> set[str]:
    """Prefixos de CNPJ (8 dígitos) cadastrados em stores.json; vazio se ausente."""
    try:
        return set(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return set()


def is_unknown_store(cnpj: str, known: set[str]) -> bool:
    return cnpj[:8] not in known


def find_pdfs(folder: Path) -> list[Path]:
    return sorted(p for p in folder.rglob("*") if p.is_file() and p.suffix.lower() == ".pdf")


def import_folder(folder: Path, db: Path, stores: Path, log_file: Path, legacy_dir: Path | None = None) -> int:
    """Importa os PDFs da pasta. Retorna o código de saída (0, 1 com erros, 2 sem pasta)."""
    logging.basicConfig(
        filename=log_file,
        encoding="utf-8",
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    log = logging.getLogger("pricetrail")
    log.info("importação iniciada: pasta=%s db=%s", folder, db)

    if not folder.is_dir():
        log.error("pasta não encontrada: %s", folder)
        print(f"pasta não encontrada: {folder}", file=sys.stderr)
        return 2

    conn = connect(db, legacy_dir)

    known_stores = load_known_stores(stores)
    warned_stores: set[str] = set()
    imported = skipped = failed = 0
    for path in find_pdfs(folder):
        try:
            note = parse_note(extract_text(path))
        except NoteError as error:
            failed += 1
            log.error("%s: %s", path, error)
            print(f"ERRO   {path.name}: {error}", file=sys.stderr)
            continue
        except Exception:
            failed += 1
            log.exception("%s: erro inesperado", path)
            print(f"ERRO   {path.name}: erro inesperado (ver {log_file.name})", file=sys.stderr)
            continue
        prefix = note.seller_cnpj[:8]
        if is_unknown_store(note.seller_cnpj, known_stores) and prefix not in warned_stores:
            warned_stores.add(prefix)
            message = (
                f"loja fora do stores.json: {note.seller_name} (CNPJ {prefix}); "
                f'adicione "{prefix}": {{"store": "...", "category": "..."}}'
            )
            log.warning(message)
            print(f"AVISO  {message}", file=sys.stderr)
        if save_note(conn, note, path.name):
            imported += 1
            print(f"NOVA   {path.name}: {note.seller_name}, {len(note.items)} itens, {note.issued_at}")
        else:
            skipped += 1
            print(f"JÁ TEM {path.name}: chave {note.access_key}")
    conn.close()

    summary = f"{imported} novas, {skipped} já existentes, {failed} com erro"
    log.info(summary)
    print(summary)
    return 1 if failed else 0
