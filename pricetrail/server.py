"""Servidor local: rotas HTTP finas sobre catalog."""
import dataclasses
import json
import logging
import re
import sqlite3
from pathlib import Path

from flask import Flask, abort, g, jsonify, request, send_file

from . import catalog, importer, shopping
from .db import connect

WEB_DIR = Path(__file__).resolve().parent / "web"
ALLOWED_HOSTS = {"localhost", "127.0.0.1"}
ACCESS_KEY_RE = re.compile(r"[0-9]{44}")
MAX_UPLOAD_MB = 20
MAX_UPLOAD_FILES = 50
APP_HEADER = "X-Pricetrail"  # enviado pela página /import
SUMMARY_KEYS = {importer.NEW: "new", importer.EXISTING: "existing", importer.ERROR: "error"}


class Pairs(list):
    """Objeto JSON lido como lista de pares: guarda nomes repetidos, que um dict esconderia."""


def create_app(
    db_path: Path, data_dir: Path, legacy_dir: Path | None = None, log_file: Path | None = None
) -> Flask:
    """log_file recebe o log do upload, no formato do CLI; sem ele, o log fica como estiver."""
    if log_file is not None:
        importer.configure_log(log_file)
    connect(db_path, data_dir, legacy_dir).close()  # migra agora: um erro aparece ao subir, não no primeiro request
    app = Flask(__name__, static_folder=WEB_DIR, static_url_path="/static")
    app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_MB * 1024 * 1024

    @app.errorhandler(413)
    def too_large(_error):
        return jsonify(error=f"Envio acima de {MAX_UPLOAD_MB} MB: envie menos arquivos de cada vez."), 413

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

    @app.get("/lista")
    def shopping_list_page():
        return app.send_static_file("lista/index.html")

    @app.get("/api/shopping-list")
    def shopping_list():
        return jsonify(shopping.build_list(db()))

    @app.get("/api/products")
    def products():
        return jsonify(catalog.list_products(db()))

    @app.get("/api/catalog")
    def catalog_data():
        return jsonify(catalog.build_catalog(db(), data_dir))

    def change_rejections(change):
        if not request.is_json:
            abort(415)
        try:
            change(db(), request.get_json(silent=True))
        except catalog.RejectionError as error:
            return jsonify(error=str(error)), 422
        return jsonify(catalog.build_catalog(db(), data_dir))

    @app.post("/api/rejections")
    def reject():
        return change_rejections(catalog.reject_pairs)

    @app.delete("/api/rejections")
    def undo_rejection():
        return change_rejections(catalog.undo_rejected_pairs)

    @app.get("/api/stores")
    def stores():
        return jsonify(catalog.list_stores(db()))

    @app.put("/api/stores/<cnpj_root>")
    def put_store(cnpj_root: str):
        if not request.is_json:
            return jsonify(error="Envie o corpo como application/json."), 415
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

    def sent_by_this_app() -> bool:
        """Contra envio de outro site: um formulário multipart não passa por preflight de CORS.

        O cabeçalho próprio força o preflight, que o servidor não autoriza. O Origin,
        quando vem, precisa ser o próprio servidor.
        """
        if request.headers.get(APP_HEADER) != "1":
            return False
        origin = request.headers.get("Origin")
        return origin is None or origin == request.host_url.rstrip("/")

    @app.get("/import")
    def import_page():
        return app.send_static_file("import/index.html")

    @app.post("/api/import")
    def upload():
        if not sent_by_this_app():
            return jsonify(error="Envio recusado: use a página /import deste servidor."), 403
        files = [file for file in request.files.getlist("files") if file.filename]
        if not files:
            return jsonify(error="Nenhum arquivo recebido: escolha um ou mais PDFs de NFC-e."), 422
        if len(files) > MAX_UPLOAD_FILES:
            return jsonify(
                error=f"{len(files)} arquivos num envio só: o limite é {MAX_UPLOAD_FILES}; envie em partes."
            ), 422
        conn = db()
        known_roots = catalog.registered_store_roots(conn)
        results = [
            importer.import_upload(conn, Path(file.filename).name, file.stream, data_dir, known_roots)
            for file in files
        ]
        summary = {"new": 0, "existing": 0, "error": 0}
        for result in results:
            summary[SUMMARY_KEYS[result.status]] += 1
        logging.getLogger("pricetrail").info(
            "upload: %d novas, %d já existentes, %d com erro", summary["new"], summary["existing"], summary["error"]
        )
        return jsonify(results=[dataclasses.asdict(result) for result in results], summary=summary)

    @app.get("/notes/<access_key>.pdf")
    def note_pdf(access_key: str):
        pdf = catalog.find_note_pdf(db(), data_dir, access_key) if ACCESS_KEY_RE.fullmatch(access_key) else None
        if pdf is None:
            abort(404)
        return send_file(pdf, mimetype="application/pdf")

    return app
