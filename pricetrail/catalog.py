"""Consultas e regras de produtos, grupos, sugestões e notas."""
import difflib
import itertools
import json
import re
import sqlite3
import unicodedata
from collections import defaultdict
from pathlib import Path

from .db import canonical_pair, is_cnpj_root, parse_ref
from .pdfs import resolve_in_data

SIMILAR_RATIO = 0.88

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


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFD", text).upper()
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return " ".join(re.sub(r"[^A-Z0-9]+", " ", text).split())


def similar(a: str, b: str) -> bool:
    """ratio() é lento e roda a cada request; os dois primeiros são limites superiores dele."""
    matcher = difflib.SequenceMatcher(None, a, b)
    return (
        matcher.real_quick_ratio() > SIMILAR_RATIO
        and matcher.quick_ratio() > SIMILAR_RATIO
        and matcher.ratio() > SIMILAR_RATIO
    )


def suggest_groups(rows: list[dict]) -> list[dict]:
    """Candidatos a agrupamento, para revisão humana. Nada é aplicado.

    rows: um dict por (cnpj, código, unidade) com cnpj, code, description, unit,
    prices (lista), purchases (int). Sugere, na mesma loja: mesma descrição com
    códigos diferentes, e descrições quase iguais.
    """
    by_store = defaultdict(list)
    for row in rows:
        by_store[row["cnpj"][:8]].append(row)

    suggestions = []
    for store, items in by_store.items():
        by_description = defaultdict(list)
        for item in items:
            by_description[normalize(item["description"])].append(item)
        for description, members in sorted(by_description.items()):
            if len(members) > 1:
                suggestions.append(_suggestion("mesma descrição", store, members))
        names = sorted(by_description)
        for index, a in enumerate(names):
            for b in names[index + 1 :]:
                if similar(a, b):
                    suggestions.append(
                        _suggestion("descrições parecidas", store, by_description[a] + by_description[b])
                    )
    return suggestions


def _warnings(members: list[dict]) -> list[str]:
    prices = [price for member in members for price in member["prices"]]
    warnings = []
    if len({member["unit"] for member in members}) > 1:
        warnings.append("unidades diferentes")
    if prices and max(prices) / min(prices) > 1.5:
        warnings.append(f"preços muito diferentes ({min(prices):.2f} a {max(prices):.2f})")
    return warnings


def _suggestion(reason: str, store: str, members: list[dict]) -> dict:
    warnings = _warnings(members)
    first = min(members, key=lambda m: m["description"])
    # Um código com duas descrições ou unidades é mais de uma linha, mas uma referência só.
    codes = sorted({member["code"] for member in members})
    return {
        "reason": reason,
        "name": first["description"],
        "refs": [f"{store}:{code}" for code in codes],
        "members": members,
        "warnings": warnings,
    }


def split_ref(ref: str) -> tuple[str, str]:
    root, code = ref.split(":", 1)
    return root, code


def is_rejected(rejected: set[tuple], ref_a: str, ref_b: str) -> bool:
    return canonical_pair(split_ref(ref_a), split_ref(ref_b)) in rejected


def drop_rejected(suggestions: list[dict], rejected: set[tuple]) -> list[dict]:
    """Aplica os pares marcados como "não juntar".

    Um produto só sai da sugestão se todos os seus pares nela estiverem rejeitados.
    Sugestão que ficar com menos de 2 produtos some; duplicadas (mesmas
    referências, ex.: "mesma descrição" e "parecidas") são unificadas.
    """
    result, seen = [], set()
    for suggestion in suggestions:
        refs = [
            ref for ref in suggestion["refs"]
            if any(other != ref and not is_rejected(rejected, ref, other) for other in suggestion["refs"])
        ]
        key = tuple(refs)
        if len(refs) < 2 or key in seen:
            continue
        seen.add(key)
        keep = {split_ref(ref)[1] for ref in refs}
        members = [m for m in suggestion["members"] if m["code"] in keep]
        result.append({**suggestion, "refs": refs, "members": members, "warnings": _warnings(members)})
    return result


# cnpj é o de uma das filiais: suggest_groups e as referências só usam a raiz.
PRODUCT_ROWS_QUERY = """
SELECT h.seller_cnpj AS cnpj, h.product_code AS code, h.description, h.unit,
       group_concat(h.unit_price) AS prices, COUNT(DISTINCT h.access_key) AS purchases,
       MAX(h.issued_at) AS last,
       COALESCE(s.store, h.seller_name) AS store
FROM price_history h
LEFT JOIN stores s ON s.cnpj_root = substr(h.seller_cnpj, 1, 8)
GROUP BY substr(h.seller_cnpj, 1, 8), h.product_code, h.description, h.unit
"""

GROUPS_QUERY = """
SELECT g.name, r.cnpj_root || ':' || r.product_code AS ref
FROM product_groups g
JOIN group_refs r ON r.group_id = g.id
ORDER BY g.id, r.rowid
"""

NOTES_QUERY = """
SELECT substr(n.seller_cnpj, 1, 8) || ':' || i.product_code AS ref,
       n.issued_at, n.source_file, n.source_path, n.number, n.access_key,
       SUM(i.quantity) AS quantity, MIN(i.unit_price) AS price
FROM items i JOIN notes n USING (access_key)
GROUP BY n.access_key, i.product_code
ORDER BY n.issued_at DESC
"""


def load_product_rows(conn: sqlite3.Connection) -> list[dict]:
    """Uma linha por (raiz do CNPJ, código, descrição, unidade)."""
    return [
        {**dict(row), "prices": [float(price) for price in row["prices"].split(",")]}
        for row in conn.execute(PRODUCT_ROWS_QUERY)
    ]


def list_ref_products(rows: list[dict]) -> list[dict]:
    """Um produto por referência raiz:código, com a descrição mais recente."""
    products: dict[str, dict] = {}
    for row in sorted(rows, key=lambda r: r["last"]):
        ref = f"{row['cnpj'][:8]}:{row['code']}"
        product = products.setdefault(
            ref,
            {"ref": ref, "code": row["code"], "units": [], "prices": [], "purchases": 0, "store": row["store"]},
        )
        product["description"] = row["description"]
        if row["unit"] not in product["units"]:
            product["units"].append(row["unit"])
        product["prices"] += row["prices"]
        product["purchases"] += row["purchases"]
    return [
        {
            "ref": product["ref"],
            "code": product["code"],
            "description": product["description"],
            "unit": "/".join(product["units"]),
            "store": product["store"],
            "purchases": product["purchases"],
            "min": min(product["prices"]),
            "max": max(product["prices"]),
        }
        for product in products.values()
    ]


def list_suggestions(rows: list[dict], rejected: set[tuple]) -> list[dict]:
    return [
        {"name": s["name"], "reason": s["reason"], "refs": s["refs"], "warnings": s["warnings"]}
        for s in drop_rejected(suggest_groups(rows), rejected)
    ]


class GroupsError(ValueError):
    """Grupos que violam as regras; a mensagem é mostrada ao usuário."""


def validate_groups(pairs: list[tuple[str, object]]) -> list[tuple[str, list[str]]]:
    """Confere nomes e referências e devolve (nome, refs) limpos; levanta GroupsError."""
    result: list[tuple[str, list[str]]] = []
    names: set[str] = set()
    owner: dict[str, str] = {}
    for raw_name, refs in pairs:
        name = raw_name.strip()
        if not name:
            raise GroupsError("Todo grupo precisa de um nome.")
        if name in names:
            raise GroupsError(f"O nome “{name}” aparece em mais de um grupo.")
        names.add(name)
        if not isinstance(refs, list) or not refs:
            raise GroupsError(f"O grupo “{name}” precisa de uma lista de produtos.")
        for ref in refs:
            if not parse_ref(ref):
                raise GroupsError(f"“{ref}” no grupo “{name}” não é uma referência raiz:código.")
            if owner.setdefault(ref, name) != name:
                raise GroupsError(f"O produto {ref} está nos grupos “{owner[ref]}” e “{name}”.")
        result.append((name, list(dict.fromkeys(refs))))
    return result


def replace_groups(conn: sqlite3.Connection, pairs: list[tuple[str, object]]) -> None:
    """Troca todos os grupos numa transação: se algo falhar, nada muda."""
    groups = validate_groups(pairs)
    with conn:
        _write_groups(conn, groups)


def _write_groups(conn: sqlite3.Connection, groups: list[tuple[str, list[str]]]) -> None:
    """Troca os grupos sem fechar a transação, para quem precisa de mais escritas junto."""
    conn.execute("DELETE FROM product_groups")  # group_refs sai junto, por cascata
    for name, refs in groups:
        group_id = conn.execute("INSERT INTO product_groups (name) VALUES (?)", (name,)).lastrowid
        conn.executemany(
            "INSERT INTO group_refs (group_id, cnpj_root, product_code) VALUES (?, ?, ?)",
            [(group_id, *split_ref(ref)) for ref in refs],
        )


def list_groups(conn: sqlite3.Connection) -> dict[str, list[str]]:
    groups: dict[str, list[str]] = {}
    for row in conn.execute(GROUPS_QUERY):
        groups.setdefault(row["name"], []).append(row["ref"])
    return groups


def list_notes(conn: sqlite3.Connection, data_dir: Path) -> dict[str, list[dict]]:
    """Notas em que cada produto aparece. O link só existe se a rota de PDF puder entregar."""
    hrefs: dict[str, str | None] = {}
    notes: dict[str, list[dict]] = {}
    for row in conn.execute(NOTES_QUERY):
        key = row["access_key"]
        if key not in hrefs:
            hrefs[key] = f"/notes/{key}.pdf" if resolve_in_data(row["source_path"], data_dir) else None
        notes.setdefault(row["ref"], []).append(
            {
                "date": row["issued_at"][:10],
                "number": row["number"],
                "file": row["source_file"],
                "href": hrefs[key],
                "quantity": row["quantity"],
                "price": row["price"],
            }
        )
    return notes


STORES_QUERY = "SELECT cnpj_root, store, category FROM stores ORDER BY store, cnpj_root"

# Uma linha por raiz presente nas notas; o nome é o da nota mais recente.
UNREGISTERED_QUERY = """
SELECT substr(n.seller_cnpj, 1, 8) AS cnpj_root, n.seller_name AS name, COUNT(*) AS notes, MAX(n.issued_at) AS last
FROM notes n
WHERE substr(n.seller_cnpj, 1, 8) NOT IN (SELECT cnpj_root FROM stores)
GROUP BY substr(n.seller_cnpj, 1, 8)
ORDER BY name
"""

DEFAULT_CATEGORY = "Outros"


class StoreError(ValueError):
    """Cadastro de loja inválido; a mensagem é mostrada ao usuário."""


def list_stores(conn: sqlite3.Connection) -> dict:
    """Lojas cadastradas e raízes de CNPJ das notas que ainda não têm cadastro."""
    return {
        "stores": [dict(row) for row in conn.execute(STORES_QUERY)],
        "unregistered": [dict(row) for row in conn.execute(UNREGISTERED_QUERY)],
    }


def is_registered_store(conn: sqlite3.Connection, cnpj_root: str) -> bool:
    return conn.execute("SELECT 1 FROM stores WHERE cnpj_root = ?", (cnpj_root,)).fetchone() is not None


def save_store(conn: sqlite3.Connection, cnpj_root: str, store, category) -> dict:
    """Cria ou atualiza a loja. Categoria vazia vira "Outros"."""
    if not is_cnpj_root(cnpj_root):
        raise StoreError("a raiz do CNPJ deve ter 8 dígitos")
    if not isinstance(store, str) or not store.strip():
        raise StoreError("o nome da loja não pode ser vazio")
    category = category.strip() if isinstance(category, str) else ""
    row = {"cnpj_root": cnpj_root, "store": store.strip(), "category": category or DEFAULT_CATEGORY}
    with conn:
        conn.execute(
            "INSERT INTO stores (cnpj_root, store, category) VALUES (:cnpj_root, :store, :category) "
            "ON CONFLICT(cnpj_root) DO UPDATE SET store = excluded.store, category = excluded.category",
            row,
        )
    return row


def load_rejected_pairs(conn: sqlite3.Connection) -> set[tuple]:
    return {tuple(row) for row in conn.execute("SELECT * FROM rejected_pairs")}


def list_rejections(rejected: set[tuple]) -> list[list[str]]:
    """Os pares como [ref, ref], em ordem estável."""
    return [[f"{a}:{b}", f"{c}:{d}"] for a, b, c, d in sorted(rejected)]


def build_catalog(conn: sqlite3.Connection, data_dir: Path) -> dict:
    """Os dados da página de agrupamento."""
    rows = load_product_rows(conn)
    rejected = load_rejected_pairs(conn)
    return {
        "products": list_ref_products(rows),
        "suggestions": list_suggestions(rows, rejected),
        "groups": list_groups(conn),
        "notes": list_notes(conn, data_dir),
        "rejections": list_rejections(rejected),
    }


class RejectionError(ValueError):
    """A lista de referências não serve para rejeitar pares."""


def _pairs_between(refs) -> list[tuple]:
    if not isinstance(refs, list) or not all(isinstance(ref, str) for ref in refs):
        raise RejectionError("envie uma lista de referências no formato raiz:código")
    parsed = []
    for ref in refs:
        if not (pair := parse_ref(ref)):
            raise RejectionError(f"{ref!r} não é uma referência raiz:código")
        parsed.append(pair)
    unique = list(dict.fromkeys(parsed))
    if len(unique) < 2:
        raise RejectionError("informe ao menos duas referências diferentes")
    return [canonical_pair(a, b) for a, b in itertools.combinations(unique, 2)]


def reject_pairs(conn: sqlite3.Connection, refs) -> None:
    """Rejeita todos os pares entre as referências."""
    pairs = _pairs_between(refs)
    with conn:
        conn.executemany(
            "INSERT OR IGNORE INTO rejected_pairs (cnpj_root_a, code_a, cnpj_root_b, code_b) VALUES (?, ?, ?, ?)",
            pairs,
        )


def undo_rejected_pairs(conn: sqlite3.Connection, refs) -> None:
    """Desfaz a rejeição de todos os pares entre as referências."""
    pairs = _pairs_between(refs)
    with conn:
        conn.executemany(
            "DELETE FROM rejected_pairs WHERE cnpj_root_a = ? AND code_a = ? AND cnpj_root_b = ? AND code_b = ?",
            pairs,
        )


def find_note_pdf(conn: sqlite3.Connection, data_dir: Path, access_key: str) -> Path | None:
    row = conn.execute("SELECT source_path FROM notes WHERE access_key = ?", (access_key,)).fetchone()
    return resolve_in_data(row["source_path"], data_dir) if row else None


EXPORT_FORMAT_VERSION = 1


class CurationFileError(ValueError):
    """O arquivo de curadoria é inválido ou de um formato desconhecido."""


def export_curation(conn: sqlite3.Connection) -> str:
    """Grupos, pares rejeitados e lojas como JSON de ordem estável, para commitar."""
    groups = {name: sorted(refs) for name, refs in list_groups(conn).items()}
    data = {
        "format_version": EXPORT_FORMAT_VERSION,
        "groups": groups,
        "rejected_pairs": list_rejections(load_rejected_pairs(conn)),
        "stores": {
            row["cnpj_root"]: {"store": row["store"], "category": row["category"]}
            for row in conn.execute(STORES_QUERY)
        },
    }
    return json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _parse_curation(text: str) -> tuple[list, list, list]:
    """Valida o arquivo inteiro e devolve (grupos, pares, lojas) prontos para gravar."""
    try:
        data = json.loads(text)
    except ValueError as error:
        raise CurationFileError(f"não é um JSON válido: {error}") from error
    if not isinstance(data, dict):
        raise CurationFileError("o arquivo deve ser um objeto JSON")
    if data.get("format_version") != EXPORT_FORMAT_VERSION:
        raise CurationFileError(
            f"formato desconhecido: format_version={data.get('format_version')!r}, "
            f"esta versão lê {EXPORT_FORMAT_VERSION}"
        )
    for key in ("groups", "rejected_pairs", "stores"):
        if key not in data:
            raise CurationFileError(f"falta o campo {key!r}")
    if not isinstance(data["groups"], dict):
        raise CurationFileError('"groups" deve ser {"Nome": ["raiz:código", ...]}')
    try:
        groups = validate_groups(list(data["groups"].items()))
    except GroupsError as error:
        raise CurationFileError(f"grupos: {error}") from error

    pairs = []
    if not isinstance(data["rejected_pairs"], list):
        raise CurationFileError('"rejected_pairs" deve ser uma lista de [ref, ref]')
    for pair in data["rejected_pairs"]:
        if not (isinstance(pair, list) and len(pair) == 2):
            raise CurationFileError(f"par rejeitado inválido: {pair!r}")
        try:
            pairs += _pairs_between(pair)
        except RejectionError as error:
            raise CurationFileError(f"par rejeitado inválido {pair!r}: {error}") from error

    if not isinstance(data["stores"], dict):
        raise CurationFileError('"stores" deve ser {"raiz": {"store": ..., "category": ...}}')
    stores = []
    for root, entry in data["stores"].items():
        if not is_cnpj_root(root):
            raise CurationFileError(f"raiz de CNPJ inválida em stores: {root!r}")
        if not isinstance(entry, dict):
            raise CurationFileError(f"a loja {root} deve ser um objeto com store e category")
        store, category = entry.get("store"), entry.get("category")
        if not all(v is None or isinstance(v, str) for v in (store, category)):
            raise CurationFileError(f"nome e categoria da loja {root} devem ser texto")
        stores.append((root, store, category))
    return groups, sorted(set(pairs)), stores


def restore_curation(conn: sqlite3.Connection, text: str) -> None:
    """Troca grupos, pares rejeitados e lojas pelo conteúdo do arquivo, numa transação só.

    O arquivo é validado inteiro antes de tocar no banco. Referências a produtos sem
    nota são aceitas: a curadoria não depende de a nota já estar importada.
    """
    groups, pairs, stores = _parse_curation(text)
    with conn:
        _write_groups(conn, groups)
        conn.execute("DELETE FROM rejected_pairs")
        conn.executemany(
            "INSERT INTO rejected_pairs (cnpj_root_a, code_a, cnpj_root_b, code_b) VALUES (?, ?, ?, ?)",
            pairs,
        )
        conn.execute("DELETE FROM stores")
        conn.executemany("INSERT INTO stores (cnpj_root, store, category) VALUES (?, ?, ?)", stores)
