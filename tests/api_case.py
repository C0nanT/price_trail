"""Base dos testes da API: banco, pasta de dados e curadoria antiga em uma pasta temporária."""
import contextlib
import io
import json
import logging
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from pricetrail import cli, importer, nfce
from pricetrail.db import connect
from pricetrail.server import create_app
from tests.fixtures import make_key, make_text

CNPJ = "75315333029000"
CNPJ_TEXT = "75.315.333/0290-00"


def item(code, description="DET YPE", unit="UND9", price="5,00"):
    return (description, code, "1", unit, price, price)


def note_text(*items, number=1, cnpj=CNPJ, cnpj_text=CNPJ_TEXT, issued="02/10/2026"):
    total = f"{sum(int(i[5].replace(',', '')) for i in items) / 100:.2f}".replace(".", ",")
    return make_text(list(items), total=total, discount="", paid=total, number=number,
                     key=make_key(cnpj=cnpj, number=number), cnpj_text=cnpj_text, issued=issued)


def run_cli(*args):
    """Roda a linha de comando e devolve (código de saída, stdout, stderr)."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = cli.main([str(arg) for arg in args])
    return code, out.getvalue(), err.getvalue()


def note_url(number=1, cnpj=CNPJ):
    return f"/notes/{make_key(cnpj=cnpj, number=number)}.pdf"


class ApiTestCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.db = self.root / "t.sqlite"
        self.legacy = self.root / "legado"
        self.legacy.mkdir()
        self.data = self.root / "data"
        self.data.mkdir()
        # O pdftotext é a fronteira externa: aqui o "PDF" é o próprio texto da nota.
        self.pdftotext_calls = []
        self.addCleanup(self.close_log_files)
        patcher = mock.patch("subprocess.run", self.fake_pdftotext)
        patcher.start()
        self.addCleanup(patcher.stop)

    @staticmethod
    def close_log_files():
        """O import grava num arquivo temporário: solta o handler antes de a pasta sumir."""
        log = logging.getLogger("pricetrail")
        for handler in list(log.handlers):
            if isinstance(handler, logging.FileHandler):
                log.removeHandler(handler)
                handler.close()

    def fake_pdftotext(self, command, **_kwargs):
        self.pdftotext_calls.append(command)
        text = Path(command[2]).read_text(encoding="utf-8").removeprefix("%PDF-")
        return subprocess.CompletedProcess(command, 1 if text == "corrompido" else 0, text, "erro de leitura")

    def write_legacy(self, name, content):
        (self.legacy / name).write_text(json.dumps(content), encoding="utf-8")

    def client(self):
        return create_app(self.db, self.data, self.legacy).test_client()

    def add_note(self, *items, **note):
        """Grava a nota sem PDF nenhum na pasta de dados."""
        parsed = nfce.parse_note(note_text(*items, **note))
        conn = connect(self.db, self.data, self.legacy)
        importer.save_note(conn, parsed, f"{parsed.number}.pdf")
        conn.close()

    def write_pdf(self, name, *items, **note):
        path = self.data / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(note_text(*items, **note), encoding="utf-8")
        return path

    def import_data(self, folder=None):
        """Roda o importador e devolve o que ele escreveu em stderr."""
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()) as err:
            code = importer.import_folder(folder or self.data, self.db,
                                          self.root / "t.log", self.data, self.legacy)
        self.assertEqual(code, 0)
        return err.getvalue()

    def products(self):
        response = self.client().get("/api/products")
        self.assertEqual(response.status_code, 200)
        return response.get_json()

    def catalog(self):
        response = self.client().get("/api/catalog")
        self.assertEqual(response.status_code, 200)
        return response.get_json()

    def href(self, ref):
        """Link do PDF da única nota do produto."""
        (note,) = self.catalog()["notes"][ref]
        return note["href"]
