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

function minutesText(minutes) {
  if (minutes < 60) return `${minutes} min`;
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  return rest ? `${hours} h ${rest} min` : `${hours} h`;
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
    if (response.status === 429) {
      // Bloqueado (este IP ou o teto global): nem a senha certa entra até o prazo acabar.
      showError(data?.minutesLeft
        ? `Muitas tentativas erradas. Tente de novo em ${minutesText(data.minutesLeft)}.`
        : data?.error || "Muitas tentativas erradas. Tente de novo mais tarde.");
    } else if (response.status === 401 && data?.lockMinutesIfWrong) {
      // Esta era a última tentativa: o erro acabou de bloquear o login.
      showError(`${data.error} Essa era a última tentativa: o login fica bloqueado por ${minutesText(data.lockMinutesIfWrong)}.`);
    } else {
      showError(data?.error || `O servidor respondeu ${response.status}.`);
    }
    form.password.value = "";
    form.password.focus();
  } catch (failure) {
    showError(`Não consegui falar com o servidor (${failure.message}). Tente de novo.`);
  } finally {
    send.disabled = false;
  }
}

form.addEventListener("submit", submit);
