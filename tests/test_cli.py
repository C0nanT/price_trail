import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from pricetrail import nfce
from tests.api_case import run_cli


class ImportCommandTest(unittest.TestCase):
    def test_importa_pasta_vazia(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            code, out, _ = run_cli("import", tmp, "--db", tmp / "t.sqlite", "--log", tmp / "t.log")
            self.assertEqual(code, 0)
            self.assertIn("0 novas, 0 já existentes, 0 com erro", out)
            self.assertTrue((tmp / "t.sqlite").exists())

    def test_pasta_inexistente_sai_com_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            code, _, err = run_cli("import", tmp / "nada", "--db", tmp / "t.sqlite", "--log", tmp / "t.log")
            self.assertEqual(code, 2)
            self.assertIn("pasta não encontrada", err)


class AmbienteTest(unittest.TestCase):
    def test_env_define_banco_e_pasta_de_dados_e_argumento_ganha(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / "dados").mkdir()
            env = {"DB_PATH": str(tmp / "env.sqlite"), "DATA_DIR": str(tmp / "dados")}
            with mock.patch.dict(os.environ, env):
                code, out, _ = run_cli("import", "--log", tmp / "t.log")
                self.assertEqual(code, 0)
                self.assertIn("0 novas", out)
                self.assertTrue((tmp / "env.sqlite").exists())
                run_cli("import", "--db", tmp / "arg.sqlite", "--log", tmp / "t.log")
                self.assertTrue((tmp / "arg.sqlite").exists())


class ParserIndependenteTest(unittest.TestCase):
    def test_nfce_nao_depende_de_banco_nem_subprocess(self):
        source = Path(nfce.__file__).read_text(encoding="utf-8")
        self.assertNotIn("sqlite3", source)
        self.assertNotIn("subprocess", source)


if __name__ == "__main__":
    unittest.main()
