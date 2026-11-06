import sqlite3
import unittest
from decimal import Decimal

from pricetrail import importer, nfce
from pricetrail.db import SCHEMA
from tests.fixtures import (
    farmacia_item, make_key, make_text, spaced,  # noqa: F401
)


class ConversionTests(unittest.TestCase):
    def test_to_decimal_brazilian_format(self):
        self.assertEqual(nfce.to_decimal("1.234,56"), Decimal("1234.56"))
        self.assertEqual(nfce.to_decimal("29,9"), Decimal("29.9"))

    def test_to_cents(self):
        self.assertEqual(nfce.to_cents("6,11"), 611)
        self.assertEqual(nfce.to_cents("1.000,00"), 100000)

    def test_clean_address(self):
        self.assertEqual(nfce.clean_address("A , 469 , , ESTREITO ,\n FLORIANOPOLIS , SC"),
                         "A, 469, ESTREITO, FLORIANOPOLIS, SC")


class AccessKeyTests(unittest.TestCase):
    def test_valid_key(self):
        self.assertTrue(nfce.access_key_is_valid(make_key()))

    def test_wrong_check_digit(self):
        key = make_key()
        bad = key[:43] + str((int(key[43]) + 1) % 10)
        self.assertFalse(nfce.access_key_is_valid(bad))


class PricePerKgTests(unittest.TestCase):
    def d(self, s):
        return Decimal(s)

    def test_unit_kg(self):
        self.assertEqual(nfce.compute_price_per_kg("BATATA", "KG", self.d("4.89")), self.d("4.89"))

    def test_grams_in_description(self):
        self.assertEqual(nfce.compute_price_per_kg("ARROZ 500G", "UND", self.d("5")), self.d("10"))

    def test_kg_in_description_decimal_comma(self):
        self.assertEqual(nfce.compute_price_per_kg("FARINHA 1,5KG", "UND", self.d("6")), self.d("4"))

    def test_multipack_is_ignored(self):
        self.assertIsNone(nfce.compute_price_per_kg("COCA 12X500G", "UND", self.d("30")))

    def test_no_weight(self):
        self.assertIsNone(nfce.compute_price_per_kg("CAFE PET", "UND", self.d("29.9")))


class ParseNoteTests(unittest.TestCase):
    def test_mercado_layout(self):
        note = nfce.parse_note(make_text())
        self.assertEqual(note.seller_cnpj, "75315333029000")
        self.assertEqual(note.seller_name, "ATACADAO S.A.")
        self.assertEqual(note.seller_address, "JUSCELINO KUBITSCHECK DE OLIVE, 469, ESTREITO, FLORIANOPOLIS, SC")
        self.assertEqual(note.issued_at, "2026-10-02T19:53:38")
        self.assertEqual((note.total_cents, note.discount_cents, note.paid_cents), (4099, 100, 3999))
        self.assertEqual(len(note.items), 3)

    def test_item_fields(self):
        item = nfce.parse_note(make_text()).items[1]
        self.assertEqual(item.product_code, "14691")
        self.assertEqual(item.quantity, Decimal("1.25"))
        self.assertEqual(item.unit_raw, "KG9")
        self.assertEqual(item.unit, "KG")
        self.assertEqual(item.unit_price, Decimal("4.89"))
        self.assertEqual(item.price_per_kg, Decimal("4.89"))
        self.assertEqual(item.total_cents, 611)

    def test_pharmacy_layout_total_before_quantity(self):
        items = [
            ("ENXAGUANTE COLGATE 500ML", "1000020275", "65,99", "1", "UN", "65,99"),
            ("LAVITAN MELATONINA", "1000023079", "73,80", "2", "UN", "36,9"),
        ]
        note = nfce.parse_note(make_text(items, farmacia=True, total="139,79", discount="", paid="139,79"))
        self.assertEqual([i.total_cents for i in note.items], [6599, 7380])
        self.assertEqual(note.items[1].quantity, Decimal("2"))

    def test_missing_total_falls_back_to_paid_plus_discount(self):
        note = nfce.parse_note(make_text(omit_total=True))
        self.assertEqual(note.total_cents, 4099)

    def test_no_discount(self):
        note = nfce.parse_note(make_text(discount="", paid="40,99"))
        self.assertEqual(note.discount_cents, 0)

    def test_empty_text(self):
        with self.assertRaises(nfce.NoteError):
            nfce.parse_note("")

    def test_missing_items_end_marker(self):
        with self.assertRaises(nfce.NoteError):
            nfce.parse_note(make_text().replace(nfce.ITEMS_END, "x"))

    def test_missing_total_field_when_paid_missing(self):
        with self.assertRaisesRegex(nfce.NoteError, "valor a pagar"):
            nfce.parse_note(make_text().replace("Valor a pagar R$:", ""))

    def test_bad_check_digit(self):
        key = make_key()
        bad = key[:43] + str((int(key[43]) + 1) % 10)
        with self.assertRaisesRegex(nfce.NoteError, "dígito verificador"):
            nfce.parse_note(make_text(key=bad))

    def test_cnpj_mismatch_with_key(self):
        with self.assertRaisesRegex(nfce.NoteError, "CNPJ"):
            nfce.parse_note(make_text(cnpj_text="11.111.111/0001-11"))

    def test_number_mismatch_with_key(self):
        text = make_text().replace("Número: 45170", "Número: 99999")
        with self.assertRaisesRegex(nfce.NoteError, "número"):
            nfce.parse_note(text)

    def test_item_count_mismatch(self):
        with self.assertRaisesRegex(nfce.NoteError, "itens lidos"):
            nfce.parse_note(make_text(count=5))

    def test_total_mismatch(self):
        with self.assertRaisesRegex(nfce.NoteError, "somam"):
            nfce.parse_note(make_text(total="50,00"))

    def test_qty_times_price_mismatch(self):
        items = [("CAFE", "1", "2", "UND9", "10", "30,00")]
        with self.assertRaisesRegex(nfce.NoteError, "quantidade x preço"):
            nfce.parse_note(make_text(items, total="30,00", discount="", paid="30,00"))

    def test_unrecognized_item_chunk(self):
        text = make_text().replace("Qtd. total", "LIXO SEM FORMATO\nQtd. total")
        with self.assertRaisesRegex(nfce.NoteError, "não reconhecido"):
            nfce.parse_note(text)

    def test_browser_header_leaks_into_description(self):
        junk = "06/04/2026 https://sat.sef.sc.gov.br/consulta\n"
        # lixo entre itens cai na descrição do item seguinte
        with self.assertRaisesRegex(nfce.NoteError, "suspeita"):
            nfce.parse_note(make_text(between_items=junk))

    def test_overlong_description(self):
        items = [("X" * 130, "1", "1", "UND9", "10", "10,00")]
        with self.assertRaisesRegex(nfce.NoteError, "suspeita"):
            nfce.parse_note(make_text(items, total="10,00", discount="", paid="10,00"))


class SaveNoteTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.executescript(SCHEMA)
        self.note = nfce.parse_note(make_text())

    def test_save_and_idempotent(self):
        self.assertTrue(importer.save_note(self.conn, self.note, "a.pdf"))
        self.assertFalse(importer.save_note(self.conn, self.note, "copy.pdf"))
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM notes").fetchone()[0], 1)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM items").fetchone()[0], 3)
        self.assertEqual(self.conn.execute("SELECT source_file FROM notes").fetchone()[0], "a.pdf")

    def test_price_history_view(self):
        importer.save_note(self.conn, self.note, "a.pdf")
        row = self.conn.execute(
            "SELECT purchase_date, unit_price, price_per_kg FROM price_history WHERE product_code='14691'"
        ).fetchone()
        self.assertEqual(row, ("2026-10-02", 4.89, 4.89))


class FindPdfsTests(unittest.TestCase):
    def test_recursive_and_case_insensitive(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "sub").mkdir()
            for name in ["b.pdf", "sub/a.PDF", "c.txt"]:
                (root / name).write_text("x")
            found = [p.relative_to(root).as_posix() for p in importer.find_pdfs(root)]
            self.assertEqual(found, ["b.pdf", "sub/a.PDF"])


if __name__ == "__main__":
    unittest.main()
