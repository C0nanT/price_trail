"""chart.py e group_page.py seguem funcionando num banco migrado, até saírem do projeto."""
import tempfile
import unittest
from pathlib import Path

import chart
import group_page
from pricetrail import importer, nfce
from pricetrail.db import connect
from products import Resolver
from tests.fixtures import make_text


class MigratedDatabaseTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.db = self.root / "t.sqlite"
        conn = connect(self.db)
        importer.save_note(conn, nfce.parse_note(make_text()), "a.pdf")
        conn.close()

    def test_chart_le_o_banco_migrado(self):
        products = chart.load_products(self.db, {}, Resolver({"Batata": ["75315333:14691"]}))
        self.assertEqual(len(products), 3)
        self.assertIn("Batata", [p["description"] for p in products])

    def test_group_page_le_o_banco_migrado(self):
        rows = group_page.load_rows(self.db)
        self.assertEqual(sorted(r["code"] for r in rows), ["10759", "14691", "23290"])
        (self.root / "a.pdf").write_text("não é pdf de verdade")
        notes = group_page.load_notes(self.db, self.root, self.root / "group_page")
        self.assertEqual(notes["75315333:14691"][0]["href"], "../a.pdf")


if __name__ == "__main__":
    unittest.main()
