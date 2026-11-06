"use strict";
const PRICE_RATIO_WARN = 1.5;

const el = (id) => document.getElementById(id);
const money = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });
const normalize = (t) => t.normalize("NFD").replace(/[̀-ͯ]/g, "").toUpperCase();

// Dados de GET /api/catalog; applyCatalog os troca de uma vez.
let products = [];
let suggestions = [];
let notes = {};
let byRef = new Map();

let groups = {}; // nome -> [referências]
let selected = new Set();
let nameTouched = false;
let dirty = false; // há edição que o servidor ainda não confirmou

// ---- gravação no banco ----
let saving = Promise.resolve();

// Cada edição manda o mapa inteiro; as gravações vão em fila para não se atropelarem.
function persist() {
  dirty = true;
  renderStatus();
  saving = saving.then(saveGroups);
  return saving;
}

async function saveGroups() {
  if (!dirty) return;
  const sent = JSON.stringify(groups);
  try {
    const response = await fetch("/api/groups", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: sent,
    });
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      throw new Error(body.error || `a API respondeu ${response.status}`);
    }
    if (JSON.stringify(groups) === sent) dirty = false;
    el("save-error").hidden = true;
  } catch (error) {
    el("save-error").textContent = `Não foi possível salvar (${error.message}). A edição continua na tela; corrija e tente de novo.`;
    el("save-error").hidden = false;
  }
  renderStatus();
}

// ---- helpers ----
function make(tag, props = {}, ...children) {
  const node = Object.assign(document.createElement(tag), props);
  node.append(...children);
  return node;
}

const groupOf = () => {
  const map = new Map();
  for (const [name, refs] of Object.entries(groups)) for (const ref of refs) map.set(ref, name);
  return map;
};

const priceText = (p) => (p.min === p.max ? money.format(p.min) : `${money.format(p.min)} – ${money.format(p.max)}`);
const metaText = (p) =>
  `${p.store} · cód. ${p.code} · ${p.unit} · ${p.purchases} ${p.purchases === 1 ? "compra" : "compras"} · ${priceText(p)}`;

const dateFormat = new Intl.DateTimeFormat("pt-BR");
const qtyFormat = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 3 });

// "Notas (N)": abre a lista de notas onde o produto aparece, cada uma com link para o PDF.
function notesBlock(ref) {
  const list = notes[ref] || [];
  if (!list.length) return make("span");
  const items = list.map((n) => {
    const label = `${dateFormat.format(new Date(`${n.date}T00:00:00`))} · nota ${n.number} · ${qtyFormat.format(n.quantity)} × ${money.format(n.price)}`;
    const body = n.href
      ? make("a", { href: n.href, target: "_blank", rel: "noopener", textContent: `${label} — abrir PDF` })
      : make("span", { textContent: `${label} — PDF ${n.file} não encontrado em data/` });
    return make("li", {}, body);
  });
  return make("details", { className: "notes" },
    make("summary", { textContent: `Ver nota (${list.length})` }), make("ul", {}, ...items));
}

function flash(text) {
  el("status").textContent = text;
  setTimeout(() => { if (el("status").textContent === text) renderStatus(); }, 2500);
}

function renderStatus() {
  el("status").textContent = dirty ? "Alterações ainda não salvas" : "";
}

// ---- lista de produtos ----
function fillStores() {
  const stores = [...new Set(products.map((p) => p.store))].sort();
  el("store").replaceChildren(new Option("Todas", ""), ...stores.map((s) => new Option(s, s)));
}

function renderProducts() {
  const taken = groupOf();
  const terms = normalize(el("search").value).split(/\s+/).filter(Boolean);
  const store = el("store").value;
  const onlyFree = el("ungrouped").checked;
  const shown = products.filter((p) => {
    if (store && p.store !== store) return false;
    if (onlyFree && taken.has(p.ref) && !selected.has(p.ref)) return false;
    const hay = normalize(`${p.description} ${p.code} ${p.store}`);
    return terms.every((t) => hay.includes(t));
  }).sort((a, b) => a.description.localeCompare(b.description, "pt-BR") || a.code.localeCompare(b.code));
  el("count").textContent = `${shown.length} de ${products.length}`;

  el("products").replaceChildren(...shown.map((p) => {
    const box = make("input", { type: "checkbox", checked: selected.has(p.ref), disabled: taken.has(p.ref) });
    box.addEventListener("change", () => toggle(p.ref, box.checked));
    const meta = make("div", { className: "meta", textContent: metaText(p) });
    if (taken.has(p.ref)) meta.append(" ", make("span", { className: "tag", textContent: `em: ${taken.get(p.ref)}` }));
    const label = make("label", { className: "item" },
      box, make("div", { className: "body" }, make("div", { className: "title", textContent: p.description }), meta));
    return make("li", { className: "entry" + (selected.has(p.ref) ? " selected" : "") }, label, notesBlock(p.ref));
  }));
}

function toggle(ref, on) {
  if (on) selected.add(ref); else selected.delete(ref);
  renderDraft();
  renderProducts();
}

// ---- rascunho do novo grupo ----
function draftWarnings(items) {
  const warnings = [];
  if (new Set(items.map((p) => p.unit)).size > 1) {
    warnings.push("Unidades diferentes: o gráfico não junta produtos com unidades diferentes.");
  }
  const prices = items.flatMap((p) => [p.min, p.max]);
  if (prices.length && Math.max(...prices) / Math.min(...prices) > PRICE_RATIO_WARN) {
    warnings.push(`Preços muito diferentes (${money.format(Math.min(...prices))} a ${money.format(Math.max(...prices))}): pode ser tamanho ou sabor distinto.`);
  }
  return warnings;
}

function renderDraft() {
  const items = [...selected].map((ref) => byRef.get(ref)).filter(Boolean);
  el("draft-hint").hidden = items.length > 0;
  el("draft").replaceChildren(...items.map((p) => {
    const remove = make("button", { className: "link", type: "button", textContent: "tirar" });
    remove.addEventListener("click", () => toggle(p.ref, false));
    return make("li", { className: "entry" },
      make("div", { className: "item" },
        make("div", { className: "body" }, make("div", { className: "title", textContent: p.description }),
          make("div", { className: "meta", textContent: metaText(p) })), remove),
      notesBlock(p.ref));
  }));
  const warnings = draftWarnings(items);
  el("draft-warn").hidden = warnings.length === 0;
  el("draft-warn").textContent = warnings.join(" ");
  if (!nameTouched) el("name").value = items.length ? items[0].description : "";
  el("create").disabled = items.length < 2 || !el("name").value.trim();
}

function createGroup() {
  const name = el("name").value.trim();
  const refs = [...selected];
  if (!name || refs.length < 2) return;
  const existing = groups[name] || [];
  groups[name] = [...existing, ...refs.filter((r) => !existing.includes(r))];
  selected = new Set();
  nameTouched = false;
  persist();
  flash(existing.length ? `Produtos adicionados a “${name}”` : `Grupo “${name}” criado`);
  renderAll();
}

// ---- sugestões ----
function renderSuggestions() {
  const taken = groupOf();
  const open = suggestions.filter((s) => s.refs.some((r) => !taken.has(r)) && s.refs.filter((r) => !taken.has(r)).length > 1);
  el("sug-count").textContent = `${open.length}`;
  el("suggestions").replaceChildren(...open.map((s) => {
    const free = s.refs.filter((r) => !taken.has(r));
    const pick = make("button", { type: "button", textContent: "Selecionar" });
    pick.addEventListener("click", () => {
      selected = new Set(free);
      nameTouched = false;
      renderDraft();
      renderProducts();
      el("name").focus();
    });
    const head = make("div", { className: "head" }, make("strong", { textContent: s.name }), pick);
    const meta = make("div", { className: "meta" }, `${free.length} produtos · ${s.reason} · cód. ${free.map((r) => r.split(":")[1]).join(", ")} `);
    for (const w of s.warnings) meta.append(make("span", { className: "tag warn-tag", textContent: w }), " ");
    return make("li", { className: "sug" }, head, meta);
  }));
}

// ---- grupos existentes ----
function renameGroup(oldName, input) {
  const name = input.value.trim();
  if (!name || name === oldName) { input.value = oldName; return; }
  if (groups[name]) { flash(`Já existe um grupo “${name}”`); input.value = oldName; return; }
  const renamed = {};
  for (const [key, refs] of Object.entries(groups)) renamed[key === oldName ? name : key] = refs;
  groups = renamed;
  persist();
  renderAll();
}

function renderGroups() {
  const names = Object.keys(groups);
  el("group-count").textContent = `${names.length}`;
  el("groups").replaceChildren(...names.map((name) => {
    const nameInput = make("input", { value: name, "aria-label": "Nome do grupo" });
    nameInput.addEventListener("change", () => renameGroup(name, nameInput));
    const del = make("button", { type: "button", textContent: "Excluir grupo" });
    del.addEventListener("click", () => {
      if (!confirm(`Excluir o grupo “${name}”? Os produtos voltam a aparecer separados.`)) return;
      delete groups[name];
      persist();
      renderAll();
    });
    const members = groups[name].map((ref) => {
      const p = byRef.get(ref);
      const remove = make("button", { className: "link", type: "button", textContent: "tirar" });
      remove.addEventListener("click", () => {
        groups[name] = groups[name].filter((r) => r !== ref);
        if (!groups[name].length) delete groups[name];
        persist();
        renderAll();
      });
      const text = p ? `${p.description} · cód. ${p.code} · ${p.unit} · ${priceText(p)}` : `${ref} (descrição exata, fora do banco atual)`;
      return make("li", {}, make("div", { className: "mrow" }, make("span", { textContent: text }), remove), notesBlock(ref));
    });
    return make("li", { className: "group" }, make("header", {}, nameInput, del), make("ul", {}, ...members));
  }));
}

window.addEventListener("beforeunload", (event) => {
  if (dirty) event.preventDefault();
});

// ---- carga ----
async function loadCatalog() {
  if (window.DATA) return window.DATA; // página gerada pelo group_page.py, até ele sair
  const response = await fetch("/api/catalog");
  if (!response.ok) throw new Error(`a API respondeu ${response.status}`);
  return response.json();
}

function showError(error) {
  el("error").textContent = `Não foi possível carregar os produtos (${error.message}). `
    + "Confira se o servidor está rodando e recarregue a página.";
  el("error").hidden = false;
}

function applyCatalog(data) {
  ({ products, suggestions, notes } = data);
  byRef = new Map(products.map((p) => [p.ref, p]));
  groups = structuredClone(data.groups);
}

// ---- ligação ----
function renderAll() {
  renderStatus();
  renderProducts();
  renderDraft();
  renderSuggestions();
  renderGroups();
}

el("search").addEventListener("input", renderProducts);
el("store").addEventListener("change", renderProducts);
el("ungrouped").addEventListener("change", renderProducts);
el("name").addEventListener("input", () => { nameTouched = true; renderDraft(); });
el("create").addEventListener("click", createGroup);
el("clear").addEventListener("click", () => { selected = new Set(); nameTouched = false; renderDraft(); renderProducts(); });

async function start() {
  try {
    applyCatalog(await loadCatalog());
  } catch (error) {
    showError(error);
    return;
  }
  fillStores();
  renderAll();
}

start();
