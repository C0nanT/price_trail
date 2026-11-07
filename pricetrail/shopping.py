"""Lista de compras da semana: itens fixos, preço = média das notas dos últimos 6 meses."""
import sqlite3
from datetime import date

WINDOW_MONTHS = 6
# Nome da unidade impressa na nota -> como a página mostra o preço.
PER_LABEL = {"KG": "kg", "UND": "und", "MCO": "maço", "PCT": "pacote", "BDJ": "bandeja"}


def item(name, description=None, qty=None, per=None, alt=None):
    """description: texto exato do item nas notas; sem ele, o item não tem preço.

    per: força o rótulo do preço (ex.: ovo vem como UND, mas é cartela).
    alt: (rótulo, description) de uma variação que aparece como observação.
    """
    return {"name": name, "description": description, "qty": qty, "per": per, "alt": alt}


SECTIONS = (
    ("Hortifruti", (
        item("Batata lavada", "BATATA LAVADA"),
        item("Cebola", "CEBOLA ATACADAO"),
        item("Tomate salada", "TOMATE SALADA"),
        item("Cenoura", "CENOURA"),
        item("Brócolis japonês", "BROCOLIS JAPONES"),
        item("Banana caturra", "BANANA CATURRA"),
    )),
    ("Laticínios e frios", (
        item("Creme de leite Piracanjuba", "CR.LEITE PIRACANJUBA", qty="3 und"),
        item("Leite longa vida Aurora", "LEITE L. VIDA AURORA", qty="2 und"),
        item("Leite condensado Tirol", "L.COND.TIROL SEMI.TP", qty="2 und"),
        item("Queijo muçarela President fatiado", "QJO MUSS PRESIDENT F", qty="1 und"),
        item("Requeijão cremoso Tradição", "REQ.CREMOSO TRAD.", qty="1 und"),
        item("Bebida láctea Pirakids", "BEB.LACTEA PIRAKIDS", qty="2 und"),
    )),
    ("Carnes", (
        item("Filé de peito Sadia", "FILE PEITO SADIA"),
        item("Filezinho sassami Copacol", "FILE SASSAMI COPACOL"),
        item("Carne moída acém", "BOV.ACEM MOIDO RE.BJ", alt=("paleta", "BOV.PALETA MOIDA RES")),
    )),
    ("Mercearia", (
        item("Arroz Camil", "ARROZ CAMIL AG.T1"),
        item("Ovos", "OVO GD BR PVC NIENOW", per="cartela"),
        item("Pão de sanduíche Thabrew", "PAO SANDUICHE THABR."),
        item("Farinha de trigo", "FARINHA TRIGO FARINA", qty="1 und"),
        item("Molho de tomate Quero", "MOLHO QUERO TRAD", qty="4 und"),
        item("Mistura para bolo Dr. Oetker", "MIST.BOLO C.DR.OETK.", qty="2 und"),
        item("Pudim Apti", "PUDIM APTI", qty="1 und"),
    )),
    ("Limpeza e higiene", (
        item("Detergente Limpol", "DET.LIQ.LIMPOL", qty="2 und"),
        item("Sabonete Johnsons", "SAB.JOHNSONS", qty="3 und"),
        item("Saco de lixo", "GUARD.RESID.21X22", qty="1 und"),
    )),
    ("Confira em casa antes", tuple(
        item(name) for name in (
            "Amaciante Downy", "Água sanitária", "Papel higiênico", "Café Melitta", "Azeite", "Guardanapo",
        )
    )),
)


def today() -> date:
    return date.today()


def months_ago(today: date, months: int) -> date:
    """Mesmo dia, `months` meses antes; no fim do mês, o último dia que existir."""
    index = today.year * 12 + today.month - 1 - months
    year, month = divmod(index, 12)
    month += 1
    for day in range(today.day, 27, -1):
        try:
            return date(year, month, day)
        except ValueError:
            continue
    return date(year, month, min(today.day, 28))


def average_price(conn: sqlite3.Connection, description: str, since: date) -> dict | None:
    """Média do preço impresso nas notas desde `since`; None quando não houve compra."""
    row = conn.execute(
        "SELECT AVG(unit_price) AS price, COUNT(*) AS n, MAX(unit) AS unit"
        " FROM price_history WHERE description = ? AND purchase_date >= ?",
        (description, since.isoformat()),
    ).fetchone()
    if not row["n"]:
        return None
    return {"price": round(row["price"], 2), "n": row["n"], "per": PER_LABEL.get(row["unit"], row["unit"].lower())}


def build_list(conn: sqlite3.Connection) -> dict:
    since = months_ago(today(), WINDOW_MONTHS)
    sections = []
    for title, items in SECTIONS:
        rows = []
        for spec in items:
            row = {"name": spec["name"], "qty": spec["qty"], "price": None, "per": None, "n": 0, "alt": None}
            found = average_price(conn, spec["description"], since) if spec["description"] else None
            if found:
                row.update(price=found["price"], per=spec["per"] or found["per"], n=found["n"])
            if spec["alt"]:
                alt = average_price(conn, spec["alt"][1], since)
                if alt:
                    row["alt"] = {"label": spec["alt"][0], "price": alt["price"], "per": alt["per"]}
            rows.append(row)
        sections.append({"title": title, "items": rows})
    return {"since": since.isoformat(), "sections": sections}
