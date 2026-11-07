"""Logs do servidor: JSON, sem dados de compras, INFO no stdout e WARNING+ no stderr."""
import io
import json
import logging
import sys
from unittest import mock

from pricetrail import cli, logs
from tests.api_case import ApiTestCase, CNPJ_TEXT, item, note_text
from tests.test_import_api import UPLOAD_HEADERS


class ServerLogTest(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.stream = io.StringIO()
        handler = logging.StreamHandler(self.stream)
        handler.setFormatter(logs.JsonFormatter())
        log = logging.getLogger("pricetrail")
        log.addHandler(handler)
        self.addCleanup(log.removeHandler, handler)
        self.addCleanup(log.setLevel, log.level)
        log.setLevel(logging.DEBUG)

    def upload(self, *files):
        data = {"files": [(io.BytesIO(("%PDF-" + text).encode()), name) for name, text in files]}
        return self.client().post("/api/import", data=data, headers=UPLOAD_HEADERS,
                                  content_type="multipart/form-data")

    def lines(self):
        return [json.loads(line) for line in self.stream.getvalue().splitlines()]

    def test_upload_gera_json_com_contagens_e_chaves_sem_dados_de_compras(self):
        text = note_text(item("10", description="PRODUTO SECRETO"), number=1)
        response = self.upload(("minha-nota.pdf", text), ("ruim.pdf", "corrompido"))
        for line in self.lines():
            self.assertTrue({"ts", "level", "logger", "msg"} <= line.keys())
            self.assertTrue(line["ts"].endswith("+00:00"))
        everything = self.stream.getvalue()
        key = response.get_json()["results"][0]["access_key"]
        self.assertIn(key, everything)
        self.assertEqual(self.lines()[-1]["summary"], {"new": 1, "existing": 0, "error": 1})
        for secret in ("minha-nota", "ruim.pdf", "PRODUTO SECRETO", CNPJ_TEXT, "pdftotext", "erro de leitura"):
            self.assertNotIn(secret, everything)
        error = response.get_json()["results"][1]
        self.assertEqual(error["name"], "ruim.pdf")
        self.assertIn("pdftotext", error["message"])

    def test_aviso_de_loja_sem_cadastro_leva_so_a_raiz_do_cnpj(self):
        self.upload(("a.pdf", note_text(item("10"))))
        (warning,) = [line for line in self.lines() if line["level"] == "WARNING"]
        self.assertEqual(warning["cnpj_root"], "75315333")
        self.assertNotIn("0290", self.stream.getvalue())

    def test_erro_inesperado_usa_exception_com_mensagem_generica(self):
        with mock.patch("pricetrail.importer.read_and_save", side_effect=RuntimeError("falha")):
            self.upload(("a.pdf", note_text(item("10"))))
        (error,) = [line for line in self.lines() if line["level"] == "ERROR"]
        self.assertIn("RuntimeError", error["exc_info"])
        self.assertNotIn("a.pdf", error["msg"])


class ConfigureTest(ApiTestCase):
    def setUp(self):
        super().setUp()
        log = logging.getLogger("pricetrail")
        saved = (list(log.handlers), log.level, log.propagate)

        def restore():
            for handler in list(log.handlers):
                log.removeHandler(handler)
            for handler in saved[0]:
                log.addHandler(handler)
            log.setLevel(saved[1])
            log.propagate = saved[2]

        self.addCleanup(restore)

    def configure(self, level=None):
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(sys, "stdout", out), mock.patch.object(sys, "stderr", err):
            logs.configure_server_logging(level)
        return out, err

    def test_info_no_stdout_e_warning_com_traceback_no_stderr(self):
        out, err = self.configure()
        log = logging.getLogger("pricetrail")
        log.info("oi", extra={"n": 3})
        try:
            raise ValueError("x")
        except ValueError:
            log.exception("falhou")
        log.debug("ruido")
        (info,) = [json.loads(line) for line in out.getvalue().splitlines()]
        (error,) = [json.loads(line) for line in err.getvalue().splitlines()]
        self.assertEqual((info["msg"], info["n"], info["level"]), ("oi", 3, "INFO"))
        self.assertIn("ValueError", error["exc_info"])

    def test_log_level_liga_debug_e_o_padrao_e_info(self):
        with mock.patch.dict("os.environ", {"LOG_LEVEL": "DEBUG"}):
            out, _ = self.configure()
        logging.getLogger("pricetrail").debug("d")
        self.assertIn('"DEBUG"', out.getvalue())
        with mock.patch.dict("os.environ", clear=False):
            __import__("os").environ.pop("LOG_LEVEL", None)
            out, _ = self.configure()
        logging.getLogger("pricetrail").debug("d")
        self.assertEqual(out.getvalue(), "")

    def test_serve_nao_cria_pricetrail_log_e_nao_aceita_log(self):
        with mock.patch("flask.Flask.run"), mock.patch.object(sys, "stdout", io.StringIO()):
            code = cli.main(["serve", "--db", str(self.db), "--data", str(self.data)])
        self.assertEqual(code, 0)
        self.assertFalse(any(isinstance(h, logging.FileHandler) for h in logging.getLogger("pricetrail").handlers))
        with self.assertRaises(SystemExit), mock.patch.object(sys, "stderr", io.StringIO()):
            cli.main(["serve", "--log", "x"])
