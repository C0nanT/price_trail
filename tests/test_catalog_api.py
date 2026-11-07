"""GET /api/catalog e a rota de PDF: os dados da página de agrupamento."""
import sqlite3
import unittest

from pricetrail.db import MigrationError, SCHEMA, connect
from tests.api_case import ApiTestCase, item, note_url
from tests.fixtures import make_key

REF = "75315333:10"
FILIAL = {"cnpj": "75315333000199", "cnpj_text": "75.315.333/0001-99"}


class CatalogTests(ApiTestCase):
    def test_formato_igual_ao_do_data_js(self):
        self.write_legacy("stores.json", {"75315333": {"store": "Atacadão", "category": "Mercado"}})
        self.write_legacy("products.json", {"Detergente": [REF]})
        self.write_pdf("a.pdf", item("10", price="5,00"), number=7)
        self.import_data()
        self.assertEqual(self.catalog(), {
            "products": [{
                "ref": REF, "code": "10", "description": "DET YPE", "unit": "UND",
                "store": "Atacadão", "purchases": 1, "min": 5.0, "max": 5.0,
            }],
            "suggestions": [],
            "rejections": [],
            "groups": {"Detergente": [REF]},
            "notes": {REF: [{
                "date": "2026-10-02", "number": 7, "file": "a.pdf", "href": note_url(7),
                "quantity": 1.0, "price": 5.0,
            }]},
        })

    def test_um_produto_por_referencia_com_a_descricao_mais_recente(self):
        self.add_note(item("10", "DET YPE", price="2,00"), number=1, issued="01/01/2026")
        self.add_note(item("10", "DET YPE NOVO", price="3,00"), number=2, issued="01/05/2026")
        (product,) = self.catalog()["products"]
        self.assertEqual(product["description"], "DET YPE NOVO")
        self.assertEqual((product["min"], product["max"], product["purchases"]), (2.0, 3.0, 2))

    def test_unidades_do_mesmo_codigo_aparecem_juntas(self):
        self.add_note(item("10", unit="UND9"), number=1, issued="01/01/2026")
        self.add_note(item("10", unit="KG9"), number=2, issued="01/05/2026")
        self.assertEqual([p["unit"] for p in self.catalog()["products"]], ["UND/KG"])

    def test_duas_filiais_viram_uma_referencia_e_nao_uma_sugestao(self):
        self.add_note(item("10"), number=1)
        self.add_note(item("10"), number=2, **FILIAL)
        data = self.catalog()
        self.assertEqual([(p["ref"], p["purchases"]) for p in data["products"]], [(REF, 2)])
        self.assertEqual(data["suggestions"], [])
        self.assertEqual(len(data["notes"][REF]), 2)

    def test_loja_sem_cadastro_fica_com_o_nome_da_nota(self):
        self.add_note(item("10"))
        self.assertEqual(self.catalog()["products"][0]["store"], "ATACADAO S.A.")

    def test_grupos_vem_do_banco_e_nao_do_json(self):
        self.write_legacy("products.json", {"B": ["75315333:2", "75315333:1"], "A": ["75315333:3"]})
        self.add_note(item("1"))
        expected = {"B": ["75315333:2", "75315333:1"], "A": ["75315333:3"]}
        self.assertEqual(self.catalog()["groups"], expected)
        self.write_legacy("products.json", {"Outro": ["75315333:1"]})
        self.assertEqual(self.catalog()["groups"], expected)

    def test_sugere_mesma_descricao_com_codigos_diferentes(self):
        self.add_note(item("1", "DET YPE"), item("2", "DET YPE"))
        self.assertEqual(self.catalog()["suggestions"], [{
            "name": "DET YPE", "reason": "mesma descrição",
            "refs": ["75315333:1", "75315333:2"], "warnings": [],
        }])

    def test_sugestao_com_aviso_de_preco_e_unidade(self):
        self.add_note(item("1", "QJO", unit="UND9", price="2,00"), item("2", "QJO", unit="KG9", price="4,00"))
        self.assertEqual(self.catalog()["suggestions"][0]["warnings"],
                         ["unidades diferentes", "preços muito diferentes (2.00 a 4.00)"])

    def test_mesmo_codigo_com_duas_unidades_ou_descricoes_nao_vira_sugestao(self):
        self.add_note(item("1", "DETERGENTE YPE NEUTRO", unit="UND9"), number=1)
        self.add_note(item("1", "DETERGENTE YPE NEUTRO", unit="KG9"), number=2)
        self.add_note(item("1", "DETERGENTE YPE NEUTRA"), number=3)
        self.assertEqual(self.catalog()["suggestions"], [])

    def test_sugestao_lista_cada_referencia_uma_vez(self):
        self.add_note(item("1", "QJO", unit="UND9"), item("2", "QJO"), number=1)
        self.add_note(item("1", "QJO", unit="KG9"), number=2)
        (suggestion,) = self.catalog()["suggestions"]
        self.assertEqual(suggestion["refs"], ["75315333:1", "75315333:2"])

    def test_banco_vazio(self):
        self.assertEqual(self.catalog(), {"products": [], "suggestions": [], "groups": {}, "notes": {}, "rejections": []})

    def test_recusa_outro_host(self):
        response = self.client().get("/api/catalog", headers={"Host": "evil.example"})
        self.assertEqual(response.status_code, 403)


class PdfRouteTests(ApiTestCase):
    def test_entrega_o_pdf_da_nota(self):
        pdf = self.write_pdf("a.pdf", item("10"))
        self.import_data()
        response = self.client().get(note_url())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "application/pdf")
        self.assertEqual(response.get_data(), pdf.read_bytes())
        response.close()

    def test_arquivo_apagado_da_404_e_link_nulo(self):
        pdf = self.write_pdf("a.pdf", item("10"))
        self.import_data()
        self.assertEqual(self.href(REF), note_url())
        pdf.unlink()
        self.assertIsNone(self.href(REF))
        self.assertEqual(self.client().get(note_url()).status_code, 404)

    def test_nota_sem_caminho_gravado_da_404_e_link_nulo(self):
        self.add_note(item("10"))
        self.assertIsNone(self.href(REF))
        self.assertEqual(self.client().get(note_url()).status_code, 404)

    def test_chave_valida_de_nota_desconhecida_da_404(self):
        self.assertEqual(self.client().get(note_url(99)).status_code, 404)

    def test_recusa_chave_que_nao_tem_44_digitos(self):
        self.write_pdf("a.pdf", item("10"))
        self.import_data()
        client = self.client()
        key = make_key(number=1)
        for bad in (key[:-1], key + "0", key[:-1] + "x", "٣" * 44, "..", "%2e%2e%2fa"):
            with self.subTest(key=bad):
                self.assertEqual(client.get(f"/notes/{bad}.pdf").status_code, 404)

    def test_recusa_outro_host(self):
        self.write_pdf("a.pdf", item("10"))
        self.import_data()
        self.assertEqual(self.client().get(note_url(), headers={"Host": "evil.example"}).status_code, 403)

    def corrupt_source_path(self, source_path):
        conn = connect(self.db)
        with conn:
            conn.execute("UPDATE notes SET source_path = ?", (source_path,))
        conn.close()

    def test_caminho_gravado_fora_da_pasta_de_dados_nao_e_entregue(self):
        secret = self.root / "segredo.pdf"
        secret.write_text("segredo")
        self.write_pdf("a.pdf", item("10"))
        self.import_data()
        for path in ("../segredo.pdf", str(secret), "sub/../../segredo.pdf"):
            with self.subTest(path=path):
                self.corrupt_source_path(path)
                self.assertEqual(self.client().get(note_url()).status_code, 404)
                self.assertIsNone(self.href(REF))

    def test_link_simbolico_para_fora_da_pasta_de_dados_nao_e_entregue(self):
        secret = self.root / "segredo.pdf"
        secret.write_text("segredo")
        pdf = self.write_pdf("a.pdf", item("10"))
        self.import_data()
        pdf.unlink()
        pdf.symlink_to(secret)
        self.assertEqual(self.client().get(note_url()).status_code, 404)
        self.assertIsNone(self.href(REF))

    def test_nenhum_request_executa_pdftotext(self):
        self.write_pdf("a.pdf", item("10"), item("11"))
        self.import_data()
        client = self.client()
        self.pdftotext_calls.clear()
        for path in ("/api/catalog", "/api/products", note_url(), "/groups", "/"):
            with self.subTest(path=path):
                response = client.get(path)
                self.assertEqual(response.status_code, 200)
                response.close()
        self.assertEqual(self.pdftotext_calls, [])


class ReimportTests(ApiTestCase):
    def assert_serves(self, pdf):
        self.assertEqual(self.href(REF), note_url())
        response = self.client().get(note_url())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_data(), pdf.read_bytes())
        response.close()

    def test_renomear_e_reimportar_mantem_o_link(self):
        pdf = self.write_pdf("a.pdf", item("10"))
        self.import_data()
        renamed = pdf.rename(self.data / "b.pdf")
        self.assertIsNone(self.href(REF))
        self.import_data()
        self.assert_serves(renamed)

    def test_mover_para_subpasta_e_reimportar_mantem_o_link(self):
        pdf = self.write_pdf("a.pdf", item("10"))
        self.import_data()
        (self.data / "2026 out").mkdir()
        moved = pdf.rename(self.data / "2026 out" / "a.pdf")
        self.import_data()
        self.assert_serves(moved)

    def test_nome_antigo_ocupado_por_outra_nota_nao_confunde_o_link(self):
        pdf = self.write_pdf("a.pdf", item("10"), number=1)
        self.import_data()
        renamed = pdf.rename(self.data / "b.pdf")
        other = self.write_pdf("a.pdf", item("20"), number=2)
        self.import_data()
        self.assert_serves(renamed)
        response = self.client().get(note_url(2))
        self.assertEqual(response.get_data(), other.read_bytes())
        response.close()

    def test_importar_so_uma_subpasta_grava_o_caminho_relativo_a_pasta_de_dados(self):
        pdf = self.write_pdf("2026/a.pdf", item("10"))
        self.import_data(self.data / "2026")
        self.assert_serves(pdf)

    def test_nota_antiga_sem_caminho_ganha_link_ao_reimportar(self):
        self.add_note(item("10"))
        pdf = self.write_pdf("a.pdf", item("10"))
        self.import_data()
        self.assert_serves(pdf)

    def test_copia_fora_da_pasta_de_dados_avisa_e_nao_perde_o_link(self):
        pdf = self.write_pdf("a.pdf", item("10"))
        self.import_data()
        outside = self.root / "fora"
        outside.mkdir()
        (outside / "a.pdf").write_bytes(pdf.read_bytes())
        self.assertIn("fora da pasta de dados", self.import_data(outside))
        self.assert_serves(pdf)


class SourcePathMigrationTests(ApiTestCase):
    def build_version_0(self, *notes):
        """Banco de antes das migrações, com (número, arquivo de origem) de cada nota."""
        conn = sqlite3.connect(self.db)
        conn.executescript(SCHEMA)
        for number, source_file in notes:
            conn.execute(
                "INSERT INTO notes VALUES (?, '75315333029000', 'ATACADAO S.A.', 'RUA', ?, 528,"
                " '2026-10-02T19:53:38', 1, 500, 0, 500, ?)",
                (make_key(number=number), number, source_file),
            )
            conn.execute(
                "INSERT INTO items VALUES (?, 1, ?, 'DET YPE', 1.0, 'UND9', 'UND', 5.0, NULL, 500)",
                (make_key(number=number), str(number)),
            )
        conn.commit()
        conn.close()

    def href_of(self, number):
        return self.href(f"75315333:{number}")

    def test_acha_o_pdf_pela_chave_mesmo_renomeado(self):
        self.build_version_0((1, "original.pdf"))
        pdf = self.write_pdf("sub/renomeado.pdf", item("1"), number=1)
        self.assertEqual(self.href_of(1), note_url(1))
        response = self.client().get(note_url(1))
        self.assertEqual(response.get_data(), pdf.read_bytes())
        response.close()

    def test_sem_chave_legivel_acha_pelo_nome(self):
        self.build_version_0((1, "a.pdf"))
        (self.data / "a.pdf").write_text("texto sem chave de acesso")
        self.assertEqual(self.href_of(1), note_url(1))

    def test_pdf_de_outra_nota_com_o_mesmo_nome_nao_serve_de_fallback(self):
        self.build_version_0((1, "a.pdf"))
        self.write_pdf("a.pdf", item("2"), number=2)
        self.assertIsNone(self.href_of(1))

    def test_nota_sem_pdf_fica_sem_link(self):
        self.build_version_0((1, "a.pdf"), (2, "b.pdf"))
        self.write_pdf("a.pdf", item("1"), number=1)
        self.assertEqual(self.href_of(1), note_url(1))
        self.assertIsNone(self.href_of(2))

    def test_le_cada_pdf_uma_vez_so_e_nunca_mais(self):
        self.build_version_0((1, "a.pdf"))
        self.write_pdf("a.pdf", item("1"), number=1)
        self.write_pdf("b.pdf", item("2"), number=2)
        client = self.client()
        self.assertEqual(len(self.pdftotext_calls), 2)
        self.pdftotext_calls.clear()
        client.get("/api/catalog")
        self.client()
        connect(self.db, self.data).close()
        self.assertEqual(self.pdftotext_calls, [])

    def test_pdftotext_quebrado_num_arquivo_nao_aborta_a_carga(self):
        self.build_version_0((1, "a.pdf"), (2, "b.pdf"))
        self.write_pdf("a.pdf", item("1"), number=1)
        (self.data / "b.pdf").write_text("corrompido")
        self.assertEqual(self.href_of(1), note_url(1))

    def assert_refuses_without_data(self, data_dir):
        with self.assertRaises(MigrationError) as caught:
            connect(self.db, data_dir)
        self.assertIn("pasta de dados", str(caught.exception))
        # Nada foi aplicado: com a pasta certa, a carga inteira roda.
        self.write_pdf("a.pdf", item("1"), number=1)
        self.assertEqual(self.href_of(1), note_url(1))

    def test_banco_com_notas_sem_pasta_informada_nao_migra(self):
        self.build_version_0((1, "a.pdf"))
        self.assert_refuses_without_data(None)

    def test_banco_com_notas_e_pasta_inexistente_nao_migra(self):
        self.build_version_0((1, "a.pdf"))
        self.assert_refuses_without_data(self.root / "nao-existe")

    def test_banco_sem_notas_migra_sem_pasta(self):
        connect(self.db).close()
        self.assertEqual(self.catalog()["notes"], {})


if __name__ == "__main__":
    unittest.main()
