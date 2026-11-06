#!/usr/bin/env python3
"""Lista candidatos a agrupamento de produtos para você revisar.

Uso: python3 suggest_products.py [--db ARQUIVO] [--out ARQUIVO]

Não altera nada. Escreve products.suggested.json: copie os grupos que forem o
mesmo produto para products.json. Grupos com aviso (preço ou unidade muito
diferente) provavelmente são tamanhos/variações distintas.
"""
import argparse
import json
import sqlite3
import sys
from pathlib import Path

from products import suggest_groups

PROJECT_DIR = Path(__file__).resolve().parent
QUERY = """
SELECT seller_cnpj AS cnpj, product_code AS code, description, unit,
       group_concat(unit_price) AS prices, COUNT(DISTINCT access_key) AS purchases
FROM price_history
GROUP BY seller_cnpj, product_code, description, unit
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Sugere agrupamentos de produtos.")
    parser.add_argument("--db", type=Path, default=PROJECT_DIR / "pricetrail.sqlite")
    parser.add_argument("--out", type=Path, default=PROJECT_DIR / "products.suggested.json")
    args = parser.parse_args()
    if not args.db.is_file():
        print(f"banco não encontrado: {args.db}", file=sys.stderr)
        return 2

    conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    rows = []
    for row in conn.execute(QUERY):
        rows.append({**dict(row), "prices": [float(p) for p in row["prices"].split(",")]})
    conn.close()

    suggestions = suggest_groups(rows)
    output = {}
    for number, s in enumerate(suggestions, start=1):
        flag = f"  !! {'; '.join(s['warnings'])}" if s["warnings"] else ""
        print(f"[{number}] {s['name']}  ({s['reason']}){flag}")
        for m in s["members"]:
            print(f"      {m['code']:>8}  {m['unit']:<4} {m['purchases']}x  {m['description']}  "
                  f"R$ {min(m['prices']):.2f}-{max(m['prices']):.2f}")
        key = s["name"] if s["name"] not in output else f"{s['name']} ({number})"
        output[key] = s["refs"]
    args.out.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\n{len(suggestions)} sugestões em {args.out}. Copie as aprovadas para products.json.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
