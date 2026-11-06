import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

import chart
from pricetrail import importer, nfce
from pricetrail.db import SCHEMA
from products import ProductsError, Resolver, drop_rejected, load_groups, load_rejected, normalize, suggest_groups
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


class DropRejectedTests(unittest.TestCase):
    def suggestions(self):
        return suggest_groups([row("1", "X"), row("2", "X"), row("3", "X"), row("4", "Y"), row("5", "Y")])

    def test_whole_group_rejected_disappears(self):
        out = drop_rejected(self.suggestions(), {"75315333:4", "75315333:5"})
        self.assertEqual([s["refs"] for s in out], [["75315333:1", "75315333:2", "75315333:3"]])

    def test_single_ref_rejected_keeps_the_rest(self):
        out = drop_rejected(self.suggestions(), {"75315333:3"})
        refs = {tuple(s["refs"]) for s in out}
        self.assertIn(("75315333:1", "75315333:2"), refs)
        self.assertTrue(all(len(m["code"]) for s in out for m in s["members"]))
        self.assertEqual([m["code"] for m in out[0]["members"]], ["1", "2"])

    def test_leaving_one_product_drops_suggestion(self):
        out = drop_rejected(self.suggestions(), {"75315333:1", "75315333:2"})
        self.assertEqual([s["refs"] for s in out], [["75315333:4", "75315333:5"]])

    def test_duplicate_suggestions_merge(self):
        base = self.suggestions()[0]
        out = drop_rejected([base, dict(base)], set())
        self.assertEqual(len(out), 1)

    def test_warnings_recomputed_after_dropping(self):
        rows = [row("1", "X", prices=[1.0]), row("2", "X", prices=[1.1]), row("3", "X", prices=[9.0])]
        before = suggest_groups(rows)[0]
        self.assertTrue(before["warnings"])
        after = drop_rejected([before], {"75315333:3"})[0]
        self.assertEqual(after["warnings"], [])

    def test_load_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "r.json"
            self.assertEqual(load_rejected(path), set())
            path.write_text('{"A": ["75315333:1"], "B": ["75315333:2"]}')
            self.assertEqual(load_rejected(path), {"75315333:1", "75315333:2"})


class ChartGroupingTests(unittest.TestCase):
    def build_db(self, tmp):
        db = Path(tmp) / "t.sqlite"
        conn = sqlite3.connect(db)
        conn.executescript(SCHEMA)
        # duas notas com o mesmo produto sob códigos diferentes
        for number, code, price, total in [(1, "10", "5,00", "5,00"), (2, "11", "6,00", "6,00")]:
            note = nfce.parse_note(make_text(
                [("DET YPE", code, "1", "UND9", price, total)],
                total=total, discount="", paid=total, number=number))
            importer.save_note(conn, note, f"{number}.pdf")
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
            conn.executescript(SCHEMA)
            for number, unit in [(1, "UND9"), (2, "KG9")]:
                note = nfce.parse_note(make_text(
                    [("QJO", str(number), "1", unit, "5", "5,00")],
                    total="5,00", discount="", paid="5,00", number=number))
                importer.save_note(conn, note, f"{number}.pdf")
            conn.close()
            merged = chart.load_products(db, {}, Resolver({"Queijo": ["QJO"]}))
            self.assertEqual(len(merged), 2)


if __name__ == "__main__":
    unittest.main()
