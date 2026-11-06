#!/usr/bin/env python3
"""Gera chart.html com o histórico de preços de cada produto do banco.

Uso: python3 chart.py [--db ARQUIVO] [--out ARQUIVO]

A página é autossuficiente e funciona offline. Rode de novo depois de importar
notas para atualizar os dados.
"""
import argparse
import json
import sqlite3
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
STORES_FILE = PROJECT_DIR / "stores.json"

# Linhas repetidas de um produto na mesma nota e com o mesmo preço viram uma compra.
QUERY = """
SELECT seller_cnpj, seller_name, product_code, description, unit,
       issued_at, unit_price,
       SUM(quantity) AS quantity,
       SUM(line_total) AS line_total
FROM price_history
GROUP BY seller_cnpj, product_code, unit, access_key, unit_price
ORDER BY issued_at
"""

TEMPLATE = r"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Histórico de preços</title>
<style>
:root {
  color-scheme: light;
  --surface: #fcfcfb;
  --text-primary: #0b0b0b;
  --text-secondary: #52514e;
  --hairline: #e4e3df;
  --series: #2a78d6;
}
@media (prefers-color-scheme: dark) {
  :root {
    color-scheme: dark;
    --surface: #1a1a19;
    --text-primary: #f0efec;
    --text-secondary: #c3c2b7;
    --hairline: #343432;
    --series: #3987e5;
  }
}
* { box-sizing: border-box; }
body {
  margin: 0;
  background: var(--surface);
  color: var(--text-primary);
  font: 16px/1.45 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
}
main { max-width: 880px; margin: 0 auto; padding: 32px 16px 48px; }
h1 { margin: 0 0 20px; font-size: 24px; line-height: 1.2; }
h2 { margin: 0; font-size: 19px; line-height: 1.3; overflow-wrap: anywhere; }
.controls { display: flex; flex-wrap: wrap; gap: 12px; margin-bottom: 28px; }
.controls label { display: grid; gap: 4px; font-size: 13px; color: var(--text-secondary); }
.controls label { flex: 1 1 160px; min-width: 0; }
.controls label:last-child { flex: 2 1 300px; }
input, select {
  width: 100%;
  height: 40px;
  padding: 0 10px;
  border: 1px solid var(--text-secondary);
  border-radius: 6px;
  background: var(--surface);
  color: var(--text-primary);
  font: inherit;
}
.subtitle { margin: 2px 0 20px; color: var(--text-secondary); font-size: 14px; }
.check { display: flex; flex-wrap: wrap; align-items: end; gap: 12px 20px; margin: 0 0 20px; }
.check label { display: grid; gap: 4px; flex: 0 1 200px; font-size: 13px; color: var(--text-secondary); }
.check .average { color: var(--text-secondary); font-size: 14px; }
.check .average strong { display: block; color: var(--text-primary); font-size: 21px; font-variant-numeric: tabular-nums; }
#verdict { flex: 1 1 240px; min-width: 0; font-size: 16px; font-weight: 600; }
#verdict small { display: block; font-weight: 400; font-size: 13px; color: var(--text-secondary); }
#chart { position: relative; height: 320px; touch-action: pan-y; }
#chart svg { display: block; width: 100%; height: 100%; overflow: visible; }
#chart text { fill: var(--text-secondary); font-size: 12px; font-variant-numeric: tabular-nums; }
#chart text.value { fill: var(--text-primary); font-size: 13px; font-weight: 600; }
.point:focus { outline: none; }
.point:focus .dot { stroke: var(--text-primary); }
#tooltip {
  position: absolute;
  top: 0;
  z-index: 1;
  padding: 8px 10px;
  border: 1px solid var(--hairline);
  border-radius: 6px;
  background: var(--surface);
  box-shadow: 0 2px 8px rgb(0 0 0 / 0.16);
  font-size: 13px;
  white-space: nowrap;
  pointer-events: none;
}
#tooltip strong { display: block; font-size: 15px; font-variant-numeric: tabular-nums; }
#tooltip span { display: block; color: var(--text-secondary); }
.table-wrap { margin-top: 28px; overflow-x: auto; }
table { width: 100%; border-collapse: collapse; font-size: 14px; }
th, td { padding: 8px 12px 8px 0; border-bottom: 1px solid var(--hairline); text-align: left; white-space: nowrap; }
th { color: var(--text-secondary); font-weight: 500; }
th:last-child, td:last-child { padding-right: 0; }
.number { text-align: right; font-variant-numeric: tabular-nums; }
.note { margin: 16px 0 0; color: var(--text-secondary); font-size: 13px; }
@media (max-width: 560px) {
  main { padding-top: 20px; }
  #chart { height: 280px; }
  th:nth-child(2), td:nth-child(2) { display: none; }
}
</style>
</head>
<body>
<main>
  <h1>Histórico de preços</h1>
  <div class="controls">
    <label>Categoria <select id="category"></select></label>
    <label>Estabelecimento <select id="store"></select></label>
    <label>Buscar <input id="search" type="search" placeholder="Ex.: tomate" autocomplete="off"></label>
    <label>Produto <select id="product"></select></label>
  </div>
  <section id="details">
    <h2 id="title"></h2>
    <p class="subtitle" id="subtitle"></p>
    <div class="check">
      <div class="average">Média dos preços <strong id="average"></strong></div>
      <label>Preço atual (R$) <input id="current" inputmode="decimal" placeholder="Ex.: 7,99" autocomplete="off"></label>
      <div id="verdict" aria-live="polite"></div>
    </div>
    <div id="chart"><div id="tooltip" hidden><strong></strong><span></span><span></span></div></div>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Data</th><th>Loja</th><th class="number">Preço</th>
            <th class="number">Quantidade</th><th class="number">Total</th>
          </tr>
        </thead>
        <tbody id="rows"></tbody>
      </table>
    </div>
    <p class="note">Preços como impressos na nota. Descontos no total da compra não estão incluídos.</p>
  </section>
  <p id="empty" hidden>Nenhum produto encontrado.</p>
</main>
<script id="data" type="application/json">__DATA__</script>
<script>
const products = JSON.parse(document.getElementById("data").textContent);
const SVG_NS = "http://www.w3.org/2000/svg";
const MARGIN = { top: 28, right: 28, bottom: 28, left: 48 };

const el = (id) => document.getElementById(id);
const search = el("search");
const select = el("product");
const categorySelect = el("category");
const storeSelect = el("store");
const ALL = "";
const chart = el("chart");
const tooltip = el("tooltip");

const moneyFormat = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });
const numberFormat = new Intl.NumberFormat("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const quantityFormat = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 3 });
const percentFormat = new Intl.NumberFormat("pt-BR", {
  style: "percent", maximumFractionDigits: 1, signDisplay: "exceptZero",
});
const dateFormat = new Intl.DateTimeFormat("pt-BR");
const shortDateFormat = new Intl.DateTimeFormat("pt-BR", { day: "2-digit", month: "2-digit", year: "2-digit" });

const normalize = (text) =>
  text.normalize("NFD").replace(/[̀-ͯ]/g, "").toUpperCase();

function svgNode(name, attributes, parent) {
  const node = document.createElementNS(SVG_NS, name);
  for (const [key, value] of Object.entries(attributes)) node.setAttribute(key, value);
  parent.appendChild(node);
  return node;
}

function svgText(parent, attributes, text) {
  svgNode("text", attributes, parent).textContent = text;
}

function niceTicks(maxValue) {
  const rough = maxValue / 4;
  const power = 10 ** Math.floor(Math.log10(rough));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * power).find((s) => s >= rough);
  const ticks = [];
  for (let value = 0; value < maxValue + step; value += step) ticks.push(value);
  return ticks;
}

function fillSelect(node, values, allLabel) {
  const previous = node.value;
  node.replaceChildren(new Option(allLabel, ALL), ...values.map((value) => new Option(value, value)));
  if (values.includes(previous)) node.value = previous;
}

function fillStores() {
  const inCategory = products.filter((p) => !categorySelect.value || p.category === categorySelect.value);
  fillSelect(storeSelect, [...new Set(inCategory.map((p) => p.store))].sort(), "Todos");
}

function fillOptions() {
  const terms = normalize(search.value).split(/\s+/).filter(Boolean);
  const matches = products.filter((product) => {
    if (categorySelect.value && product.category !== categorySelect.value) return false;
    if (storeSelect.value && product.store !== storeSelect.value) return false;
    const haystack = normalize(`${product.description} ${product.code} ${product.seller}`);
    return terms.every((term) => haystack.includes(term));
  });
  const previous = select.value;
  select.replaceChildren(...matches.map((product) => {
    const count = product.purchases.length;
    const label = `${product.description} (${product.code}) · ${count} ${count === 1 ? "compra" : "compras"}`;
    return new Option(label, products.indexOf(product));
  }));
  if ([...select.options].some((option) => option.value === previous)) select.value = previous;
  render();
}

const NEAR_AVERAGE = 0.05;

function averageOf(product) {
  const prices = product.purchases.map((purchase) => purchase.price);
  return prices.reduce((sum, price) => sum + price, 0) / prices.length;
}

function currentPrice() {
  const text = el("current").value.trim().replace(/^R\$\s*/, "").replace(/\./g, "").replace(",", ".");
  const value = Number(text);
  return text && Number.isFinite(value) && value > 0 ? value : null;
}

function renderCheck(product) {
  const average = averageOf(product);
  const current = currentPrice();
  el("average").textContent = moneyFormat.format(average);
  const verdict = el("verdict");
  if (current === null) {
    verdict.textContent = "";
    return;
  }
  const diff = current / average - 1;
  const percent = percentFormat.format(Math.abs(diff));
  const text = Math.abs(diff) <= NEAR_AVERAGE ? "≈ Preço na média"
    : diff < 0 ? "▼ Barato" : "▲ Caro";
  const detail = Math.abs(diff) <= NEAR_AVERAGE
    ? `${percent} ${diff < 0 ? "abaixo" : "acima"} da média`
    : `${percent} ${diff < 0 ? "abaixo" : "acima"} da média de ${moneyFormat.format(average)}`;
  verdict.replaceChildren(text, Object.assign(document.createElement("small"), { textContent: detail }));
}

function renderTable(product) {
  el("rows").replaceChildren(...[...product.purchases].reverse().map((purchase) => {
    const row = document.createElement("tr");
    const cells = [
      [dateFormat.format(purchase.date), ""],
      [product.seller, ""],
      [moneyFormat.format(purchase.price), "number"],
      [`${quantityFormat.format(purchase.quantity)} ${product.unit}`, "number"],
      [moneyFormat.format(purchase.total), "number"],
    ];
    for (const [text, className] of cells) {
      const cell = row.insertCell();
      cell.textContent = text;
      cell.className = className;
    }
    return row;
  }));
}

function labeledIndexes(purchases) {
  const prices = purchases.map((purchase) => purchase.price);
  return new Set([
    prices.indexOf(Math.min(...prices)),
    prices.indexOf(Math.max(...prices)),
    prices.length - 1,
  ]);
}

function showTooltip(product, purchase, x, plot) {
  const [price, date, detail] = tooltip.children;
  price.textContent = `${moneyFormat.format(purchase.price)} / ${product.unit}`;
  date.textContent = dateFormat.format(purchase.date);
  detail.textContent = `${quantityFormat.format(purchase.quantity)} ${product.unit} · ${moneyFormat.format(purchase.total)}`;
  tooltip.hidden = false;
  const left = Math.max(0, Math.min(x + 12, plot.width - tooltip.offsetWidth));
  const flipped = x + 12 + tooltip.offsetWidth > plot.width;
  tooltip.style.left = `${flipped ? Math.max(0, x - tooltip.offsetWidth - 12) : left}px`;
  plot.crosshair.setAttribute("x1", x);
  plot.crosshair.setAttribute("x2", x);
  plot.crosshair.removeAttribute("visibility");
}

function hideTooltip(plot) {
  tooltip.hidden = true;
  plot.crosshair.setAttribute("visibility", "hidden");
}

function renderChart(product) {
  chart.querySelector("svg")?.remove();
  tooltip.hidden = true;
  const width = chart.clientWidth;
  const height = chart.clientHeight;
  const { purchases } = product;
  const svg = document.createElementNS(SVG_NS, "svg");
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
  svg.setAttribute("role", "img");
  svg.setAttribute("aria-label", `Preço de ${product.description} ao longo do tempo`);
  chart.prepend(svg);

  const innerWidth = width - MARGIN.left - MARGIN.right;
  const baseline = height - MARGIN.bottom;
  const times = purchases.map((purchase) => purchase.date.getTime());
  const firstTime = times[0];
  const span = times[times.length - 1] - firstTime;
  const xOf = (time) => MARGIN.left + (span ? ((time - firstTime) / span) * innerWidth : innerWidth / 2);

  const average = averageOf(product);
  const current = currentPrice();
  const ticks = niceTicks(Math.max(...purchases.map((purchase) => purchase.price), current ?? 0));
  const top = ticks[ticks.length - 1];
  const yOf = (price) => baseline - (price / top) * (baseline - MARGIN.top);

  for (const tick of ticks) {
    const y = yOf(tick);
    svgNode("line", {
      x1: MARGIN.left, x2: width - MARGIN.right, y1: y, y2: y,
      stroke: "var(--hairline)", "stroke-width": 1,
    }, svg);
    svgText(svg, { x: MARGIN.left - 8, y: y + 4, "text-anchor": "end" }, numberFormat.format(tick));
  }

  let lastTickX = Infinity;
  for (let index = purchases.length - 1; index >= 0; index -= 1) {
    const x = xOf(times[index]);
    if (lastTickX - x < 72) continue;
    lastTickX = x;
    svgText(svg, { x, y: height - 6, "text-anchor": "middle" }, shortDateFormat.format(purchases[index].date));
  }

  const referenceLine = (price, label, dash, color, above) => {
    const y = yOf(price);
    svgNode("line", {
      x1: MARGIN.left, x2: width - MARGIN.right, y1: y, y2: y,
      stroke: color, "stroke-width": 1.5, "stroke-dasharray": dash,
    }, svg);
    const text = svgNode("text", {
      x: width - MARGIN.right, y: above ? y - 5 : y + 14, "text-anchor": "end",
      style: `fill:${color};font-weight:600`,
    }, svg);
    text.textContent = label;
  };
  referenceLine(average, `Média ${numberFormat.format(average)}`, "6 4", "var(--text-secondary)", current === null || current < average);
  if (current !== null) {
    referenceLine(current, `Atual ${numberFormat.format(current)}`, "2 3", "var(--text-primary)", current >= average);
  }

  const crosshair = svgNode("line", {
    y1: MARGIN.top, y2: baseline, stroke: "var(--text-secondary)", "stroke-width": 1, visibility: "hidden",
  }, svg);
  const plot = { crosshair, width };

  if (purchases.length > 1) {
    svgNode("polyline", {
      points: purchases.map((purchase, index) => `${xOf(times[index])},${yOf(purchase.price)}`).join(" "),
      fill: "none", stroke: "var(--series)", "stroke-width": 2,
      "stroke-linejoin": "round", "stroke-linecap": "round",
    }, svg);
  }

  const labeled = labeledIndexes(purchases);
  purchases.forEach((purchase, index) => {
    const x = xOf(times[index]);
    const y = yOf(purchase.price);
    const point = svgNode("g", { class: "point", tabindex: 0 }, svg);
    svgNode("circle", {
      class: "dot", cx: x, cy: y, r: 5, fill: "var(--series)", stroke: "var(--surface)", "stroke-width": 2,
    }, point);
    if (labeled.has(index)) {
      const anchor = x > width - 60 ? "end" : x < MARGIN.left + 40 ? "start" : "middle";
      svgText(svg, { class: "value", x, y: y - 12, "text-anchor": anchor }, numberFormat.format(purchase.price));
    }
    point.addEventListener("focus", () => showTooltip(product, purchase, x, plot));
    point.addEventListener("blur", () => hideTooltip(plot));
  });

  svg.addEventListener("pointermove", (event) => {
    const pointerX = event.clientX - svg.getBoundingClientRect().left;
    let nearest = 0;
    times.forEach((time, index) => {
      if (Math.abs(xOf(time) - pointerX) < Math.abs(xOf(times[nearest]) - pointerX)) nearest = index;
    });
    showTooltip(product, purchases[nearest], xOf(times[nearest]), plot);
  });
  svg.addEventListener("pointerleave", () => hideTooltip(plot));
}

function render() {
  const product = products[select.value];
  el("details").hidden = !product;
  el("empty").hidden = Boolean(product);
  if (!product) return;
  el("title").textContent = product.description;
  el("subtitle").textContent = `${product.seller} · código ${product.code} · preço por ${product.unit}, em R$`;
  renderCheck(product);
  renderChart(product);
  renderTable(product);
}

for (const product of products) {
  for (const purchase of product.purchases) purchase.date = new Date(purchase.issued_at);
}

search.addEventListener("input", fillOptions);
categorySelect.addEventListener("change", () => { fillStores(); fillOptions(); });
storeSelect.addEventListener("change", fillOptions);
select.addEventListener("change", render);
el("current").addEventListener("input", render);
new ResizeObserver(render).observe(chart);
fillSelect(categorySelect, [...new Set(products.map((p) => p.category))].sort(), "Todas");
fillStores();
fillOptions();
</script>
</body>
</html>
"""


def load_stores(path: Path) -> dict[str, dict]:
    """Mapeia a raiz do CNPJ (8 dígitos, igual em todas as filiais) para loja e categoria."""
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def load_products(db_path: Path, stores: dict[str, dict]) -> list[dict]:
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    products: dict[tuple, dict] = {}
    for row in conn.execute(QUERY):
        key = (row["seller_cnpj"], row["product_code"], row["unit"])
        known = stores.get(row["seller_cnpj"][:8], {})
        product = products.setdefault(
            key,
            {
                "code": row["product_code"],
                "description": row["description"],
                "seller": row["seller_name"],
                "store": known.get("store", row["seller_name"]),
                "category": known.get("category", "Outros"),
                "unit": row["unit"],
                "purchases": [],
            },
        )
        product["purchases"].append(
            {
                "issued_at": row["issued_at"],
                "price": row["unit_price"],
                "quantity": row["quantity"],
                "total": row["line_total"],
            }
        )
    conn.close()
    return sorted(
        products.values(),
        key=lambda product: (-len(product["purchases"]), product["description"]),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Gera o gráfico de histórico de preços.")
    parser.add_argument("--db", type=Path, default=PROJECT_DIR / "pricetrail.sqlite")
    parser.add_argument("--out", type=Path, default=PROJECT_DIR / "chart.html")
    args = parser.parse_args()

    if not args.db.is_file():
        print(f"banco não encontrado: {args.db}. Rode pricetrail.py primeiro.", file=sys.stderr)
        return 2

    products = load_products(args.db, load_stores(STORES_FILE))
    data = json.dumps(products, ensure_ascii=False).replace("</", "<\\/")
    args.out.write_text(TEMPLATE.replace("__DATA__", data), encoding="utf-8")
    print(f"{len(products)} produtos em {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
