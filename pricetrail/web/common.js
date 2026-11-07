"use strict";
// Helpers das páginas logadas. Carregado antes dos scripts de cada uma.

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

// Sessão expirada: vai ao login, que volta para esta página depois de entrar.
// A promessa nunca resolve, para a página não mostrar erro enquanto sai.
function goToLogin() {
  location.href = `/login?next=${encodeURIComponent(location.pathname + location.search)}`;
  return new Promise(() => {});
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
  if (response.status === 401) return goToLogin();
  const data = await response.json().catch(() => null);
  if (!response.ok) throw new ApiError(data?.error || `a API respondeu ${response.status}`, response.status);
  return data;
}

// Botão "Sair" de cada página: o logout exige o token CSRF da sessão, buscado na hora.
async function logout() {
  try {
    const { csrfToken } = await (await fetch("/api/session", { cache: "no-store" })).json();
    await fetch("/api/logout", { method: "POST", headers: { "X-CSRF-Token": csrfToken } });
  } finally {
    location.href = "/login";
  }
}

document.addEventListener("click", (event) => {
  if (event.target.closest("[data-logout]")) logout();
});

// what: o que a página carrega, ex.: "os preços".
function showError(what, error) {
  el("error").textContent = `Não foi possível carregar ${what} (${error.message}). `
    + "Confira se o servidor está rodando e recarregue a página.";
  el("error").hidden = false;
}
