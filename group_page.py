#!/usr/bin/env python3
"""Gera a página para agrupar produtos (group_page/index.html).

Uso: python3 group_page.py [--db ARQUIVO] [--out PASTA]

A página lê o banco e o products.json atuais, deixa você montar os grupos e
exporta um products.json novo (baixar, copiar ou salvar direto no Chrome).
Rode de novo depois de importar notas. É a versão em arquivo da página de
pricetrail/web/group, que o servidor entrega com dados atuais em /groups.
"""
import argparse
import json
import os
import shutil
import sqlite3
import sys
from pathlib import Path
from urllib.parse import quote

from pricetrail.pdfs import extract_text, find_pdfs
from pricetrail.nfce import ACCESS_KEY_RE, NoteError
from products import ProductsError, drop_rejected, load_groups, load_rejected, suggest_groups

PROJECT_DIR = Path(__file__).resolve().parent
WEB_DIR = PROJECT_DIR / "pricetrail" / "web" / "group"

QUERY = """
SELECT seller_cnpj AS cnpj, seller_name, product_code AS code, description, unit,
       group_concat(unit_price) AS prices, COUNT(DISTINCT access_key) AS purchases,
       MAX(issued_at) AS last
FROM price_history
GROUP BY seller_cnpj, product_code, description, unit
"""


def load_rows(db_path: Path) -> list[dict]:
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    rows = [{**dict(r), "prices": [float(p) for p in r["prices"].split(",")]} for r in conn.execute(QUERY)]
    conn.close()
    return rows


NOTES_QUERY = """
SELECT substr(n.seller_cnpj, 1, 8) || ':' || i.product_code AS ref,
       n.issued_at, n.source_file, n.number, n.access_key,
       SUM(i.quantity) AS quantity, MIN(i.unit_price) AS price
FROM items i JOIN notes n USING (access_key)
GROUP BY n.access_key, i.product_code
ORDER BY n.issued_at DESC
"""


def pdf_index(data_dir: Path) -> tuple[dict[str, Path], dict[str, Path]]:
    """PDFs por chave de acesso (lida do conteúdo, resiste a renomear) e por nome."""
    by_key, by_name = {}, {}
    if not data_dir.is_dir():
        return by_key, by_name
    for pdf in find_pdfs(data_dir):
        by_name.setdefault(pdf.name, pdf)
        try:
            match = ACCESS_KEY_RE.search(extract_text(pdf))
        except (NoteError, OSError):
            continue
        if match:
            by_key.setdefault("".join(match[1].split()), pdf)
    return by_key, by_name


def load_notes(db_path: Path, data_dir: Path, out_dir: Path) -> dict[str, list[dict]]:
    """Notas em que cada produto aparece, com o caminho do PDF relativo à página."""
    by_key, by_name = pdf_index(data_dir)
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    notes: dict[str, list[dict]] = {}
    for ref, issued_at, source, number, key, quantity, price in conn.execute(NOTES_QUERY):
        pdf = by_key.get(key) or by_name.get(source)
        href = quote(os.path.relpath(pdf, out_dir).replace(os.sep, "/")) if pdf else None
        notes.setdefault(ref, []).append(
            {"date": issued_at[:10], "number": number, "file": source, "href": href,
             "quantity": quantity, "price": price}
        )
    conn.close()
    return notes


def build_data(rows: list[dict], groups: dict[str, list[str]], stores: dict, rejected: set[str] = frozenset(),
               notes: dict[str, list[dict]] | None = None) -> dict:
    products = {}
    for row in sorted(rows, key=lambda r: r["last"]):  # a descrição mais recente vence
        ref = f"{row['cnpj'][:8]}:{row['code']}"
        item = products.setdefault(
            ref,
            {"ref": ref, "code": row["code"], "units": [], "prices": [], "purchases": 0,
             "store": stores.get(row["cnpj"][:8], {}).get("store", row["seller_name"])},
        )
        item["description"] = row["description"]
        if row["unit"] not in item["units"]:
            item["units"].append(row["unit"])
        item["prices"] += row["prices"]
        item["purchases"] += row["purchases"]
    listing = [
        {"ref": p["ref"], "code": p["code"], "description": p["description"], "unit": "/".join(p["units"]),
         "store": p["store"], "purchases": p["purchases"], "min": min(p["prices"]), "max": max(p["prices"])}
        for p in products.values()
    ]
    suggestions = [
        {"name": s["name"], "reason": s["reason"], "refs": s["refs"], "warnings": s["warnings"]}
        for s in drop_rejected(suggest_groups(rows), set(rejected))
    ]
    return {"notes": notes or {}, "products": listing, "suggestions": suggestions, "groups": groups}


def static_page() -> str:
    """A página do servidor, adaptada para abrir como arquivo, com os dados em data.js."""
    html = (WEB_DIR / "index.html").read_text(encoding="utf-8")
    html = html.replace('<a href="/">', '<a href="../chart.html">').replace("/static/group/", "")
    return html.replace('<script src="app.js">', '<script src="data.js"></script>\n<script src="app.js">')


def main() -> int:
    parser = argparse.ArgumentParser(description="Gera a página de agrupamento de produtos.")
    parser.add_argument("--db", type=Path, default=PROJECT_DIR / "pricetrail.sqlite")
    parser.add_argument("--data", type=Path, default=PROJECT_DIR / "data", help="pasta dos PDFs")
    parser.add_argument("--out", type=Path, default=PROJECT_DIR / "group_page")
    args = parser.parse_args()
    if not args.db.is_file():
        print(f"banco não encontrado: {args.db}. Rode python3 -m pricetrail import primeiro.", file=sys.stderr)
        return 2
    try:
        groups = load_groups(PROJECT_DIR / "products.json")
        rejected = load_rejected(PROJECT_DIR / "products.rejected.json")
    except ProductsError as error:
        print(f"products.json: {error}", file=sys.stderr)
        return 2
    stores_file = PROJECT_DIR / "stores.json"
    stores = json.loads(stores_file.read_text(encoding="utf-8")) if stores_file.is_file() else {}

    args.out.mkdir(exist_ok=True)
    notes = load_notes(args.db, args.data, args.out)
    data = build_data(load_rows(args.db), groups, stores, rejected, notes)
    for name in ("style.css", "app.js"):
        shutil.copy(WEB_DIR / name, args.out / name)
    (args.out / "index.html").write_text(static_page(), encoding="utf-8")
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    (args.out / "data.js").write_text(f"window.DATA = {payload};\n", encoding="utf-8")
    print(f"{len(data['products'])} produtos, {len(data['suggestions'])} sugestões em {args.out}/index.html")
    return 0


if __name__ == "__main__":
    sys.exit(main())
