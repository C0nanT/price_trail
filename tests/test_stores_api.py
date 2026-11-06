"""Cadastro de lojas: GET /api/stores, PUT /api/stores/<raiz> e o aviso do import."""
from tests.api_case import ApiTestCase, item

OUTRA = "84683481000100"


class StoresApiTest(ApiTestCase):
    def put(self, client, root, body):
        return client.put(f"/api/stores/{root}", json=body)

    def test_separa_cadastradas_e_sem_cadastro(self):
        self.write_legacy("stores.json", {"75315333": {"store": "Atacadão", "category": "Mercado"}})
        self.add_note(item("1"))
        self.add_note(item("2"), number=2, cnpj=OUTRA, cnpj_text="84.683.481/0001-00")
        data = self.client().get("/api/stores").get_json()
        self.assertEqual(data["stores"], [{"cnpj_root": "75315333", "store": "Atacadão", "category": "Mercado"}])
        (missing,) = data["unregistered"]
        self.assertEqual(missing["cnpj_root"], "84683481")
        self.assertEqual(missing["name"], "ATACADAO S.A.")

    def test_put_cria_e_atualiza(self):
        self.add_note(item("1"))
        client = self.client()
        self.assertEqual(self.put(client, "75315333", {"store": "Atacadão", "category": "Mercado"}).status_code, 200)
        self.assertEqual(self.put(client, "75315333", {"store": "Atacadão 2", "category": "Casa"}).status_code, 200)
        data = client.get("/api/stores").get_json()
        self.assertEqual(data["stores"], [{"cnpj_root": "75315333", "store": "Atacadão 2", "category": "Casa"}])
        self.assertEqual(data["unregistered"], [])

    def test_put_invalido_retorna_422(self):
        client = self.client()
        for root, body in (
            ("123", {"store": "A", "category": "B"}),
            ("1234567a", {"store": "A", "category": "B"}),
            ("75315333", {"store": "  ", "category": "B"}),
            ("75315333", {"category": "B"}),
            ("75315333", [1]),
        ):
            response = self.put(client, root, body)
            self.assertEqual(response.status_code, 422, (root, body))
            self.assertTrue(response.get_json()["error"])
        self.assertEqual(client.get("/api/stores").get_json()["stores"], [])

    def test_loja_cadastrada_aparece_em_products(self):
        self.add_note(item("1"))
        client = self.client()
        self.put(client, "75315333", {"store": "Atacadão", "category": "Mercado"})
        (product,) = client.get("/api/products").get_json()
        self.assertEqual((product["stores"], product["categories"]), (["Atacadão"], ["Mercado"]))

    def test_sem_cadastro_usa_nome_da_nota_e_outros(self):
        self.add_note(item("1"))
        (product,) = self.products()
        self.assertEqual((product["stores"], product["categories"]), (["ATACADAO S.A."], ["Outros"]))


class ImportWarningTest(ApiTestCase):
    def test_avisa_uma_vez_por_raiz_sem_cadastro(self):
        self.write_pdf("a.pdf", item("1"), number=1)
        self.write_pdf("b.pdf", item("2"), number=2)
        err = self.import_data()
        self.assertEqual(err.count("AVISO"), 1)
        self.assertIn("75315333", err)
        self.assertIn("/groups", err)

    def test_nao_avisa_loja_cadastrada(self):
        self.write_legacy("stores.json", {"75315333": {"store": "A", "category": "B"}})
        self.write_pdf("a.pdf", item("1"))
        self.assertNotIn("AVISO", self.import_data())
