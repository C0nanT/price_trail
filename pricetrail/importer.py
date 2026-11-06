"""Importa PDFs de NFC-e: encontra, extrai o texto, chama o parser e grava."""
import logging
import sqlite3
import sys
from pathlib import Path

from .catalog import is_registered_store
from .db import connect
from .nfce import Note, NoteError, parse_note
from .pdfs import extract_text, find_pdfs, path_in_data


def save_note(conn: sqlite3.Connection, note: Note, source_file: str) -> bool:
    """Grava a nota e seus itens atomicamente. Retorna False se ela já existia."""
    with conn:
        cursor = conn.execute(
            """
            INSERT OR IGNORE INTO notes (
                access_key, seller_cnpj, seller_name, seller_address, number, series, issued_at,
                item_count, total_cents, discount_cents, paid_cents, source_file
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """,
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


def update_source_path(conn: sqlite3.Connection, access_key: str, source_path: str) -> None:
    """Aponta a nota para o arquivo que acabou de ser lido, que é dela com certeza.

    Vale também quando o caminho antigo ainda existe: ele pode ser agora outra nota.
    """
    with conn:
        conn.execute(
            "UPDATE notes SET source_path = ? WHERE access_key = ? AND source_path IS NOT ?",
            (source_path, access_key, source_path),
        )


def import_folder(
    folder: Path, db: Path, log_file: Path, data_dir: Path, legacy_dir: Path | None = None
) -> int:
    """Importa os PDFs da pasta. Retorna o código de saída (0, 1 com erros, 2 sem pasta).

    data_dir é a pasta de dados, a que o servidor usa para abrir os PDFs. folder
    pode ser ela ou uma subpasta; de fora dela, as notas ficam sem link para o PDF.
    """
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

    conn = connect(db, data_dir, legacy_dir)

    if path_in_data(folder, data_dir) is None:
        message = f"{folder} está fora da pasta de dados ({data_dir}): as notas ficam sem link para o PDF; use --data"
        log.warning(message)
        print(f"AVISO  {message}", file=sys.stderr)

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
        if prefix not in warned_stores and not is_registered_store(conn, prefix):
            warned_stores.add(prefix)
            message = (
                f"loja sem cadastro: {note.seller_name} (CNPJ {prefix}); "
                "cadastre nome e categoria na página /groups do servidor"
            )
            log.warning(message)
            print(f"AVISO  {message}", file=sys.stderr)
        is_new = save_note(conn, note, path.name)
        source_path = path_in_data(path, data_dir)
        if source_path is not None:
            update_source_path(conn, note.access_key, source_path)
        if is_new:
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
