"use strict";
const STORAGE_KEY = "pricetrail-groups";
const PRICE_RATIO_WARN = 1.5;

const el = (id) => document.getElementById(id);
const money = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });
const normalize = (t) => t.normalize("NFD").replace(/[̀-ͯ]/g, "").toUpperCase();

// Dados de GET /api/catalog; applyCatalog os troca de uma vez.
let products = [];
let suggestions = [];
let notes = {};
let rejections = []; // pares [ref, ref] marcados como "não juntar"
let byRef = new Map();

let groups = {}; // nome -> [referências]
let selected = new Set();
let nameTouched = false;
let dirty = false;

// ---- persistência local (só conveniência; o arquivo é o products.json) ----
let baseKey = "";

function restoreDraft() {
  try {
    const stored = JSON.parse(localStorage.getItem(STORAGE_KEY) || "null");
    if (stored && stored.base === baseKey) {
      groups = stored.groups;
      dirty = true;
    }
  } catch { /* sem storage: segue sem restaurar */ }
}

function persist() {
  dirty = true;
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify({ base: baseKey, groups })); } catch { /* ignora */ }
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
  el("status").textContent = dirty ? "Alterações ainda não exportadas" : "";
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
    const reject = make("button", { type: "button", textContent: "Não juntar" });
    reject.addEventListener("click", () => sendRejections("POST", s.refs));
    const head = make("div", { className: "head" }, make("strong", { textContent: s.name }), pick, reject);
    const meta = make("div", { className: "meta" }, `${free.length} produtos · ${s.reason} · cód. ${free.map((r) => r.split(":")[1]).join(", ")} `);
    for (const w of s.warnings) meta.append(make("span", { className: "tag warn-tag", textContent: w }), " ");
    return make("li", { className: "sug" }, head, meta);
  }));
}

// ---- rejeições ("não juntar") ----
// Cada chamada devolve o catálogo atualizado; as seleções e os grupos em edição ficam como estão.
async function sendRejections(method, refs) {
  try {
    const response = await fetch("/api/rejections", {
      method,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(refs),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || `a API respondeu ${response.status}`);
    ({ suggestions, rejections = [] } = data);
    renderSuggestions();
    renderRejections();
  } catch (error) {
    flash(`Não foi possível salvar a rejeição (${error.message}).`);
  }
}

function renderRejections() {
  el("rej-count").textContent = `${rejections.length}`;
  el("rejections").replaceChildren(...rejections.map((pair) => {
    const undo = make("button", { type: "button", textContent: "Desfazer" });
    undo.addEventListener("click", () => sendRejections("DELETE", pair));
    const label = pair.map((ref) => `${byRef.get(ref)?.description ?? "?"} (cód. ${ref.split(":")[1]})`).join(" × ");
    return make("li", { className: "sug" }, make("div", { className: "head" }, make("span", { textContent: label }), undo));
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

// ---- exportar ----
const exportText = () => JSON.stringify(groups, null, 2) + "\n";

function markExported() {
  dirty = false;
  try { localStorage.removeItem(STORAGE_KEY); } catch { /* ignora */ }
  renderStatus();
}

el("download").addEventListener("click", () => {
  const url = URL.createObjectURL(new Blob([exportText()], { type: "application/json" }));
  const link = make("a", { href: url, download: "products.json" });
  link.click();
  URL.revokeObjectURL(url);
  flash("Baixado. Mova para a pasta do projeto e rode chart.py");
  markExported();
});

el("copy").addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText(exportText());
    flash("JSON copiado");
  } catch {
    flash("Não consegui copiar; use Baixar");
  }
});

if (window.showSaveFilePicker) {
  el("save").hidden = false;
  el("save").addEventListener("click", async () => {
    try {
      const handle = await window.showSaveFilePicker({
        suggestedName: "products.json",
        types: [{ description: "JSON", accept: { "application/json": [".json"] } }],
      });
      const writable = await handle.createWritable();
      await writable.write(exportText());
      await writable.close();
      flash("Salvo");
      markExported();
    } catch (error) {
      if (error.name !== "AbortError") flash("Não consegui salvar; use Baixar");
    }
  });
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
  rejections = data.rejections ?? [];
  byRef = new Map(products.map((p) => [p.ref, p]));
  groups = structuredClone(data.groups);
  baseKey = JSON.stringify(data.groups);
}

// ---- ligação ----
function renderAll() {
  renderStatus();
  renderProducts();
  renderDraft();
  renderSuggestions();
  renderRejections();
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
  restoreDraft();
  fillStores();
  renderAll();
}

start();
