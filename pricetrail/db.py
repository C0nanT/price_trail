"""Conexão e schema do banco SQLite."""
import sqlite3
from pathlib import Path

SCHEMA = """
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
);

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
);

DROP VIEW IF EXISTS price_history;
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
JOIN notes n USING (access_key);
"""


def connect(path: Path) -> sqlite3.Connection:
    """Abre o banco, liga as chaves estrangeiras e garante o schema."""
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    return conn
