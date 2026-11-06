"use strict";
// Seção "Lojas": cadastro de nome e categoria por raiz de CNPJ (GET /api/stores, PUT /api/stores/<raiz>).
// Independente do restante da página: usa só os helpers `el` e `make` de app.js.

function storeRow(root, name, store, category, hint) {
  const nameInput = make("input", { value: store, placeholder: name, "aria-label": `Nome da loja ${root}` });
  const categoryInput = make("input", { value: category, placeholder: "Outros", "aria-label": `Categoria da loja ${root}` });
  const save = make("button", { type: "button", textContent: "Salvar" });
  const message = make("span", { className: "meta" });
  const submit = async () => {
    message.textContent = "";
    try {
      const response = await fetch(`/api/stores/${root}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ store: nameInput.value, category: categoryInput.value }),
      });
      if (response.status === 422) {
        message.textContent = (await response.json()).error;
        return;
      }
      if (!response.ok) throw new Error(`a API respondeu ${response.status}`);
      await loadStores();
    } catch (error) {
      message.textContent = `Não consegui salvar (${error.message})`;
    }
  };
  save.addEventListener("click", submit);
  for (const input of [nameInput, categoryInput]) {
    input.addEventListener("keydown", (event) => { if (event.key === "Enter") submit(); });
  }
  return make("li", { className: "store-row" },
    make("span", { className: "meta", textContent: `${root} · ${hint}` }), nameInput, categoryInput, save, message);
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
    const response = await fetch("/api/stores");
    if (!response.ok) throw new Error(`a API respondeu ${response.status}`);
    el("stores-error").hidden = true;
    renderStores(await response.json());
  } catch (error) {
    el("stores-error").textContent = `Não foi possível carregar as lojas (${error.message}).`;
    el("stores-error").hidden = false;
  }
}

loadStores();
