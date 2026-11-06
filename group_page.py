#!/usr/bin/env python3
"""Gera a página para agrupar produtos (group_page/index.html).

Uso: python3 group_page.py [--db ARQUIVO] [--out PASTA]

A página lê o banco e o products.json atuais, deixa você montar os grupos e
exporta um products.json novo (baixar, copiar ou salvar direto no Chrome).
Rode de novo depois de importar notas.
"""
import argparse
import json
import shutil
import sqlite3
import sys
from pathlib import Path

from products import ProductsError, drop_rejected, load_groups, load_rejected, suggest_groups

PROJECT_DIR = Path(__file__).resolve().parent
WEB_DIR = PROJECT_DIR / "web"
STATIC_FILES = ["index.html", "style.css", "app.js"]

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


def build_data(rows: list[dict], groups: dict[str, list[str]], stores: dict, rejected: set[str] = frozenset()) -> dict:
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
    return {"products": listing, "suggestions": suggestions, "groups": groups}


def main() -> int:
    parser = argparse.ArgumentParser(description="Gera a página de agrupamento de produtos.")
    parser.add_argument("--db", type=Path, default=PROJECT_DIR / "pricetrail.sqlite")
    parser.add_argument("--out", type=Path, default=PROJECT_DIR / "group_page")
    args = parser.parse_args()
    if not args.db.is_file():
        print(f"banco não encontrado: {args.db}. Rode pricetrail.py primeiro.", file=sys.stderr)
        return 2
    try:
        groups = load_groups(PROJECT_DIR / "products.json")
        rejected = load_rejected(PROJECT_DIR / "products.rejected.json")
    except ProductsError as error:
        print(f"products.json: {error}", file=sys.stderr)
        return 2
    stores_file = PROJECT_DIR / "stores.json"
    stores = json.loads(stores_file.read_text(encoding="utf-8")) if stores_file.is_file() else {}

    data = build_data(load_rows(args.db), groups, stores, rejected)
    args.out.mkdir(exist_ok=True)
    for name in STATIC_FILES:
        shutil.copy(WEB_DIR / name, args.out / name)
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    (args.out / "data.js").write_text(f"window.DATA = {payload};\n", encoding="utf-8")
    print(f"{len(data['products'])} produtos, {len(data['suggestions'])} sugestões em {args.out}/index.html")
    return 0


if __name__ == "__main__":
    sys.exit(main())
