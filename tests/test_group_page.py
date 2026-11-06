import unittest

from group_page import build_data


def row(code, description, price, last, unit="UND", cnpj="75315333029000"):
    return {"cnpj": cnpj, "seller_name": "ATACADAO S.A.", "code": code, "description": description,
            "unit": unit, "prices": [price], "purchases": 1, "last": last}


class BuildDataTests(unittest.TestCase):
    def test_one_entry_per_store_code_with_latest_description(self):
        rows = [row("1", "DET YPE", 2.0, "2026-01-01"), row("1", "DET YPE NOVO", 3.0, "2026-05-01"),
                row("2", "DET YPE", 2.5, "2026-02-01")]
        data = build_data(rows, {"G": ["75315333:2"]}, {"75315333": {"store": "Atacadão"}})
        by_ref = {p["ref"]: p for p in data["products"]}
        self.assertEqual(set(by_ref), {"75315333:1", "75315333:2"})
        self.assertEqual(by_ref["75315333:1"]["description"], "DET YPE NOVO")
        self.assertEqual((by_ref["75315333:1"]["min"], by_ref["75315333:1"]["max"]), (2.0, 3.0))
        self.assertEqual(by_ref["75315333:1"]["purchases"], 2)
        self.assertEqual(by_ref["75315333:1"]["store"], "Atacadão")
        self.assertEqual(data["groups"], {"G": ["75315333:2"]})

    def test_includes_suggestions(self):
        data = build_data([row("1", "X", 1.0, "2026-01-01"), row("2", "X", 1.0, "2026-01-02")], {}, {})
        self.assertEqual(data["suggestions"][0]["refs"], ["75315333:1", "75315333:2"])


if __name__ == "__main__":
    unittest.main()
