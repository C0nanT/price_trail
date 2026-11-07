"use strict";
// Página de importação: envia os PDFs para /api/import e mostra o resultado de cada arquivo.

// O cabeçalho próprio é o que o servidor exige para aceitar o envio: outro site não consegue mandá-lo.
async function upload(files) {
  const form = new FormData();
  for (const file of files) form.append("files", file);
  const response = await fetch("/api/import", { method: "POST", headers: { "X-Pricetrail": "1" }, body: form });
  const data = await response.json().catch(() => null);
  if (!response.ok) throw new ApiError(data?.error || `o servidor respondeu ${response.status}`, response.status);
  return data;
}

function detail(result) {
  if (result.status === "ERRO") return result.message;
  const date = result.issued_at ? dateFormat.format(new Date(result.issued_at)) : "";
  const text = result.status === "NOVA"
    ? `${result.seller_name}, ${result.item_count} itens, ${date}`
    : `chave ${result.access_key}`;
  const warning = result.unregistered_store ? ` (loja sem cadastro: ${result.seller_name})` : "";
  return text + (result.message ? `; ${result.message}` : "") + warning;
}

function showResult({ results, summary }) {
  el("summary").textContent = `${summary.new} novas, ${summary.existing} já existentes, ${summary.error} com erro`;
  el("rows").replaceChildren(...results.map((result) => {
    const row = document.createElement("tr");
    for (const text of [result.name, result.status, detail(result)]) {
      const cell = document.createElement("td");
      cell.textContent = text;
      row.append(cell);
    }
    if (result.status === "ERRO") row.className = "error";
    return row;
  }));
  el("result").hidden = false;
}

el("form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const files = el("files").files;
  el("error").hidden = true;
  if (!files.length) {
    el("error").textContent = "Escolha um ou mais PDFs.";
    el("error").hidden = false;
    return;
  }
  el("send").disabled = true;
  el("status").textContent = "Enviando...";
  try {
    showResult(await upload(files));
    el("files").value = "";
  } catch (error) {
    el("error").textContent = `Nada foi importado: ${error.message}`;
    el("error").hidden = false;
  } finally {
    el("send").disabled = false;
    el("status").textContent = "";
  }
});
