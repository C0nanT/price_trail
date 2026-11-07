"""Login de usuário único: credenciais do ambiente, sessão assinada do Flask e token CSRF.

O usuário e o hash argon2 da senha vêm de AUTH_USERNAME e AUTH_PASSWORD_HASH, e SECRET_KEY
assina o cookie. Sem os três, o servidor não sobe: nunca abre sem autenticação por esquecimento.
"""
import hmac
import logging
import os
import secrets
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import timedelta
from urllib.parse import quote, urlsplit

from argon2 import PasswordHasher, extract_parameters
from argon2.exceptions import InvalidHashError, VerificationError
from flask import Flask, jsonify, redirect, request, session

REQUIRED_ENV = ("AUTH_USERNAME", "AUTH_PASSWORD_HASH", "SECRET_KEY")
SESSION_LIFETIME = timedelta(days=30)
CSRF_HEADER = "X-CSRF-Token"
PUBLIC_PATHS = {"/login", "/api/session", "/api/login", "/health"}
PUBLIC_PREFIXES = ("/static/",)
UNKNOWN_USER = "desconhecido"  # nunca loga o que foi digitado no campo de usuário: pode ser a senha
WRONG_CREDENTIALS = "Usuário ou senha inválidos."

log = logging.getLogger("pricetrail.auth")


class AuthConfigError(Exception):
    """Configuração de login ausente ou inválida: o servidor não deve subir."""


@dataclass(frozen=True)
class AuthConfig:
    username: str
    password_hash: str
    secret_key: str
    cookie_secure: bool


def config_from_env(env: Mapping[str, str] = os.environ) -> AuthConfig:
    missing = [name for name in REQUIRED_ENV if not env.get(name, "").strip()]
    if missing:
        raise AuthConfigError(
            f"faltam as variáveis de ambiente {', '.join(missing)}: o login é obrigatório e o servidor"
            " não sobe sem elas. Gere o hash da senha com `python -m pricetrail hash-password`."
        )
    password_hash = env["AUTH_PASSWORD_HASH"].strip()
    try:
        extract_parameters(password_hash)
    except InvalidHashError:
        raise AuthConfigError(
            "AUTH_PASSWORD_HASH não é um hash argon2: gere um com `python -m pricetrail hash-password`."
        ) from None
    return AuthConfig(
        username=env["AUTH_USERNAME"],
        password_hash=password_hash,
        secret_key=env["SECRET_KEY"],
        cookie_secure=env.get("SESSION_COOKIE_SECURE", "1").strip() != "0",
    )


def hash_password(password: str) -> str:
    return PasswordHasher().hash(password)


def password_matches(password_hash: str, password: str) -> bool:
    try:
        return PasswordHasher().verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def safe_next(value) -> str:
    """Só caminho relativo do próprio site; qualquer outra coisa vira a página inicial."""
    if not isinstance(value, str) or not value.startswith("/") or value.startswith(("//", "/\\")):
        return "/"
    if any(char == "\\" or char.isspace() or ord(char) < 32 or ord(char) == 127 for char in value):
        return "/"
    parts = urlsplit(value)
    if parts.scheme or parts.netloc:
        return "/"
    return value


def is_public(path: str) -> bool:
    return path in PUBLIC_PATHS or path.startswith(PUBLIC_PREFIXES)


def client_ip() -> str:
    # O ticket 05 troca pelo IP escolhido em pick_client_ip.
    return request.remote_addr or "unknown"


def install(app: Flask, config: AuthConfig) -> None:
    """Liga a sessão, o controle de acesso e as rotas de login no app."""
    app.config.update(
        SECRET_KEY=config.secret_key,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SECURE=config.cookie_secure,
        SESSION_COOKIE_SAMESITE="Lax",
        PERMANENT_SESSION_LIFETIME=SESSION_LIFETIME,
    )
    expected_user = config.username.encode("utf-8")

    def logged_in() -> bool:
        return session.get("auth") is True

    def csrf_ok() -> bool:
        expected = session.get("csrf")
        sent = request.headers.get(CSRF_HEADER)
        return bool(expected and sent) and hmac.compare_digest(sent.encode("utf-8"), expected.encode("utf-8"))

    @app.before_request
    def require_login():
        if is_public(request.path) or logged_in():
            return None
        if request.path.startswith(("/api/", "/notes/")):
            return jsonify(error="Sessão expirada ou ausente: entre de novo."), 401
        target = request.path
        if request.query_string:
            target += "?" + request.query_string.decode("utf-8", "replace")
        return redirect("/login?next=" + quote(target, safe=""))

    @app.get("/login")
    def login_page():
        return app.send_static_file("login/index.html")

    @app.get("/api/session")
    def session_state():
        """A página de login é estática: busca aqui o token CSRF antes de enviar o formulário."""
        if not session.get("csrf"):
            session["csrf"] = secrets.token_urlsafe(32)
        response = jsonify(csrfToken=session["csrf"], loggedIn=logged_in())
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.post("/api/login")
    def login():
        if not csrf_ok():
            return jsonify(error="Sessão do formulário expirada: recarregue a página e tente de novo."), 403
        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            body = {}
        username, password = body.get("username"), body.get("password")
        # O hash é verificado sempre e o usuário comparado em tempo constante:
        # nem a resposta nem o tempo dizem qual dos dois estava errado.
        user_ok = isinstance(username, str) and hmac.compare_digest(username.encode("utf-8"), expected_user)
        password_ok = password_matches(config.password_hash, password if isinstance(password, str) else "")
        user = config.username if user_ok else UNKNOWN_USER
        if not (user_ok and password_ok):
            log.warning("login falhou", extra={"event": "login_falhou", "ip": client_ip(), "user": user})
            return jsonify(error=WRONG_CREDENTIALS), 401
        session.clear()
        session.permanent = True
        session["auth"] = True
        session["csrf"] = secrets.token_urlsafe(32)
        log.info("login ok", extra={"event": "login_ok", "ip": client_ip(), "user": user})
        return jsonify(next=safe_next(body.get("next")))

    @app.post("/api/logout")
    def logout():
        if not csrf_ok():
            return jsonify(error="Sessão do formulário expirada: recarregue a página e tente de novo."), 403
        session.clear()
        log.info("logout", extra={"event": "logout", "ip": client_ip(), "user": config.username})
        return jsonify(ok=True)
