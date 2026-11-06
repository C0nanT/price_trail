"""Servidor local: rotas HTTP finas sobre catalog."""
import sqlite3
from pathlib import Path

from flask import Flask, abort, g, jsonify, request

from . import catalog
from .db import connect

WEB_DIR = Path(__file__).resolve().parent / "web"
ALLOWED_HOSTS = {"localhost", "127.0.0.1"}


def create_app(db_path: Path, legacy_dir: Path | None = None) -> Flask:
    connect(db_path, legacy_dir).close()  # migra agora: um erro aparece ao subir, não no primeiro request
    app = Flask(__name__, static_folder=WEB_DIR, static_url_path="/static")

    def db() -> sqlite3.Connection:
        """Uma conexão por request: o servidor atende em várias threads."""
        if "db" not in g:
            g.db = connect(db_path, legacy_dir)
        return g.db

    @app.teardown_appcontext
    def close_db(_error) -> None:
        conn = g.pop("db", None)
        if conn is not None:
            conn.close()

    @app.before_request
    def refuse_foreign_host() -> None:
        """Contra DNS rebinding: um site externo não pode se passar pelo servidor local."""
        if request.host.split(":")[0].lower() not in ALLOWED_HOSTS:
            abort(403)

    @app.get("/")
    def chart_page():
        return app.send_static_file("chart/index.html")

    @app.get("/api/products")
    def products():
        return jsonify(catalog.list_products(db()))

    return app
