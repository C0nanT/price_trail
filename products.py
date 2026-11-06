"""Agrupamento manual de produtos (products.json) e sugestões de grupos.

products.json mapeia um nome canônico para uma lista de referências:
  - "75315333:1595"       código de produto de uma loja (8 primeiros dígitos do CNPJ)
  - "DET.LIQ.YPE"         descrição exata (sem acento/pontuação/caixa), qualquer loja e código
Nada é agrupado sem estar listado ali.
"""
import json
import re
from pathlib import Path

from pricetrail.catalog import drop_rejected, normalize, suggest_groups  # noqa: F401

CODE_REF_RE = re.compile(r"^(\d{8}):(\S+)$")


class ProductsError(Exception):
    """products.json inválido."""


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


def load_rejected(path: Path) -> set[str]:
    """Referências de products.rejected.json (mesmo formato do products.json)."""
    return {ref for refs in load_groups(path).values() for ref in refs}
