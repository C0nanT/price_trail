"""Agrupamento manual de produtos (products.json) e sugestões de grupos.

products.json mapeia um nome canônico para uma lista de referências:
  - "75315333:1595"       código de produto de uma loja (8 primeiros dígitos do CNPJ)
  - "DET.LIQ.YPE"         descrição exata (sem acento/pontuação/caixa), qualquer loja e código
Nada é agrupado sem estar listado ali.
"""
import difflib
import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path

CODE_REF_RE = re.compile(r"^(\d{8}):(\S+)$")
SIMILAR_RATIO = 0.88


class ProductsError(Exception):
    """products.json inválido."""


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFD", text).upper()
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return " ".join(re.sub(r"[^A-Z0-9]+", " ", text).split())


class Resolver:
    def __init__(self, groups: dict[str, list[str]]):
        self.by_code: dict[tuple[str, str], str] = {}
        self.by_description: dict[str, str] = {}
        for name, refs in groups.items():
            for ref in refs:
                match = CODE_REF_RE.match(ref)
                if match:
                    table, key = self.by_code, (match[1], match[2])
                else:
                    table, key = self.by_description, normalize(ref)
                    if not key:
                        raise ProductsError(f"referência vazia no grupo {name!r}")
                if key in table and table[key] != name:
                    raise ProductsError(f"{ref!r} está em dois grupos: {table[key]!r} e {name!r}")
                table[key] = name

    def resolve(self, cnpj: str, code: str, description: str) -> str | None:
        """Nome canônico do grupo do produto, ou None se ele não foi agrupado."""
        return self.by_code.get((cnpj[:8], code)) or self.by_description.get(normalize(description))


def load_groups(path: Path) -> dict[str, list[str]]:
    """Lê products.json; ausente = sem grupos. Arquivo quebrado levanta ProductsError."""
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as error:
        raise ProductsError(f"{path.name} não é um JSON válido: {error}") from error
    if not isinstance(data, dict) or not all(
        isinstance(refs, list) and all(isinstance(r, str) for r in refs) for refs in data.values()
    ):
        raise ProductsError(f'{path.name} deve ser {{"Nome": ["referência", ...]}}')
    return data


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
                if difflib.SequenceMatcher(None, a, b).ratio() > SIMILAR_RATIO:
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
    return {
        "reason": reason,
        "name": first["description"],
        "refs": [f"{store}:{member['code']}" for member in sorted(members, key=lambda m: m["code"])],
        "members": members,
        "warnings": warnings,
    }


def drop_rejected(suggestions: list[dict], rejected: set[str]) -> list[dict]:
    """Tira das sugestões as referências marcadas como "não juntar".

    Sugestão que ficar com menos de 2 produtos some; duplicadas (mesmas
    referências, ex.: "mesma descrição" e "parecidas") são unificadas.
    """
    result, seen = [], set()
    for suggestion in suggestions:
        refs = [ref for ref in suggestion["refs"] if ref not in rejected]
        key = tuple(refs)
        if len(refs) < 2 or key in seen:
            continue
        seen.add(key)
        keep = {ref.split(":", 1)[1] for ref in refs}
        members = [m for m in suggestion["members"] if m["code"] in keep]
        result.append({**suggestion, "refs": refs, "members": members, "warnings": _warnings(members)})
    return result


def load_rejected(path: Path) -> set[str]:
    """Referências de products.rejected.json (mesmo formato do products.json)."""
    return {ref for refs in load_groups(path).values() for ref in refs}
