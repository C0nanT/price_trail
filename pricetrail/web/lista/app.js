"use strict";
// Lista de compras da semana: itens e preços vêm de /api/shopping-list (média dos últimos 6 meses);
// as marcações ficam no servidor (/api/shopping-list/checked) e a página as relê a cada POLL_MS,
// para refletir o que outro aparelho marcou ou desmarcou.

const POLL_MS = 10000;
const CHECKED_URL = "/api/shopping-list/checked";

let checked = new Set();
let total = 0;

function itemRow(item) {
  const li = document.createElement("li");
  const label = document.createElement("label");
  label.className = "flex min-h-touch cursor-pointer items-center gap-3 border-b border-line py-2";
  const box = document.createElement("input");
  box.type = "checkbox";
  box.className = "h-6 w-6 shrink-0 accent-[var(--accent)]";
  box.checked = checked.has(item.name);
  const text = document.createElement("span");
  text.className = "grid min-w-0 flex-1";
  const name = document.createElement("span");
  name.textContent = item.qty ? `${item.name}, ${item.qty}` : item.name;
  text.append(name);
  if (item.price !== null) {
    const price = document.createElement("span");
    price.className = "text-sm text-muted";
    price.textContent = `${money.format(item.price)}/${item.per}`
      + (item.alt ? `, ou ${item.alt.label}: ${money.format(item.alt.price)}/${item.alt.per}` : "")
      + (item.n === 1 ? " (1 compra)" : ` (média de ${item.n} compras)`);
    text.append(price);
  }
  const paint = () => name.classList.toggle("line-through", box.checked);
  const dim = () => text.classList.toggle("opacity-50", box.checked);
  paint();
  dim();
  box.addEventListener("change", () => {
    if (box.checked) checked.add(item.name);
    else checked.delete(item.name);
    paint();
    dim();
    updateProgress();
    pending += 1;
    fetchJson(CHECKED_URL, { method: "PUT", body: { name: item.name, checked: box.checked } })
      .catch((error) => showError("a marcação", error))
      .finally(() => { pending -= 1; });
  });
  label.append(box, text);
  li.append(label);
  return li;
}

function render(sections) {
  const root = el("sections");
  root.replaceChildren();
  for (const section of sections) {
    const block = document.createElement("section");
    const heading = document.createElement("h2");
    heading.className = "mb-1 text-lg font-bold";
    heading.textContent = section.title;
    const list = document.createElement("ul");
    for (const item of section.items) list.append(itemRow(item));
    block.append(heading, list);
    root.append(block);
  }
  updateProgress();
}

function updateProgress() {
  el("progress").textContent = `${checked.size} de ${total} no carrinho`;
}

let current = [];
let names = new Set();
let pending = 0; // marcações enviadas e ainda sem resposta: a leitura periódica espera por elas

function applyChecked(list) {
  const next = new Set(list.filter((name) => names.has(name)));
  if (next.size === checked.size && [...next].every((name) => checked.has(name))) return;
  checked = next;
  render(current);
}

let secondsLeft = POLL_MS / 1000;

function showCountdown() {
  el("countdown").textContent = `(${secondsLeft}s)`;
}

async function refreshChecked({ manual = false } = {}) {
  secondsLeft = POLL_MS / 1000;
  showCountdown();
  if (!manual && (pending > 0 || document.hidden)) return;
  try {
    const data = await fetchJson(CHECKED_URL);
    if (pending === 0) applyChecked(data.checked);
    if (manual) el("error").hidden = true;
  } catch (error) {
    // No ciclo automático, sem rede agora: tenta de novo no próximo. No botão, avisa.
    if (manual) showError("as marcações", error);
  }
}

el("refresh").addEventListener("click", () => refreshChecked({ manual: true }));

el("reset").addEventListener("click", () => {
  if (checked.size === 0 || !confirm("Desmarcar todos os itens?")) return;
  checked.clear();
  render(current);
  fetchJson(CHECKED_URL, { method: "DELETE" }).catch((error) => showError("a lista", error));
});

Promise.all([fetchJson("/api/shopping-list"), fetchJson(CHECKED_URL)]).then(([data, saved]) => {
  current = data.sections;
  names = new Set(current.flatMap((section) => section.items.map((item) => item.name)));
  total = names.size;
  checked = new Set(saved.checked.filter((name) => names.has(name)));
  el("since").textContent = dateFormat.format(new Date(`${data.since}T00:00:00`));
  render(current);
  showCountdown();
  setInterval(() => {
    secondsLeft -= 1;
    if (secondsLeft <= 0) refreshChecked();
    else showCountdown();
  }, 1000);
  document.addEventListener("visibilitychange", () => refreshChecked());
}, (error) => showError("a lista", error));
