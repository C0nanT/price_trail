"use strict";
// Página de login: busca o token CSRF em /api/session e envia usuário e senha para /api/login.
// Não usa o fetchJson do common.js, que manda de volta ao login em qualquer 401.

const next = new URLSearchParams(location.search).get("next") || "/";
const form = document.getElementById("form");
const error = document.getElementById("error");
const send = document.getElementById("send");

async function session() {
  const response = await fetch("/api/session", { cache: "no-store" });
  if (!response.ok) throw new Error(`o servidor respondeu ${response.status}`);
  return response.json();
}

function showError(message) {
  error.textContent = message;
  error.hidden = false;
}

async function submit(event) {
  event.preventDefault();
  error.hidden = true;
  send.disabled = true;
  try {
    const { csrfToken } = await session();
    const response = await fetch("/api/login", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
      body: JSON.stringify({ username: form.username.value, password: form.password.value, next }),
    });
    const data = await response.json().catch(() => null);
    if (response.ok) {
      // O servidor devolve o next saneado: só caminho do próprio site.
      location.replace(data?.next || "/");
      return;
    }
    showError(data?.error || `O servidor respondeu ${response.status}.`);
    form.password.value = "";
    form.password.focus();
  } catch (failure) {
    showError(`Não consegui falar com o servidor (${failure.message}). Tente de novo.`);
  } finally {
    send.disabled = false;
  }
}

form.addEventListener("submit", submit);
