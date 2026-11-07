"use strict";
// Seção "Lojas": cadastro de nome e categoria por raiz de CNPJ (GET /api/stores, PUT /api/stores/<raiz>).
// Independente do restante da página: usa só `make` de app.js e `el` e `fetchJson` de common.js.

const INPUT = "min-h-touch w-full min-w-0 md:w-auto md:flex-1 md:basis-44 rounded-lg border border-muted bg-surface px-3 text-base text-ink";

function storeRow(root, name, store, category, hint) {
  const nameInput = make("input", { className: INPUT, value: store, placeholder: name, "aria-label": `Nome da loja ${root}` });
  const categoryInput = make("input", { className: INPUT, value: category, placeholder: "Outros", "aria-label": `Categoria da loja ${root}` });
  const save = make("button", { className: "btn w-full md:w-auto", type: "button", textContent: "Salvar" });
  const message = make("span", { className: "text-sm text-warn", role: "alert" });
  const submit = async () => {
    message.textContent = "";
    try {
      await fetchJson(`/api/stores/${root}`, {
        method: "PUT",
        body: { store: nameInput.value, category: categoryInput.value },
      });
    } catch (error) {
      // 422 é cadastro inválido: a mensagem da API já diz o que corrigir.
      message.textContent = error.status === 422 ? error.message : `Não consegui salvar (${error.message})`;
      return;
    }
    await loadStores();
  };
  save.addEventListener("click", submit);
  for (const input of [nameInput, categoryInput]) {
    input.addEventListener("keydown", (event) => { if (event.key === "Enter") submit(); });
  }
  return make("li", { className: "flex flex-col gap-2 p-3 md:flex-row md:flex-wrap md:items-center" },
    make("span", { className: "text-sm md:basis-full text-muted", textContent: `${root} · ${hint}` }), nameInput, categoryInput, save, message);
}

function renderStores(data) {
  const missing = data.unregistered.map((s) =>
    storeRow(s.cnpj_root, s.name, s.name, "", `${s.notes} ${s.notes === 1 ? "nota" : "notas"}`));
  const known = data.stores.map((s) => storeRow(s.cnpj_root, s.store, s.store, s.category, "cadastrada"));
  el("stores-missing").replaceChildren(...missing);
  el("stores-known").replaceChildren(...known);
  el("stores-count").textContent = `${missing.length} sem cadastro · ${known.length} cadastradas`;
}

async function loadStores() {
  try {
    const data = await fetchJson("/api/stores");
    el("stores-error").hidden = true;
    renderStores(data);
  } catch (error) {
    el("stores-error").textContent = `Não foi possível carregar as lojas (${error.message}).`;
    el("stores-error").hidden = false;
  }
}

loadStores();
