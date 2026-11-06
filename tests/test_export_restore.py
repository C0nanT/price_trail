"""Subcomandos export e restore: a curadoria sai num JSON estável e volta igual."""
import contextlib
import io
import json
import sqlite3
import unittest
from unittest import mock

from pricetrail import cli
from pricetrail.db import SCHEMA
from tests.api_case import ApiTestCase, item

A, B, C = (f"75315333:{n}" for n in (1, 2, 3))


class ExportRestoreTests(ApiTestCase):
    def setUp(self):
        super().setUp()
        patcher = mock.patch.object(cli, "PROJECT_DIR", self.legacy)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.file = self.root / "curadoria.json"

    def run_cli(self, command, *args, db=None):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main([command, "--db", str(db or self.db), "--data", str(self.data), *args])
        return code, out.getvalue(), err.getvalue()

    def curate(self):
        web = self.client()
        web.put("/api/groups", json={"Detergente": [A, B]})
        web.post("/api/rejections", json=[C, B])
        web.put("/api/stores/75315333", json={"store": "Atacadão", "category": "Mercado"})

    def test_exportar_duas_vezes_gera_arquivos_identicos_e_ordenados(self):
        self.add_note(item("1"), item("2"), item("3"))
        self.curate()
        self.assertEqual(self.run_cli("export", "--out", str(self.file))[0], 0)
        first = self.file.read_bytes()
        self.run_cli("export", "--out", str(self.file))
        self.assertEqual(self.file.read_bytes(), first)
        data = json.loads(first)
        self.assertEqual(data["format_version"], 1)
        self.assertEqual(data["groups"], {"Detergente": [A, B]})
        self.assertEqual(data["rejected_pairs"], [[B, C]])
        self.assertEqual(data["stores"], {"75315333": {"store": "Atacadão", "category": "Mercado"}})
        self.assertEqual(list(data), sorted(data))

    def test_exportar_e_restaurar_em_banco_novo_da_as_mesmas_respostas(self):
        self.add_note(item("1"), item("2"), item("3"))
        self.curate()
        before = (self.products(), self.catalog())
        self.run_cli("export", "--out", str(self.file))
        self.db = self.root / "novo.sqlite"
        self.add_note(item("1"), item("2"), item("3"))
        code, _, _ = self.run_cli("restore", str(self.file))
        self.assertEqual(code, 0)
        self.assertEqual((self.products(), self.catalog()), before)

    def test_restaura_curadoria_de_produto_sem_nota(self):
        self.file.write_text(json.dumps({
            "format_version": 1,
            "groups": {"Fantasma": ["11111111:9", "22222222:8"]},
            "rejected_pairs": [["11111111:9", "22222222:8"]],
            "stores": {},
        }), encoding="utf-8")
        code, _, err = self.run_cli("restore", str(self.file))
        self.assertEqual(code, 0, err)
        catalog = self.catalog()
        self.assertEqual(catalog["groups"], {"Fantasma": ["11111111:9", "22222222:8"]})
        self.assertEqual(catalog["rejections"], [["11111111:9", "22222222:8"]])

    def test_restore_substitui_a_curadoria_existente(self):
        self.add_note(item("1"), item("2"), item("3"))
        self.curate()
        self.file.write_text(json.dumps({"format_version": 1, "groups": {"Outro": [C]},
                                         "rejected_pairs": [], "stores": {}}), encoding="utf-8")
        self.assertEqual(self.run_cli("restore", str(self.file))[0], 0)
        catalog = self.catalog()
        self.assertEqual(catalog["groups"], {"Outro": [C]})
        self.assertEqual(catalog["rejections"], [])
        self.assertEqual(self.client().get("/api/stores").get_json()["stores"], [])

    def test_arquivo_invalido_falha_com_mensagem_e_nao_altera_o_banco(self):
        self.add_note(item("1"), item("2"), item("3"))
        self.curate()
        before = self.catalog()
        valid = {"format_version": 1, "groups": {"Novo": [C]}, "rejected_pairs": [], "stores": {}}
        cases = {
            "formato desconhecido": {**valid, "format_version": 99},
            "sem versão": {k: v for k, v in valid.items() if k != "format_version"},
            "ref em dois grupos": {**valid, "groups": {"X": [A], "Y": [A]}},
            "par com ref repetida": {**valid, "rejected_pairs": [[A, A]]},
            "ref malformada": {**valid, "rejected_pairs": [[A, "abc"]]},
            "loja inválida": {**valid, "stores": {"123": {"store": "x", "category": "y"}}},
            "não é objeto": [1, 2],
        }
        for label, content in cases.items():
            with self.subTest(label):
                self.file.write_text(json.dumps(content), encoding="utf-8")
                code, _, err = self.run_cli("restore", str(self.file))
                self.assertEqual(code, 2)
                self.assertTrue(err.strip())
                self.assertEqual(self.catalog(), before)
        self.file.write_text("{quebrado", encoding="utf-8")
        self.assertEqual(self.run_cli("restore", str(self.file))[0], 2)
        self.assertEqual(self.run_cli("restore", str(self.root / "nada.json"))[0], 2)
        self.assertEqual(self.catalog(), before)

    def test_arquivo_padrao_fica_na_raiz_do_projeto(self):
        self.add_note(item("1"))
        self.assertEqual(self.run_cli("export")[0], 0)
        self.assertTrue((self.legacy / "curadoria.json").is_file())

    def test_export_num_banco_v0_carrega_a_curadoria_antiga(self):
        # sem passar legacy_dir como import e serve, o banco v0 pularia a carga para sempre
        self.write_legacy("products.json", {"Antigo": [A, B]})
        conn = sqlite3.connect(self.db)
        conn.executescript(SCHEMA)
        conn.close()
        self.assertEqual(self.run_cli("export", "--out", str(self.file))[0], 0)
        self.assertEqual(json.loads(self.file.read_text())["groups"], {"Antigo": [A, B]})


if __name__ == "__main__":
    unittest.main()
