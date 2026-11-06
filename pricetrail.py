#!/usr/bin/env python3
"""Importa PDFs da Consulta Pública de NFC-e (SEF/SC) para um banco SQLite.

Uso: python3 pricetrail.py [PASTA] [--db ARQUIVO]

Requer `pdftotext` (poppler-utils). Reimportar é seguro: a nota é identificada
pela chave de acesso, não pelo arquivo. O CPF do consumidor não é armazenado.
"""
import argparse
import logging
import re
import sqlite3
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent

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

HEADER_RE = re.compile(
    r"\A\s*(?P<name>.+?)\s*CNPJ:\s*(?P<cnpj>[\d./-]+)\s*(?P<address>.*?,\s*[A-Z]{2})[ \t]*\n",
    re.S,
)
ITEM_RE = re.compile(
    r"(?P<description>.+?)\s*\(Código:\s*(?P<code>[^)]*?)\s*\)\s*"
    r"(?:(?P<total_before>[\d.,]+)\s*)?"  # farmácia: total logo após o código
    r"Qtde\.:\s*(?P<quantity>[\d.,]+)\s*"
    r"UN:\s*(?P<unit>\S*?)\s*"
    r"Vl\. Unit\.:\s*(?P<unit_price>[\d.,]+)"
    r"(?(total_before)|\s+(?P<total_after>[\d.,]+))",  # Atacadão: total após o preço
    re.S,
)
# Texto entre itens (ex.: cabeçalho/rodapé de impressão do navegador) cai na descrição
# do item seguinte sem alterar contagem nem soma, então é detectado aqui.
FOREIGN_TEXT_RE = re.compile(r"https?://|R\$|\d{2}/\d{2}/\d{4}")
MAX_DESCRIPTION_LENGTH = 120  # limite do campo xProd da NF-e
# Peso na descrição, ex.: 500G, 1,5KG. Ignora multipack (12X500G): a unidade é ambígua.
WEIGHT_RE = re.compile(r"(?<![\dX.,])(\d+(?:[.,]\d+)?)\s*(KG|GRS?|G)\b", re.I)
ITEMS_END = "Qtd. total de itens:"
ISSUE_RE = re.compile(
    r"Número:\s*(?P<number>\d+)\s+Série:\s*(?P<series>\d+)\s+"
    r"Emissão:\s*(?P<issued_at>\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2})"
)
ACCESS_KEY_RE = re.compile(r"Chave de acesso:\s*((?:\d{4}\s+){10}\d{4})")
ITEM_COUNT_RE = re.compile(r"Qtd\. total de itens:\s*(\d+)")
TOTAL_RE = re.compile(r"Valor total R\$:\s*([\d.,]+)")
DISCOUNT_RE = re.compile(r"Descontos R\$:\s*([\d.,]+)")
PAID_RE = re.compile(r"Valor a pagar R\$:\s*([\d.,]+)")


class NoteError(Exception):
    """O arquivo não pôde ser lido como uma NFC-e consistente."""


@dataclass
class Item:
    seq: int
    product_code: str
    description: str
    quantity: Decimal
    unit_raw: str
    unit: str
    unit_price: Decimal
    price_per_kg: Decimal | None
    total_cents: int


@dataclass
class Note:
    access_key: str
    seller_cnpj: str
    seller_name: str
    seller_address: str
    number: int
    series: int
    issued_at: str
    total_cents: int
    discount_cents: int
    paid_cents: int
    items: list[Item]


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


def to_decimal(text: str) -> Decimal:
    return Decimal(text.replace(".", "").replace(",", "."))


def to_cents(text: str) -> int:
    return int(to_decimal(text) * 100)


def squeeze(text: str) -> str:
    return " ".join(text.split())


def require(pattern: re.Pattern, text: str, label: str) -> re.Match:
    match = pattern.search(text)
    if not match:
        raise NoteError(f"campo não encontrado: {label}")
    return match


def access_key_is_valid(key: str) -> bool:
    weights = [2, 3, 4, 5, 6, 7, 8, 9]
    total = sum(int(d) * weights[i % 8] for i, d in enumerate(reversed(key[:43])))
    remainder = total % 11
    return int(key[43]) == (0 if remainder < 2 else 11 - remainder)


def compute_price_per_kg(description: str, unit: str, unit_price: Decimal) -> Decimal | None:
    if unit.upper() == "KG":
        return unit_price
    match = WEIGHT_RE.search(description)
    if not match:
        return None
    weight = Decimal(match[1].replace(",", "."))
    kilos = weight if match[2].upper() == "KG" else weight / 1000
    return unit_price / kilos if kilos else None


def clean_address(text: str) -> str:
    return ", ".join(part for part in map(str.strip, squeeze(text).split(",")) if part)


def parse_items(body: str) -> list[Item]:
    body = body.replace("Vl. Total", " ")  # título da coluna, repetido em cada item
    items = []
    end = 0
    for seq, match in enumerate(ITEM_RE.finditer(body), start=1):
        end = match.end()
        description = squeeze(match["description"])
        if FOREIGN_TEXT_RE.search(description) or len(description) > MAX_DESCRIPTION_LENGTH:
            raise NoteError(f"item {seq}: descrição suspeita: {description[:80]!r}")
        unit_raw = match["unit"]
        letters = re.match(r"[A-Za-z]+", unit_raw)
        unit = letters.group() if letters else unit_raw
        unit_price = to_decimal(match["unit_price"])
        items.append(
            Item(
                seq=seq,
                product_code=match["code"],
                description=description,
                quantity=to_decimal(match["quantity"]),
                unit_raw=unit_raw,
                unit=unit,
                unit_price=unit_price,
                price_per_kg=compute_price_per_kg(description, unit, unit_price),
                total_cents=to_cents(match["total_before"] or match["total_after"]),
            )
        )
    leftover = squeeze(body[end:])
    if leftover:
        raise NoteError(f"trecho de itens não reconhecido: {leftover[:80]!r}")
    return items


def parse_note(text: str) -> Note:
    header = require(HEADER_RE, text, "cabeçalho do emitente")
    if ITEMS_END not in text:
        raise NoteError(f"campo não encontrado: {ITEMS_END}")
    items = parse_items(text[header.end() : text.index(ITEMS_END)])

    key = re.sub(r"\s", "", require(ACCESS_KEY_RE, text, "chave de acesso")[1])
    issue = require(ISSUE_RE, text, "número/série/emissão")
    item_count = int(require(ITEM_COUNT_RE, text, "quantidade de itens")[1])
    paid_cents = to_cents(require(PAID_RE, text, "valor a pagar")[1])
    discount = DISCOUNT_RE.search(text)
    discount_cents = to_cents(discount[1]) if discount else 0
    # Sem desconto algumas notas omitem "Valor total"; ele é igual ao valor a pagar.
    total = TOTAL_RE.search(text)
    total_cents = to_cents(total[1]) if total else paid_cents + discount_cents
    cnpj = re.sub(r"\D", "", header["cnpj"])

    if not access_key_is_valid(key):
        raise NoteError(f"dígito verificador inválido na chave {key}")
    if key[6:20] != cnpj:
        raise NoteError(f"CNPJ {cnpj} difere do CNPJ da chave {key[6:20]}")
    if int(key[25:34]) != int(issue["number"]):
        raise NoteError(f"número {issue['number']} difere do número da chave")
    if len(items) != item_count:
        raise NoteError(f"{len(items)} itens lidos, a nota declara {item_count}")
    items_cents = sum(item.total_cents for item in items)
    if items_cents != total_cents:
        raise NoteError(f"itens somam {items_cents} centavos, a nota declara {total_cents}")
    for item in items:
        if abs(item.quantity * item.unit_price * 100 - item.total_cents) > 1:
            raise NoteError(f"item {item.seq}: quantidade x preço difere do total")

    return Note(
        access_key=key,
        seller_cnpj=cnpj,
        seller_name=squeeze(header["name"]),
        seller_address=clean_address(header["address"]),
        number=int(issue["number"]),
        series=int(issue["series"]),
        issued_at=datetime.strptime(issue["issued_at"], "%d/%m/%Y %H:%M:%S").isoformat(),
        total_cents=total_cents,
        discount_cents=discount_cents,
        paid_cents=paid_cents,
        items=items,
    )


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


def find_pdfs(folder: Path) -> list[Path]:
    return sorted(p for p in folder.rglob("*") if p.is_file() and p.suffix.lower() == ".pdf")


def main() -> int:
    parser = argparse.ArgumentParser(description="Importa PDFs de NFC-e para SQLite.")
    parser.add_argument("folder", nargs="?", type=Path, default=PROJECT_DIR / "data")
    parser.add_argument("--db", type=Path, default=PROJECT_DIR / "pricetrail.sqlite")
    parser.add_argument("--log", type=Path, default=PROJECT_DIR / "pricetrail.log")
    args = parser.parse_args()

    logging.basicConfig(
        filename=args.log,
        encoding="utf-8",
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    log = logging.getLogger("pricetrail")
    log.info("importação iniciada: pasta=%s db=%s", args.folder, args.db)

    if not args.folder.is_dir():
        log.error("pasta não encontrada: %s", args.folder)
        print(f"pasta não encontrada: {args.folder}", file=sys.stderr)
        return 2

    conn = sqlite3.connect(args.db)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)

    imported = skipped = failed = 0
    for path in find_pdfs(args.folder):
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
            print(f"ERRO   {path.name}: erro inesperado (ver {args.log.name})", file=sys.stderr)
            continue
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


if __name__ == "__main__":
    sys.exit(main())
