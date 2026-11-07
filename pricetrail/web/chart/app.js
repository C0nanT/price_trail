let products = [];
const SVG_NS = "http://www.w3.org/2000/svg";
const MARGIN = { top: 28, right: 28, bottom: 28, left: 48 };

// el, money, dateFormat, normalize, fetchJson e showError vêm de /static/common.js.
const search = el("search");
const select = el("product");
const categorySelect = el("category");
const storeSelect = el("store");
const fromInput = el("from");
const toInput = el("to");
const sortSelect = el("sort");
const ALL = "";
const chart = el("chart");
const tooltip = el("tooltip");

const numberFormat = new Intl.NumberFormat("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const quantityFormat = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 3 });
const percentFormat = new Intl.NumberFormat("pt-BR", {
  style: "percent", maximumFractionDigits: 1, signDisplay: "exceptZero",
});
const shortDateFormat = new Intl.DateTimeFormat("pt-BR", { day: "2-digit", month: "2-digit", year: "2-digit" });

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
  const inCategory = products.filter((p) => !categorySelect.value || p.categories.includes(categorySelect.value));
  fillSelect(storeSelect, [...new Set(inCategory.flatMap((p) => p.stores))].sort(), "Todos");
}

function dateBound(input, endOfDay) {
  if (!input.value) return null;
  const date = new Date(`${input.value}T${endOfDay ? "23:59:59.999" : "00:00:00"}`);
  return Number.isNaN(date.getTime()) ? null : date;
}

// O intervalo de datas escolhido; calculado uma vez por filtragem, não por produto.
function dateRange() {
  return { from: dateBound(fromInput, false), to: dateBound(toInput, true) };
}

// Compras do produto dentro do intervalo de datas.
function purchasesIn(product, { from, to }) {
  return product.purchases.filter((p) => (!from || p.date >= from) && (!to || p.date <= to));
}

// Variação do último preço contra o anterior; null com menos de duas compras.
function variationOf(purchases) {
  if (purchases.length < 2) return null;
  const last = purchases[purchases.length - 1];
  const previous = purchases[purchases.length - 2];
  return { change: last.price / previous.price - 1, previous };
}

function sortMatches(entries) {
  const mode = sortSelect.value;
  if (mode === "name") {
    entries.sort((a, b) => a.product.description.localeCompare(b.product.description, "pt-BR"));
  } else if (mode === "rise" || mode === "drop") {
    const sign = mode === "rise" ? -1 : 1;
    // Produtos com uma só compra (sem variação) vão para o fim.
    entries.sort((a, b) => {
      if (a.variation === null || b.variation === null) {
        return (a.variation === null) - (b.variation === null);
      }
      return sign * (a.variation.change - b.variation.change);
    });
  }
  // "purchases": mantém a ordem vinda da API (mais compras primeiro).
  return entries;
}

function fillOptions() {
  const terms = normalize(search.value).split(/\s+/).filter(Boolean);
  const range = dateRange();
  const entries = [];
  products.forEach((product, index) => {
    if (categorySelect.value && !product.categories.includes(categorySelect.value)) return;
    if (storeSelect.value && !product.stores.includes(storeSelect.value)) return;
    if (!terms.every((term) => product.haystack.includes(term))) return;
    const purchases = purchasesIn(product, range);
    if (!purchases.length) return;
    entries.push({ product, index, count: purchases.length, variation: variationOf(purchases) });
  });
  const previous = select.value;
  select.replaceChildren(...sortMatches(entries).map(({ product, index, count }) => {
    const label = `${product.description} (${product.code.length > 24 ? product.code.slice(0, 21) + "…" : product.code}) · ${count} ${count === 1 ? "compra" : "compras"}`;
    return new Option(label, index);
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
  el("average").textContent = money.format(average);
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
    : `${percent} ${diff < 0 ? "abaixo" : "acima"} da média de ${money.format(average)}`;
  verdict.replaceChildren(text, Object.assign(document.createElement("small"), { textContent: detail }));
}

function renderTable(product) {
  el("rows").replaceChildren(...[...product.purchases].reverse().map((purchase) => {
    const row = document.createElement("tr");
    const cells = [
      [dateFormat.format(purchase.date), ""],
      [purchase.seller, ""],
      [money.format(purchase.price), "number"],
      [`${quantityFormat.format(purchase.quantity)} ${product.unit}`, "number"],
      [money.format(purchase.total), "number"],
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
  price.textContent = `${money.format(purchase.price)} / ${product.unit}`;
  date.textContent = dateFormat.format(purchase.date);
  detail.textContent = `${quantityFormat.format(purchase.quantity)} ${product.unit} · ${money.format(purchase.total)}`;
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

function renderVariation(purchases) {
  const node = el("variation");
  const variation = variationOf(purchases);
  node.className = "variation";
  if (!variation) {
    node.textContent = "";
    return;
  }
  const { change, previous } = variation;
  const kind = Math.abs(change) < 0.0005 ? "flat" : change > 0 ? "up" : "down";
  const arrow = { up: "▲", down: "▼", flat: "＝" }[kind];
  const text = kind === "flat" ? "Preço igual" : percentFormat.format(change);
  node.classList.add(kind);
  node.replaceChildren(
    `${arrow} ${text} `,
    Object.assign(document.createElement("small"), {
      textContent: `vs compra anterior (${money.format(previous.price)} em ${dateFormat.format(previous.date)})`,
    }),
  );
}

function render() {
  const original = products[select.value];
  el("details").hidden = !original;
  el("empty").hidden = Boolean(original);
  if (!original) return;
  // Todo o resto da página enxerga só as compras dentro do intervalo de datas.
  const product = { ...original, purchases: purchasesIn(original, dateRange()) };
  renderVariation(product.purchases);
  el("title").textContent = product.description;
  el("subtitle").textContent = `${product.seller} · código ${product.code} · preço por ${product.unit}, em R$`;
  renderCheck(product);
  renderChart(product);
  renderTable(product);
}

async function start() {
  try {
    products = await fetchJson("/api/products");
  } catch (error) {
    showError("os preços", error);
    return;
  }
  for (const product of products) {
    for (const purchase of product.purchases) purchase.date = new Date(purchase.issued_at);
    // Texto da busca, normalizado uma vez só e não a cada tecla.
    product.haystack = normalize(`${product.description} ${product.code} ${product.seller}`);
  }

  search.addEventListener("input", fillOptions);
  categorySelect.addEventListener("change", () => { fillStores(); fillOptions(); });
  storeSelect.addEventListener("change", fillOptions);
  for (const input of [fromInput, toInput, sortSelect]) input.addEventListener("change", fillOptions);
  select.addEventListener("change", render);
  el("current").addEventListener("input", render);
  new ResizeObserver(render).observe(chart);
  fillSelect(categorySelect, [...new Set(products.flatMap((p) => p.categories))].sort(), "Todas");
  fillStores();
  fillOptions();
}

start();
