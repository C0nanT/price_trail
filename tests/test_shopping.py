"""GET /api/shopping-list e months_ago: preço = média dos últimos 6 meses."""
import unittest
from datetime import date
from unittest import mock

from pricetrail.shopping import months_ago
from tests.api_case import ApiTestCase, item, note_text


class MonthsAgoTests(unittest.TestCase):
    def test_subtrai_meses_e_ajusta_fim_de_mes(self):
        self.assertEqual(months_ago(date(2026, 11, 7), 6), date(2026, 5, 7))
        self.assertEqual(months_ago(date(2026, 3, 31), 6), date(2025, 9, 30))
        self.assertEqual(months_ago(date(2026, 8, 31), 6), date(2026, 2, 28))
        self.assertEqual(months_ago(date(2026, 2, 5), 6), date(2025, 8, 5))


class ShoppingListTests(ApiTestCase):
    def setUp(self):
        super().setUp()
        patcher = mock.patch("pricetrail.shopping.today", return_value=date(2026, 11, 7))
        patcher.start()
        self.addCleanup(patcher.stop)

    def lista(self):
        response = self.client().get("/api/shopping-list")
        try:
            self.assertEqual(response.status_code, 200)
            return response.get_json()
        finally:
            response.close()

    def find(self, data, name):
        return next(row for section in data["sections"] for row in section["items"] if row["name"] == name)

    def test_media_so_das_notas_dentro_da_janela(self):
        for number, price, issued in ((1, "2,00", "02/10/2026"), (2, "4,00", "02/09/2026"), (3, "99,00", "02/01/2020")):
            self.write_note(number, item("1", "PUDIM APTI", "UND9", price), issued)
        self.import_data()
        row = self.find(self.lista(), "Pudim Apti")
        self.assertEqual((row["price"], row["per"], row["n"]), (3.0, "und", 2))

    def test_item_sem_compra_na_janela_vem_sem_preco(self):
        self.write_note(1, item("1", "PUDIM APTI", "UND9", "2,00"), "02/01/2020")
        self.import_data()
        self.assertEqual(self.find(self.lista(), "Pudim Apti")["price"], None)
        self.assertEqual(self.find(self.lista(), "Água sanitária")["price"], None)

    def test_ovo_e_cartela(self):
        self.write_note(1, item("1", "OVO GD BR PVC NIENOW", "UND9", "19,00"), "02/10/2026")
        self.import_data()
        self.assertEqual(self.find(self.lista(), "Ovos")["per"], "cartela")

    def write_note(self, number, line, issued):
        self.write_pdf(f"n{number}.pdf", line, number=number, issued=issued)


class CheckedTests(ApiTestCase):
    def test_marca_desmarca_e_limpa(self):
        client = self.client()
        put = lambda name, checked: client.put("/api/shopping-list/checked", json={"name": name, "checked": checked})
        self.assertEqual(put("Arroz", True).get_json(), {"checked": ["Arroz"]})
        self.assertEqual(put("Feijão", True).get_json(), {"checked": ["Arroz", "Feijão"]})
        self.assertEqual(put("Arroz", False).get_json(), {"checked": ["Feijão"]})
        self.assertEqual(client.get("/api/shopping-list/checked").get_json(), {"checked": ["Feijão"]})
        self.assertEqual(client.delete("/api/shopping-list/checked").get_json(), {"checked": []})

    def test_corpo_invalido(self):
        response = self.client().put("/api/shopping-list/checked", json={"name": "Arroz"})
        self.assertEqual(response.status_code, 422)
