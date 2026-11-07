"use strict";
// Helpers das duas páginas, o gráfico e o agrupamento. Carregado antes dos scripts de cada uma.

const el = (id) => document.getElementById(id);
const money = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });
const dateFormat = new Intl.DateTimeFormat("pt-BR");

// Maiúsculas e sem acento, para a busca não depender de como o nome foi digitado.
const normalize = (text) => text.normalize("NFD").replace(/[̀-ͯ]/g, "").toUpperCase();

class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

// Chama a API e devolve o JSON da resposta. Com body, envia como application/json.
// Resposta de erro vira ApiError com a mensagem da API, ou com o status quando o corpo não é JSON.
async function fetchJson(url, { method = "GET", body } = {}) {
  const options = { method };
  if (body !== undefined) {
    options.headers = { "Content-Type": "application/json" };
    options.body = JSON.stringify(body);
  }
  const response = await fetch(url, options);
  const data = await response.json().catch(() => null);
  if (!response.ok) throw new ApiError(data?.error || `a API respondeu ${response.status}`, response.status);
  return data;
}

// what: o que a página carrega, ex.: "os preços".
function showError(what, error) {
  el("error").textContent = `Não foi possível carregar ${what} (${error.message}). `
    + "Confira se o servidor está rodando e recarregue a página.";
  el("error").hidden = false;
}
