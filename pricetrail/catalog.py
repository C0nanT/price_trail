"""Consultas e regras de produtos."""
import sqlite3

# Linhas repetidas de um produto na mesma nota e com o mesmo preço viram uma compra.
PURCHASES_QUERY = """
SELECT substr(h.seller_cnpj, 1, 8) AS seller_root, h.seller_name, h.product_code, h.description, h.unit,
       h.issued_at, h.unit_price,
       SUM(h.quantity) AS quantity,
       SUM(h.line_total) AS line_total,
       COALESCE(s.store, h.seller_name) AS store,
       COALESCE(s.category, 'Outros') AS category,
       g.name AS group_name
FROM price_history h
LEFT JOIN stores s ON s.cnpj_root = substr(h.seller_cnpj, 1, 8)
LEFT JOIN group_refs r ON r.cnpj_root = substr(h.seller_cnpj, 1, 8) AND r.product_code = h.product_code
LEFT JOIN product_groups g ON g.id = r.group_id
GROUP BY seller_root, h.product_code, h.unit, h.access_key, h.unit_price
ORDER BY h.issued_at
"""


def list_products(conn: sqlite3.Connection) -> list[dict]:
    """Um produto por (raiz do CNPJ, código, unidade), ou por (grupo, unidade)."""
    products: dict[tuple, dict] = {}
    for row in conn.execute(PURCHASES_QUERY):
        group = row["group_name"]
        key = (group, row["unit"]) if group else (row["seller_root"], row["product_code"], row["unit"])
        product = products.setdefault(
            key,
            {
                "code": row["product_code"],
                "description": group or row["description"],
                "unit": row["unit"],
                "sellers": [],
                "stores": [],
                "categories": [],
                "purchases": [],
            },
        )
        for field, value in (
            ("sellers", row["seller_name"]),
            ("stores", row["store"]),
            ("categories", row["category"]),
        ):
            if value not in product[field]:
                product[field].append(value)
        codes = product["code"].split(", ")
        if row["product_code"] not in codes:
            product["code"] = ", ".join(sorted(codes + [row["product_code"]]))
        product["purchases"].append(
            {
                "issued_at": row["issued_at"],
                "seller": row["seller_name"],
                "price": row["unit_price"],
                "quantity": row["quantity"],
                "total": row["line_total"],
            }
        )
    for product in products.values():
        product["purchases"].sort(key=lambda purchase: purchase["issued_at"])
        product["seller"] = ", ".join(product.pop("sellers"))
    return sorted(
        products.values(),
        key=lambda product: (-len(product["purchases"]), product["description"]),
    )
