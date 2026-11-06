"""Conexão, schema e migrações do banco SQLite.

O schema evolui por migrações numeradas, controladas por PRAGMA user_version. A
versão 0 é um banco inexistente ou o banco de antes das migrações, que já tem
notes, items e a view.
"""
import json
import re
import sqlite3
from pathlib import Path

from .nfce import ACCESS_KEY_RE, NoteError
from .pdfs import extract_text, find_pdfs, path_in_data

BASE_STATEMENTS = (
    """
CREATE TABLE IF NOT EXISTS notes (
    access_key     TEXT PRIMARY KEY,
    seller_cnpj    TEXT NOT NULL,
    seller_name    TEXT NOT NULL,
    seller_address TEXT NOT NULL,
    number         INTEGER NOT NULL,
    series         INTEGER NOT NULL,
    issued_at      TEXT NOT NULL,     -- ISO 8601, horário local da emissão
    item_count     INTEGER NOT NULL,
    total_cents    INTEGER NOT NULL,  -- soma dos itens, antes do desconto
    discount_cents INTEGER NOT NULL,  -- desconto da nota, não rateado por item
    paid_cents     INTEGER NOT NULL,
    source_file    TEXT NOT NULL      -- arquivo que trouxe a nota primeiro
)
""",
    """
CREATE TABLE IF NOT EXISTS items (
    access_key   TEXT NOT NULL REFERENCES notes(access_key),
    seq          INTEGER NOT NULL,    -- posição na nota; o mesmo código pode repetir
    product_code TEXT NOT NULL,       -- código interno da loja, não é EAN
    description  TEXT NOT NULL,
    quantity     REAL NOT NULL,
    unit_raw     TEXT NOT NULL,       -- como impresso, ex.: UND9
    unit         TEXT NOT NULL,       -- só as letras, ex.: UND
    unit_price   REAL NOT NULL,       -- em reais; pode ter mais de 2 casas
    price_per_kg REAL,                -- NULL quando o peso não é conhecido
    total_cents  INTEGER NOT NULL,
    PRIMARY KEY (access_key, seq)
)
""",
    "DROP VIEW IF EXISTS price_history",
    """
CREATE VIEW price_history AS
SELECT date(n.issued_at) AS purchase_date,
       n.issued_at,
       n.seller_cnpj,
       n.seller_name,
       n.seller_address,
       i.product_code,
       i.description,
       i.quantity,
       i.unit,
       i.unit_price,
       i.price_per_kg,
       i.total_cents / 100.0 AS line_total,
       n.access_key,
       i.seq
FROM items i
JOIN notes n USING (access_key)
""",
)

# O schema da versão 0, como um script só.
SCHEMA = ";\n".join(BASE_STATEMENTS) + ";"

CURATION_STATEMENTS = (
    """
CREATE TABLE stores (
    cnpj_root TEXT PRIMARY KEY,       -- 8 primeiros dígitos, iguais em todas as filiais
    store     TEXT,
    category  TEXT
)
""",
    """
CREATE TABLE product_groups (
    id   INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
)
""",
    """
CREATE TABLE group_refs (
    group_id     INTEGER NOT NULL REFERENCES product_groups(id) ON DELETE CASCADE,
    cnpj_root    TEXT NOT NULL,
    product_code TEXT NOT NULL,
    PRIMARY KEY (cnpj_root, product_code)  -- uma referência fica em um grupo só
)
""",
)


CODE_REF_RE = re.compile(r"^(\d{8}):(\S+)$")


class MigrationError(Exception):
    """A migração não pôde ser aplicada; o banco continua como estava."""


def read_legacy_json(legacy_dir: Path | None, name: str) -> dict:
    """Lê um JSON da curadoria antiga. Sem pasta ou sem arquivo, não há nada a carregar."""
    if legacy_dir is None or not (legacy_dir / name).is_file():
        return {}
    try:
        data = json.loads((legacy_dir / name).read_text(encoding="utf-8"))
    except ValueError as error:
        raise MigrationError(f"{name} não é um JSON válido: {error}") from error
    if not isinstance(data, dict):
        raise MigrationError(f"{name} deve ser um objeto JSON")
    return data


def load_legacy_stores(conn: sqlite3.Connection, legacy_dir: Path | None) -> None:
    stores = read_legacy_json(legacy_dir, "stores.json")
    conn.executemany(
        "INSERT INTO stores (cnpj_root, store, category) VALUES (?, ?, ?)",
        [(root, entry.get("store"), entry.get("category")) for root, entry in stores.items()],
    )


def load_legacy_groups(conn: sqlite3.Connection, legacy_dir: Path | None) -> None:
    for name, refs in read_legacy_json(legacy_dir, "products.json").items():
        if not isinstance(refs, list):
            raise MigrationError(f'products.json deve ser {{"Nome": ["raiz:código", ...]}}, veja o grupo {name!r}')
        group_id = conn.execute("INSERT INTO product_groups (name) VALUES (?)", (name,)).lastrowid
        for ref in dict.fromkeys(refs):
            match = CODE_REF_RE.match(ref)
            if not match:
                raise MigrationError(f"products.json: {ref!r} no grupo {name!r} não é uma referência raiz:código")
            try:
                conn.execute(
                    "INSERT INTO group_refs (group_id, cnpj_root, product_code) VALUES (?, ?, ?)",
                    (group_id, match[1], match[2]),
                )
            except sqlite3.IntegrityError as error:
                raise MigrationError(f"products.json: {ref!r} está em mais de um grupo") from error


def migration_1(conn: sqlite3.Connection, _data_dir: Path | None, legacy_dir: Path | None) -> None:
    """Schema base, curadoria no banco e carga inicial dos JSONs."""
    for statement in BASE_STATEMENTS + CURATION_STATEMENTS:
        conn.execute(statement)
    load_legacy_stores(conn, legacy_dir)
    load_legacy_groups(conn, legacy_dir)


def index_pdfs(data_dir: Path) -> tuple[dict[str, Path], dict[str, Path]]:
    """PDFs por chave de acesso e, só para os sem chave legível, por nome do arquivo.

    Um PDF com chave é de outra nota mesmo que o nome coincida com o source_file.
    """
    by_key: dict[str, Path] = {}
    by_name: dict[str, Path] = {}
    for pdf in find_pdfs(data_dir):
        try:
            match = ACCESS_KEY_RE.search(extract_text(pdf))
        except (NoteError, OSError):
            match = None
        if match:
            by_key.setdefault("".join(match[1].split()), pdf)
        else:
            by_name.setdefault(pdf.name, pdf)
    return by_key, by_name


def backfill_source_paths(conn: sqlite3.Connection, data_dir: Path | None) -> None:
    notes = conn.execute("SELECT access_key, source_file FROM notes").fetchall()
    if not notes:
        return
    # Esta carga roda uma vez só: sem a pasta, as notas perderiam o link sem aviso.
    if data_dir is None or not data_dir.is_dir():
        raise MigrationError(f"pasta de dados não encontrada ({data_dir}), indique onde estão os PDFs com --data")
    by_key, by_name = index_pdfs(data_dir)
    for key, source_file in notes:
        pdf = by_key.get(key) or by_name.get(source_file)
        if pdf:
            conn.execute(
                "UPDATE notes SET source_path = ? WHERE access_key = ?",
                (path_in_data(pdf, data_dir), key),
            )


def migration_2(conn: sqlite3.Connection, data_dir: Path | None, _legacy_dir: Path | None) -> None:
    """Caminho do PDF de cada nota, relativo à pasta de dados."""
    conn.execute("ALTER TABLE notes ADD COLUMN source_path TEXT")
    backfill_source_paths(conn, data_dir)


# A posição na lista é o número da versão: a primeira migração leva à versão 1.
MIGRATIONS = (migration_1, migration_2)


def user_version(conn: sqlite3.Connection) -> int:
    return conn.execute("PRAGMA user_version").fetchone()[0]


def migrate(conn: sqlite3.Connection, data_dir: Path | None, legacy_dir: Path | None) -> None:
    """Aplica as migrações pendentes numa transação só: ou todas, ou nenhuma."""
    if user_version(conn) >= len(MIGRATIONS):
        return
    # Não pode rodar dentro de transação, e fica gravado no arquivo do banco.
    conn.execute("PRAGMA journal_mode = WAL")
    # executescript faria commit antes de rodar, por isso os comandos vão um a um.
    conn.execute("BEGIN IMMEDIATE")
    with conn:
        # Outro processo pode ter migrado enquanto este esperava o BEGIN.
        for version in range(user_version(conn) + 1, len(MIGRATIONS) + 1):
            MIGRATIONS[version - 1](conn, data_dir, legacy_dir)
            conn.execute(f"PRAGMA user_version = {version}")


def connect(path: Path, data_dir: Path | None = None, legacy_dir: Path | None = None) -> sqlite3.Connection:
    """Abre o banco, liga as chaves estrangeiras e aplica as migrações pendentes.

    data_dir é a pasta dos PDFs e legacy_dir a dos JSONs da curadoria antiga. As
    duas só são lidas pelas migrações que fazem a carga inicial: o banco já migrado
    não as usa. Migrar um banco com notas sem data_dir levanta MigrationError.
    """
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        migrate(conn, data_dir, legacy_dir)
    except BaseException:
        conn.close()
        raise
    return conn
