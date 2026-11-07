#!/usr/bin/env python3
"""Parser puro de NFC-e (SEF/SC): texto da nota para `Note`.

Não conhece banco nem PDF. O CPF do consumidor não é armazenado.
"""
import re
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

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
ACCESS_KEY_LINE_RE = re.compile(r"Chave de acesso:\s*((?:\d{4}\s+){10}\d{4})")
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

    key = re.sub(r"\s", "", require(ACCESS_KEY_LINE_RE, text, "chave de acesso")[1])
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
