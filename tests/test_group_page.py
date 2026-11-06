import sqlite3
import tempfile
import unittest
from pathlib import Path

from pricetrail import importer, nfce
from pricetrail.db import SCHEMA
from group_page import build_data, load_notes
from tests.fixtures import make_text


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


class LoadNotesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.db, self.data, self.out = root / "t.sqlite", root / "data", root / "group_page"
        self.data.mkdir()
        conn = sqlite3.connect(self.db)
        conn.executescript(SCHEMA)
        importer.save_note(conn, nfce.parse_note(make_text()), "a.pdf")
        conn.close()

    def tearDown(self):
        self.tmp.cleanup()

    def test_links_pdf_by_name_relative_to_page(self):
        (self.data / "a.pdf").write_text("não é pdf de verdade")
        notes = load_notes(self.db, self.data, self.out)
        entry = notes["75315333:14691"][0]
        self.assertEqual(entry["href"], "../data/a.pdf")
        self.assertEqual((entry["date"], entry["number"], entry["price"]), ("2026-10-02", 45170, 4.89))

    def test_missing_pdf_has_no_href(self):
        notes = load_notes(self.db, self.data, self.out)
        self.assertIsNone(notes["75315333:14691"][0]["href"])

    def test_spaces_are_url_encoded(self):
        (self.data / "a.pdf").write_text("x")
        sub = self.data / "minha pasta"
        sub.mkdir()
        (sub / "a.pdf").write_text("x")
        # o primeiro por ordem de busca vence; só verifica que não quebra com espaço
        self.assertNotIn(" ", load_notes(self.db, self.data, self.out)["75315333:14691"][0]["href"])


if __name__ == "__main__":
    unittest.main()
