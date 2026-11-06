"""Gera texto de NFC-e sintético (como o pdftotext -layout devolve) com chave válida."""
from pricetrail.nfce import access_key_is_valid

CNPJ = "75315333029000"


def make_key(cnpj: str = CNPJ, number: int = 45170) -> str:
    body = f"42" + "2610" + cnpj + "65" + "528" + f"{number:09d}" + "1" + "12345678"
    weights = [2, 3, 4, 5, 6, 7, 8, 9]
    total = sum(int(d) * weights[i % 8] for i, d in enumerate(reversed(body)))
    remainder = total % 11
    key = body + str(0 if remainder < 2 else 11 - remainder)
    assert access_key_is_valid(key)
    return key


def spaced(key: str) -> str:
    return " ".join(key[i : i + 4] for i in range(0, 44, 4))


def mercado_item(desc, code, qty, unit, price, total):
    return (
        f"{desc} (Código: {code} )      Vl. Total\n"
        f"Qtde.:{qty}  UN: {unit}Vl. Unit.: {price}      {total}\n"
    )


def farmacia_item(desc, code, total, qty, unit, price):
    return (
        f"{desc} (Código: {code} ) {total}\n"
        f"Qtde.:{qty} UN: {unit} Vl. Unit.: {price}\n"
    )


MERCADO_ITEMS = [
    ("CAFE MELITTA PET", "10759", "1", "UND9", "29,9", "29,90"),
    ("BATATA LAVADA", "14691", "1,25", "KG9", "4,89", "6,11"),
    ("CR.LEITE PIRACANJUBA", "23290", "2", "UND9", "2,49", "4,98"),
]


def make_text(
    items=None,
    *,
    farmacia=False,
    total="40,99",
    discount="1,00",
    paid="39,99",
    count=None,
    key=None,
    number=45170,
    cnpj_text="75.315.333/0290-00",
    omit_total=False,
    between_items="",
    issued="02/10/2026",
):
    key = key or make_key(number=number)
    items = items if items is not None else MERCADO_ITEMS
    build = farmacia_item if farmacia else mercado_item
    body = ""
    for n, item in enumerate(items):
        body += build(*item)
        if n == 0:
            body += between_items
    totals = f"Qtd. total de itens:   {len(items) if count is None else count}\n"
    if not omit_total:
        totals += f"Valor total R$:   {total}\n"
    if discount:
        totals += f"Descontos R$:   {discount}\n"
    totals += f"Valor a pagar R$:\n   {paid}\n"
    return (
        "   ATACADAO S.A.\n"
        f"   CNPJ: {cnpj_text}\n"
        "   JUSCELINO KUBITSCHECK DE OLIVE , 469 , , ESTREITO ,\n"
        "   FLORIANOPOLIS , SC\n\n"
        f"{body}\n{totals}\n"
        f"Número: {number} Série: 528 Emissão: {issued} 19:53:38 - Via Consumidor 2\n"
        f"Chave de acesso:\n{spaced(key)}\n"
    )
