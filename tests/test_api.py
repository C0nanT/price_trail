"""Comportamento externo do servidor: cliente de teste do Flask sobre um banco temporário."""
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from pricetrail import importer, nfce
from pricetrail.db import SCHEMA, MigrationError, connect
from pricetrail.server import create_app
from tests.fixtures import make_key, make_text


def item(code, description="DET YPE", unit="UND9", price="5,00"):
    return (description, code, "1", unit, price, price)


class ApiTestCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.db = self.root / "t.sqlite"
        self.legacy = self.root / "legado"
        self.legacy.mkdir()

    def write_legacy(self, name, content):
        (self.legacy / name).write_text(json.dumps(content), encoding="utf-8")

    def client(self):
        return create_app(self.db, self.legacy).test_client()

    def add_note(self, *items, number=1, cnpj="75315333029000", cnpj_text="75.315.333/0290-00"):
        total = f"{sum(int(i[5].replace(',', '')) for i in items) / 100:.2f}".replace(".", ",")
        note = nfce.parse_note(make_text(
            list(items), total=total, discount="", paid=total, number=number,
            key=make_key(cnpj=cnpj, number=number), cnpj_text=cnpj_text))
        conn = connect(self.db, self.legacy)
        importer.save_note(conn, note, f"{number}.pdf")
        conn.close()

    def products(self):
        response = self.client().get("/api/products")
        self.assertEqual(response.status_code, 200)
        return response.get_json()


class ProductsTests(ApiTestCase):
    def test_formato_igual_ao_dos_dados_do_grafico(self):
        self.add_note(item("10"))
        self.assertEqual(self.products(), [{
            "code": "10",
            "description": "DET YPE",
            "unit": "UND",
            "seller": "ATACADAO S.A.",
            "stores": ["ATACADAO S.A."],
            "categories": ["Outros"],
            "purchases": [{
                "issued_at": "2026-10-02T19:53:38",
                "seller": "ATACADAO S.A.",
                "price": 5.0,
                "quantity": 1.0,
                "total": 5.0,
            }],
        }])

    def test_duas_filiais_da_mesma_raiz_viram_um_produto(self):
        self.add_note(item("10", price="5,00"), number=1)
        self.add_note(item("10", price="6,00"), number=2, cnpj="75315333000199", cnpj_text="75.315.333/0001-99")
        products = self.products()
        self.assertEqual(len(products), 1)
        self.assertCountEqual([p["price"] for p in products[0]["purchases"]], [5.0, 6.0])

    def test_mesmo_codigo_em_raizes_diferentes_nao_junta(self):
        self.add_note(item("10"), number=1)
        self.add_note(item("10"), number=2, cnpj="84683481000100", cnpj_text="84.683.481/0001-00")
        self.assertEqual(len(self.products()), 2)

    def test_loja_cadastrada_aparece_com_nome_e_categoria(self):
        self.write_legacy("stores.json", {"75315333": {"store": "Atacadão", "category": "Mercado"}})
        self.add_note(item("10"))
        product = self.products()[0]
        self.assertEqual(product["stores"], ["Atacadão"])
        self.assertEqual(product["categories"], ["Mercado"])
        self.assertEqual(product["seller"], "ATACADAO S.A.")

    def test_loja_sem_cadastro_fica_com_nome_da_nota_e_outros(self):
        self.write_legacy("stores.json", {"84683481": {"store": "Farmácia", "category": "Farmácia"}})
        self.add_note(item("10"))
        product = self.products()[0]
        self.assertEqual(product["stores"], ["ATACADAO S.A."])
        self.assertEqual(product["categories"], ["Outros"])

    def test_produtos_sem_grupo_ficam_separados(self):
        self.add_note(item("10"), number=1)
        self.add_note(item("11"), number=2)
        self.assertEqual(len(self.products()), 2)

    def test_produtos_do_grupo_juntam(self):
        self.write_legacy("products.json", {"Detergente": ["75315333:10", "75315333:11"]})
        self.add_note(item("10", price="5,00"), number=1)
        self.add_note(item("11", price="6,00"), number=2)
        products = self.products()
        self.assertEqual(len(products), 1)
        self.assertEqual(products[0]["description"], "Detergente")
        self.assertEqual(products[0]["code"], "10, 11")
        self.assertCountEqual([p["price"] for p in products[0]["purchases"]], [5.0, 6.0])

    def test_unidades_diferentes_nao_juntam_mesmo_no_grupo(self):
        self.write_legacy("products.json", {"Queijo": ["75315333:1", "75315333:2"]})
        self.add_note(item("1", "QJO", unit="UND9"), number=1)
        self.add_note(item("2", "QJO", unit="KG9"), number=2)
        products = self.products()
        self.assertEqual(sorted(p["unit"] for p in products), ["KG", "UND"])
        self.assertEqual({p["description"] for p in products}, {"Queijo"})

    def test_grupo_vale_para_todas_as_filiais_da_raiz(self):
        self.write_legacy("products.json", {"Detergente": ["75315333:10"]})
        self.add_note(item("10"), number=1)
        self.add_note(item("10"), number=2, cnpj="75315333000199", cnpj_text="75.315.333/0001-99")
        products = self.products()
        self.assertEqual(len(products), 1)
        self.assertEqual(products[0]["description"], "Detergente")

    def test_mais_compras_primeiro_e_depois_por_descricao(self):
        self.add_note(item("3", "BBB"), item("2", "AAA"), number=1)
        self.add_note(item("1", "CCC"), number=2)
        self.add_note(item("1", "CCC", price="6,00"), number=3)
        self.assertEqual([p["description"] for p in self.products()], ["CCC", "AAA", "BBB"])


class MigrationTests(ApiTestCase):
    STORES = {"75315333": {"store": "Atacadão", "category": "Mercado"}}
    GROUPS = {"Detergente": ["75315333:10", "75315333:11"]}

    def build_version_0(self):
        """Banco como ele é hoje: notes, items e a view, sem nenhuma migração."""
        conn = sqlite3.connect(self.db)
        conn.executescript(SCHEMA)
        for number, code in [(1, "10"), (2, "11"), (3, "12")]:
            note = nfce.parse_note(make_text(
                [item(code)], total="5,00", discount="", paid="5,00", number=number))
            importer.save_note(conn, note, f"{number}.pdf")
        conn.close()

    def test_banco_atual_mantem_notas_e_ganha_lojas_e_grupos(self):
        self.build_version_0()
        self.write_legacy("stores.json", self.STORES)
        self.write_legacy("products.json", self.GROUPS)
        products = self.products()
        self.assertEqual([(p["description"], p["code"], len(p["purchases"])) for p in products],
                         [("Detergente", "10, 11", 2), ("DET YPE", "12", 1)])
        self.assertEqual(products[0]["stores"], ["Atacadão"])

    def test_banco_novo_sem_jsons_abre_vazio(self):
        self.assertEqual(self.products(), [])

    def test_carga_roda_uma_vez_e_reabrir_nao_tem_efeito(self):
        self.build_version_0()
        self.write_legacy("stores.json", self.STORES)
        self.write_legacy("products.json", self.GROUPS)
        before = self.products()
        self.assertEqual(self.products(), before)
        self.write_legacy("stores.json", {"75315333": {"store": "Outro nome", "category": "Outra"}})
        self.write_legacy("products.json", {"Mudou": ["75315333:12"]})
        self.assertEqual(self.products(), before)
        (self.legacy / "stores.json").unlink()
        (self.legacy / "products.json").unlink()
        self.assertEqual(self.products(), before)

    def assert_migration_fails(self, message):
        with self.assertRaises(MigrationError) as caught:
            self.client()
        self.assertIn(message, str(caught.exception))

    def test_referencia_em_dois_grupos_aborta_sem_aplicar_nada(self):
        self.build_version_0()
        self.write_legacy("stores.json", self.STORES)
        self.write_legacy("products.json", {"A": ["75315333:10"], "B": ["75315333:10"]})
        self.assert_migration_fails("75315333:10")
        # Corrigido o arquivo, a carga inteira roda: nada ficou pela metade.
        self.write_legacy("products.json", {"A": ["75315333:10"]})
        products = self.products()
        self.assertEqual({p["stores"][0] for p in products}, {"Atacadão"})
        self.assertEqual({p["description"] for p in products}, {"A", "DET YPE"})

    def test_referencia_repetida_no_mesmo_grupo_e_aceita(self):
        self.write_legacy("products.json", {"A": ["75315333:10", "75315333:10"]})
        self.add_note(item("10"))
        self.assertEqual(self.products()[0]["description"], "A")

    def test_referencia_por_descricao_aborta(self):
        self.write_legacy("products.json", {"A": ["DET.LIQ.YPE"]})
        self.assert_migration_fails("DET.LIQ.YPE")

    def test_json_quebrado_aborta(self):
        (self.legacy / "products.json").write_text("{ruim", encoding="utf-8")
        self.assert_migration_fails("products.json")

    def test_formato_errado_de_grupos_aborta(self):
        self.write_legacy("products.json", {"A": "75315333:10"})
        self.assert_migration_fails("products.json")


class HostTests(ApiTestCase):
    def test_aceita_localhost_e_127_0_0_1_com_ou_sem_porta(self):
        client = self.client()
        for host in ("localhost", "localhost:8000", "127.0.0.1", "127.0.0.1:8000"):
            with self.subTest(host=host):
                self.assertEqual(client.get("/api/products", headers={"Host": host}).status_code, 200)

    def test_recusa_outro_host_em_qualquer_rota(self):
        client = self.client()
        for host in ("evil.example", "evil.example:8000", "localhost.evil.example", "127.0.0.1.evil.example"):
            for path in ("/", "/api/products", "/static/chart/app.js"):
                with self.subTest(host=host, path=path):
                    self.assertEqual(client.get(path, headers={"Host": host}).status_code, 403)


class ImportWithServerTests(ApiTestCase):
    def test_nota_importada_aparece_no_proximo_request(self):
        client = self.client()
        self.assertEqual(client.get("/api/products").get_json(), [])
        self.add_note(item("10"))
        self.assertEqual(len(client.get("/api/products").get_json()), 1)

    def test_importa_enquanto_outra_conexao_esta_lendo(self):
        client = self.client()
        self.add_note(item("10"), number=1)
        reader = connect(self.db, self.legacy)
        self.addCleanup(reader.close)
        reader.execute("BEGIN")
        self.assertEqual(reader.execute("SELECT COUNT(*) FROM notes").fetchone()[0], 1)
        self.add_note(item("11"), number=2)
        self.assertEqual(len(client.get("/api/products").get_json()), 2)


class ChartPageTests(ApiTestCase):
    def test_pagina_busca_os_dados_na_api(self):
        self.add_note(item("10", "PRODUTO QUE NAO VAI NO HTML"))
        client = self.client()
        page = client.get("/")
        self.assertEqual(page.status_code, 200)
        html = page.get_data(as_text=True)
        self.assertIn("Histórico de preços", html)
        self.assertNotIn("PRODUTO QUE NAO VAI NO HTML", html)
        script = client.get("/static/chart/app.js").get_data(as_text=True)
        self.assertIn('fetch("/api/products")', script)
        self.assertEqual(client.get("/static/chart/style.css").status_code, 200)


if __name__ == "__main__":
    unittest.main()
