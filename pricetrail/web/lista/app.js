"use strict";
// Lista de compras da semana: itens e preços vêm de /api/shopping-list (média dos últimos 6 meses);
// as marcações ficam no localStorage do aparelho.

const STORAGE_KEY = "pricetrail:lista:marcados";

// O localStorage pode falhar (aba privada, dados bloqueados): a lista segue funcionando, sem salvar.
function loadChecked(names) {
  try {
    const saved = JSON.parse(localStorage.getItem(STORAGE_KEY));
    if (Array.isArray(saved)) return new Set(saved.filter((name) => names.has(name)));
  } catch { /* usa a lista vazia */ }
  return new Set();
}

function saveChecked() {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify([...checked]));
  } catch { /* sem armazenamento: só não persiste */ }
}

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
    saveChecked();
    updateProgress();
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

el("reset").addEventListener("click", () => {
  if (checked.size === 0 || !confirm("Desmarcar todos os itens?")) return;
  checked.clear();
  saveChecked();
  render(current);
});

fetchJson("/api/shopping-list").then((data) => {
  current = data.sections;
  const names = new Set(current.flatMap((section) => section.items.map((item) => item.name)));
  total = names.size;
  checked = loadChecked(names);
  el("since").textContent = dateFormat.format(new Date(`${data.since}T00:00:00`));
  render(current);
}, (error) => showError("a lista", error));
