"""Importa PDFs de NFC-e: encontra, extrai o texto, chama o parser e grava."""
import logging
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path

from .catalog import registered_store_roots
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


NEW = "NOVA"
EXISTING = "JÁ TEM"
ERROR = "ERRO"


@dataclass
class ImportResult:
    """Resultado de importar um arquivo. Os campos da nota só existem quando ela foi lida."""

    status: str
    name: str
    message: str = ""
    access_key: str | None = None
    seller_name: str | None = None
    cnpj_root: str | None = None
    item_count: int | None = None
    issued_at: str | None = None
    unregistered_store: bool = False
    unexpected: bool = False  # erro fora do parser; o detalhe está no log

    @property
    def unregistered_store_message(self) -> str:
        return (
            f"loja sem cadastro: {self.seller_name} (CNPJ {self.cnpj_root}); "
            "cadastre nome e categoria na página /groups do servidor"
        )


def import_file(conn: sqlite3.Connection, path: Path, data_dir: Path, known_roots: set[str]) -> ImportResult:
    """Importa um PDF e devolve o resultado, sem escrever no terminal.

    known_roots são as raízes de CNPJ cadastradas ou já avisadas; a função
    acrescenta a da nota lida, então o aviso de loja sem cadastro sai uma vez só.
    """
    log = logging.getLogger("pricetrail")
    try:
        note = parse_note(extract_text(path))
    except NoteError as error:
        log.error("%s: %s", path, error)
        return ImportResult(ERROR, path.name, str(error))
    except Exception:
        log.exception("%s: erro inesperado", path)
        return ImportResult(ERROR, path.name, "erro inesperado", unexpected=True)
    cnpj_root = note.seller_cnpj[:8]
    unregistered = cnpj_root not in known_roots
    result = ImportResult(
        NEW,
        path.name,
        access_key=note.access_key,
        seller_name=note.seller_name,
        cnpj_root=cnpj_root,
        item_count=len(note.items),
        issued_at=note.issued_at,
        unregistered_store=unregistered,
    )
    if unregistered:
        known_roots.add(cnpj_root)
        log.warning(result.unregistered_store_message)
    is_new = save_note(conn, note, path.name)
    source_path = path_in_data(path, data_dir)
    if source_path is not None:
        update_source_path(conn, note.access_key, source_path)
    if not is_new:
        result.status = EXISTING
    return result


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

    # Raízes cadastradas ou já avisadas: quem está aqui não gera aviso.
    known_roots = registered_store_roots(conn)
    imported = skipped = failed = 0
    for path in find_pdfs(folder):
        result = import_file(conn, path, data_dir, known_roots)
        if result.status == ERROR:
            failed += 1
            detail = f" (ver {log_file.name})" if result.unexpected else ""
            print(f"ERRO   {result.name}: {result.message}{detail}", file=sys.stderr)
            continue
        if result.unregistered_store:
            print(f"AVISO  {result.unregistered_store_message}", file=sys.stderr)
        if result.status == NEW:
            imported += 1
            print(f"NOVA   {result.name}: {result.seller_name}, {result.item_count} itens, {result.issued_at}")
        else:
            skipped += 1
            print(f"JÁ TEM {result.name}: chave {result.access_key}")
    conn.close()

    summary = f"{imported} novas, {skipped} já existentes, {failed} com erro"
    log.info(summary)
    print(summary)
    return 1 if failed else 0
