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
  el("unregistered").hidden = !results.some((result) => result.unregistered_store);
  el("result").hidden = false;
}

function fail(message) {
  el("error").textContent = message;
  el("error").hidden = false;
}

// Mensagem legível para cada falha do envio; status ausente é o servidor fora do ar.
function uploadErrorMessage(error) {
  const reasons = {
    403: "o servidor recusou o envio; use a página /import do próprio servidor",
    413: "os arquivos passam do limite de 20 MB",
    422: error.message,
  };
  if (error.status === undefined) return "Nada foi importado: não consegui falar com o servidor. Confira se ele está rodando.";
  return `Nada foi importado: ${reasons[error.status] || error.message}`;
}

let sending = false;

async function send(files) {
  if (sending) return;
  el("error").hidden = true;
  if (!files.length) return fail("Escolha um ou mais PDFs.");
  sending = true;
  el("send").disabled = true;
  el("status").textContent = "Enviando...";
  try {
    showResult(await upload(files));
    el("files").value = "";
  } catch (error) {
    el("result").hidden = true;
    fail(uploadErrorMessage(error instanceof ApiError ? error : new ApiError(error.message)));
  } finally {
    sending = false;
    el("send").disabled = false;
    el("status").textContent = "";
  }
}

el("form").addEventListener("submit", (event) => {
  event.preventDefault();
  send(el("files").files);
});

const drop = el("drop");
for (const name of ["dragenter", "dragover"]) {
  drop.addEventListener(name, (event) => { event.preventDefault(); drop.classList.add("over"); });
}
for (const name of ["dragleave", "drop"]) {
  drop.addEventListener(name, () => drop.classList.remove("over"));
}
drop.addEventListener("drop", (event) => {
  event.preventDefault();
  send([...event.dataTransfer.files].filter((file) => file.type === "application/pdf" || /\.pdf$/i.test(file.name)));
});
// Soltar fora da área não deve abrir o PDF no navegador.
for (const name of ["dragover", "drop"]) window.addEventListener(name, (event) => event.preventDefault());
