import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

import chart
import pricetrail as pt
from products import ProductsError, Resolver, load_groups, normalize, suggest_groups
from tests.fixtures import make_text


class NormalizeTests(unittest.TestCase):
    def test_normalize(self):
        self.assertEqual(normalize("Água M.Crystal"), "AGUA M CRYSTAL")
        self.assertEqual(normalize("  DET.LIQ.  YPE "), "DET LIQ YPE")


class ResolverTests(unittest.TestCase):
    def setUp(self):
        self.resolver = Resolver({
            "Detergente Ype": ["75315333:11757", "75315333:13453"],
            "Leite": ["leite piracanjuba in"],
        })

    def test_code_ref_matches_store_prefix_only(self):
        self.assertEqual(self.resolver.resolve("75315333029000", "11757", "X"), "Detergente Ype")
        self.assertIsNone(self.resolver.resolve("84683481000100", "11757", "X"))

    def test_description_ref_ignores_case_and_punctuation(self):
        self.assertEqual(self.resolver.resolve("84683481000100", "1", "LEITE PIRACANJUBA IN"), "Leite")

    def test_ungrouped_is_none(self):
        self.assertIsNone(self.resolver.resolve("75315333029000", "999", "OUTRO"))

    def test_duplicate_ref_in_two_groups(self):
        with self.assertRaises(ProductsError):
            Resolver({"A": ["75315333:1"], "B": ["75315333:1"]})


class LoadGroupsTests(unittest.TestCase):
    def test_missing_file(self):
        self.assertEqual(load_groups(Path("/nao/existe.json")), {})

    def test_invalid_json_and_shape(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "products.json"
            path.write_text("{ruim")
            with self.assertRaises(ProductsError):
                load_groups(path)
            path.write_text('{"A": "texto"}')
            with self.assertRaises(ProductsError):
                load_groups(path)
            path.write_text('{"A": ["75315333:1"]}')
            self.assertEqual(load_groups(path), {"A": ["75315333:1"]})


def row(code, description, unit="UND", prices=(1.0,), cnpj="75315333029000"):
    return {"cnpj": cnpj, "code": code, "description": description, "unit": unit,
            "prices": list(prices), "purchases": len(prices)}


class SuggestTests(unittest.TestCase):
    def test_same_description_different_codes(self):
        out = suggest_groups([row("1", "DET YPE", prices=[2.79]), row("2", "DET YPE", prices=[2.79]),
                              row("3", "OUTRO")])
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["refs"], ["75315333:1", "75315333:2"])
        self.assertEqual(out[0]["warnings"], [])

    def test_warns_on_price_and_unit(self):
        out = suggest_groups([row("1", "X", prices=[4.5]), row("2", "X", unit="EMB", prices=[9.0])])
        self.assertEqual(len(out[0]["warnings"]), 2)

    def test_similar_descriptions(self):
        out = suggest_groups([row("1", "CEREAL KELLOGGS"), row("2", "CEREAL MAT KELLOGGS")])
        self.assertEqual(out[0]["reason"], "descrições parecidas")

    def test_does_not_mix_stores(self):
        out = suggest_groups([row("1", "X"), row("2", "X", cnpj="84683481000100")])
        self.assertEqual(out, [])


class ChartGroupingTests(unittest.TestCase):
    def build_db(self, tmp):
        db = Path(tmp) / "t.sqlite"
        conn = sqlite3.connect(db)
        conn.executescript(pt.SCHEMA)
        # duas notas com o mesmo produto sob códigos diferentes
        for number, code, price, total in [(1, "10", "5,00", "5,00"), (2, "11", "6,00", "6,00")]:
            note = pt.parse_note(make_text(
                [("DET YPE", code, "1", "UND9", price, total)],
                total=total, discount="", paid=total, number=number))
            pt.save_note(conn, note, f"{number}.pdf")
        conn.close()
        return db

    def test_ungrouped_stay_separate_and_grouped_merge(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = self.build_db(tmp)
            separate = chart.load_products(db, {})
            self.assertEqual(len(separate), 2)
            merged = chart.load_products(db, {}, Resolver({"Detergente": ["75315333:10", "75315333:11"]}))
            self.assertEqual(len(merged), 1)
            product = merged[0]
            self.assertEqual(product["description"], "Detergente")
            self.assertEqual(product["code"], "10, 11")
            self.assertEqual([p["price"] for p in product["purchases"]], [5.0, 6.0])
            self.assertEqual(product["categories"], ["Outros"])

    def test_different_units_are_not_merged(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "t.sqlite"
            conn = sqlite3.connect(db)
            conn.executescript(pt.SCHEMA)
            for number, unit in [(1, "UND9"), (2, "KG9")]:
                note = pt.parse_note(make_text(
                    [("QJO", str(number), "1", unit, "5", "5,00")],
                    total="5,00", discount="", paid="5,00", number=number))
                pt.save_note(conn, note, f"{number}.pdf")
            conn.close()
            merged = chart.load_products(db, {}, Resolver({"Queijo": ["QJO"]}))
            self.assertEqual(len(merged), 2)


if __name__ == "__main__":
    unittest.main()
