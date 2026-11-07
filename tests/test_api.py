"""Comportamento externo do servidor: cliente de teste do Flask sobre um banco temporário."""
import sqlite3
import unittest

from pricetrail import importer, nfce
from pricetrail.db import SCHEMA, MigrationError, connect
from tests.api_case import ApiTestCase, item
from tests.fixtures import make_text


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

    def test_banco_novo_sem_pasta_da_curadoria_antiga_ou_com_pasta_inexistente_e_criado(self):
        for legacy in (None, self.root / "nao_existe"):
            db = self.root / f"{legacy is None}.sqlite"
            connect(db, self.data, legacy).close()
            conn = sqlite3.connect(db)
            self.addCleanup(conn.close)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM stores").fetchone()[0], 0)

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

    def test_banco_na_versao_3_ganha_indice_dos_grupos_e_mantem_os_dados(self):
        self.write_legacy("products.json", self.GROUPS)
        self.add_note(item("10"))
        conn = sqlite3.connect(self.db)
        conn.execute("DROP INDEX group_refs_group_id")
        conn.execute("PRAGMA user_version = 3")
        conn.commit()
        conn.close()
        self.assertEqual(self.products()[0]["description"], "Detergente")
        conn = sqlite3.connect(self.db)
        self.addCleanup(conn.close)
        self.assertEqual(conn.execute("PRAGMA user_version").fetchone()[0], 4)
        # O índice serve ao join dos grupos e ao ON DELETE CASCADE de product_groups.
        plan = " ".join(row[3] for row in conn.execute(
            "EXPLAIN QUERY PLAN SELECT * FROM group_refs WHERE group_id = 1"))
        self.assertIn("USING INDEX group_refs_group_id", plan)

    def test_referencia_que_nao_e_texto_aborta(self):
        for ref in (12345678, ["75315333:10"]):
            for name in ("products.json", "products.rejected.json"):
                with self.subTest(ref=ref, name=name):
                    self.write_legacy(name, {"A": [ref, "75315333:11"]})
                    self.assert_migration_fails(name)
                    (self.legacy / name).unlink()

    def test_loja_que_nao_e_objeto_aborta(self):
        self.write_legacy("stores.json", {"75315333": "Atacadão"})
        self.assert_migration_fails("stores.json")


class HostTests(ApiTestCase):
    def test_aceita_localhost_e_127_0_0_1_com_ou_sem_porta(self):
        client = self.client()
        for host in ("localhost", "localhost:8000", "127.0.0.1", "127.0.0.1:8000"):
            with self.subTest(host=host):
                self.assertEqual(client.get("/api/products", headers={"Host": host}).status_code, 200)

    def test_recusa_outro_host_em_qualquer_rota(self):
        client = self.client()
        for host in ("evil.example", "evil.example:8000", "localhost.evil.example", "127.0.0.1.evil.example"):
            for path in ("/", "/groups", "/api/products", "/static/chart/app.js"):
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
        reader = connect(self.db)
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
        self.assertIn('fetchJson("/api/products")', script)
        self.assertIn('src="/static/common.js"', html)
        self.assertIn("async function fetchJson", client.get("/static/common.js").get_data(as_text=True))
        self.assertEqual(client.get("/static/chart/style.css").status_code, 200)

    def test_pagina_tem_link_para_o_agrupamento(self):
        self.assertIn('href="/groups"', self.client().get("/").get_data(as_text=True))


class GroupPageTests(ApiTestCase):
    def test_pagina_busca_os_dados_na_api(self):
        self.add_note(item("10", "PRODUTO QUE NAO VAI NO HTML"))
        client = self.client()
        page = client.get("/groups")
        self.assertEqual(page.status_code, 200)
        html = page.get_data(as_text=True)
        self.assertIn("Agrupar produtos", html)
        self.assertNotIn("PRODUTO QUE NAO VAI NO HTML", html)
        self.assertNotIn("data.js", html)
        script = client.get("/static/group/app.js").get_data(as_text=True)
        self.assertIn('fetchJson("/api/catalog")', script)
        self.assertIn('src="/static/common.js"', html)
        self.assertEqual(client.get("/static/app.css").status_code, 200)

    def test_pagina_tem_link_para_o_grafico_e_area_de_erro(self):
        html = self.client().get("/groups").get_data(as_text=True)
        self.assertIn('href="/"', html)
        self.assertIn('id="error"', html)


if __name__ == "__main__":
    unittest.main()
