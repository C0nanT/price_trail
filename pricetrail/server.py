"""Servidor local: rotas HTTP finas sobre catalog."""
import json
import re
import sqlite3
from pathlib import Path

from flask import Flask, abort, g, jsonify, request, send_file

from . import catalog
from .db import connect

WEB_DIR = Path(__file__).resolve().parent / "web"
ALLOWED_HOSTS = {"localhost", "127.0.0.1"}
ACCESS_KEY_RE = re.compile(r"[0-9]{44}")


class Pairs(list):
    """Objeto JSON lido como lista de pares: guarda nomes repetidos, que um dict esconderia."""


def create_app(db_path: Path, data_dir: Path, legacy_dir: Path | None = None) -> Flask:
    connect(db_path, data_dir, legacy_dir).close()  # migra agora: um erro aparece ao subir, não no primeiro request
    app = Flask(__name__, static_folder=WEB_DIR, static_url_path="/static")

    def db() -> sqlite3.Connection:
        """Uma conexão por request: o servidor atende em várias threads."""
        if "db" not in g:
            g.db = connect(db_path, data_dir, legacy_dir)
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

    @app.get("/groups")
    def group_page():
        return app.send_static_file("group/index.html")

    @app.get("/api/products")
    def products():
        return jsonify(catalog.list_products(db()))

    @app.get("/api/catalog")
    def catalog_data():
        return jsonify(catalog.build_catalog(db(), data_dir, catalog.load_rejected_refs(legacy_dir)))

    @app.get("/api/stores")
    def stores():
        return jsonify(catalog.list_stores(db()))

    @app.put("/api/stores/<cnpj_root>")
    def put_store(cnpj_root: str):
        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            body = {}
        try:
            return jsonify(catalog.save_store(db(), cnpj_root, body.get("store"), body.get("category")))
        except catalog.StoreError as error:
            return jsonify(error=str(error)), 422

    @app.put("/api/groups")
    def save_groups():
        if not request.is_json:
            return jsonify(error="Envie o corpo como application/json."), 415
        try:
            pairs = json.loads(request.get_data(), object_pairs_hook=Pairs)
        except ValueError:
            return jsonify(error="O corpo não é um JSON válido."), 422
        if not isinstance(pairs, Pairs):
            return jsonify(error="Esperado um objeto nome -> lista de referências."), 422
        try:
            catalog.replace_groups(db(), pairs)
        except catalog.GroupsError as error:
            return jsonify(error=str(error)), 422
        return jsonify(catalog.list_groups(db()))

    @app.get("/notes/<access_key>.pdf")
    def note_pdf(access_key: str):
        pdf = catalog.find_note_pdf(db(), data_dir, access_key) if ACCESS_KEY_RE.fullmatch(access_key) else None
        if pdf is None:
            abort(404)
        return send_file(pdf, mimetype="application/pdf")

    return app
