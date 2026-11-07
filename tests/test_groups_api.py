"""PUT /api/groups: substitui todos os grupos de uma vez, ou não altera nada."""
import json
import unittest

from tests.api_case import ApiTestCase, item

A, B, C = "75315333:1", "75315333:2", "75315333:3"


class SaveGroupsTests(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.add_note(item("1"), item("2"), item("3"), number=1)

    def put(self, body, content_type="application/json"):
        data = body if isinstance(body, str) else json.dumps(body)
        return self.client().put("/api/groups", data=data, content_type=content_type)

    def groups(self):
        return self.catalog()["groups"]

    def test_grupo_salvo_aparece_em_products_e_em_catalog(self):
        response = self.put({"Detergente": [A, B]})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.groups(), {"Detergente": [A, B]})
        descriptions = {p["description"] for p in self.products()}
        self.assertIn("Detergente", descriptions)

    def test_substitui_renomeia_e_exclui(self):
        self.put({"Detergente": [A, B], "Outro": [C]})
        self.put({"Det Ypê": [B, A]})
        self.assertEqual(self.groups(), {"Det Ypê": [B, A]})
        self.put({})
        self.assertEqual(self.groups(), {})

    def test_referencia_em_dois_grupos_da_422_e_nao_altera(self):
        self.put({"Antigo": [A, B]})
        response = self.put({"X": [A, C], "Y": [C, B]})
        self.assertEqual(response.status_code, 422)
        self.assertIn(C, response.get_json()["error"])
        self.assertEqual(self.groups(), {"Antigo": [A, B]})

    def test_nome_repetido_da_422_e_nao_altera(self):
        self.put({"Antigo": [A, B]})
        for body in ('{"X": ["75315333:1"], "X": ["75315333:2"]}', '{"X": ["75315333:1"], " X ": ["75315333:2"]}'):
            response = self.put(body)
            self.assertEqual(response.status_code, 422)
            self.assertIn("X", response.get_json()["error"])
        self.assertEqual(self.groups(), {"Antigo": [A, B]})

    def test_formato_invalido_da_422(self):
        for body in ({"": [A]}, {"X": []}, {"X": "75315333:1"}, {"X": ["abc"]}, {"X": [1]}, [A]):
            self.assertEqual(self.put(body).status_code, 422, body)
        self.assertEqual(self.put("{quebrado").status_code, 422)
        self.assertEqual(self.groups(), {})

    def test_raiz_com_digitos_que_nao_sao_ascii_ou_quebra_de_linha_da_422(self):
        for ref in ("７５３１５３３３:1", "75315333:1\n"):
            self.assertEqual(self.put({"X": [ref]}).status_code, 422, ref)
        self.assertEqual(self.groups(), {})

    def test_escrita_sem_content_type_json_e_recusada(self):
        for content_type in ("text/plain", "application/x-www-form-urlencoded"):
            self.assertEqual(self.put({"X": [A]}, content_type).status_code, 415)
        self.assertEqual(self.groups(), {})


if __name__ == "__main__":
    unittest.main()
