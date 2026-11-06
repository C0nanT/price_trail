import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from pricetrail import cli, nfce


class ImportCommandTest(unittest.TestCase):
    def run_cli(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(list(args))
        return code, out.getvalue(), err.getvalue()

    def test_importa_pasta_vazia(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            code, out, _ = self.run_cli(
                "import", str(tmp), "--db", str(tmp / "t.sqlite"),
                "--stores", str(tmp / "stores.json"), "--log", str(tmp / "t.log"),
            )
            self.assertEqual(code, 0)
            self.assertIn("0 novas, 0 já existentes, 0 com erro", out)
            self.assertTrue((tmp / "t.sqlite").exists())

    def test_pasta_inexistente_sai_com_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            code, _, err = self.run_cli(
                "import", str(tmp / "nada"), "--db", str(tmp / "t.sqlite"),
                "--stores", str(tmp / "s.json"), "--log", str(tmp / "t.log"),
            )
            self.assertEqual(code, 2)
            self.assertIn("pasta não encontrada", err)


class ParserIndependenteTest(unittest.TestCase):
    def test_nfce_nao_depende_de_banco_nem_subprocess(self):
        source = Path(nfce.__file__).read_text(encoding="utf-8")
        self.assertNotIn("sqlite3", source)
        self.assertNotIn("subprocess", source)


if __name__ == "__main__":
    unittest.main()
