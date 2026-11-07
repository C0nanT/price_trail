"""POST /api/import: o upload de PDFs pela página /import."""
import io
from unittest import mock

from pricetrail import importer
from pricetrail.server import create_app
from tests.api_case import ApiTestCase, item, note_text, note_url, run_cli
from tests.fixtures import make_key

UPLOAD_HEADERS = {"X-Pricetrail": "1"}
KEY = make_key(number=1)


class UploadTestCase(ApiTestCase):
    def upload(self, *files, headers=UPLOAD_HEADERS, client=None, signed=True):
        """Envia (nome, conteúdo) como a página envia: multipart com o campo files repetido.

        O conteúdo ganha a assinatura de PDF, que o falso pdftotext descarta.
        """
        prefix = "%PDF-" if signed else ""
        data = {"files": [(io.BytesIO((prefix + content).encode("utf-8")), name) for name, content in files]}
        return (client or self.client()).post("/api/import", data=data, headers=headers,
                                              content_type="multipart/form-data")

    def data_files(self):
        return sorted(p.relative_to(self.data).as_posix() for p in self.data.rglob("*") if p.is_file())


class UploadTests(UploadTestCase):
    def test_nota_nova_entra_com_nome_padronizado_e_link(self):
        response = self.upload(("compra.pdf", note_text(item("10"), number=1, issued="02/10/2026")))
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        (result,) = body["results"]
        self.assertEqual(result["status"], "NOVA")
        self.assertEqual(result["name"], "compra.pdf")
        self.assertEqual(result["access_key"], KEY)
        self.assertEqual(result["item_count"], 1)
        self.assertEqual(body["summary"], {"new": 1, "existing": 0, "error": 0})

        self.assertEqual(self.data_files(), [f"2026-10-02_{KEY}.pdf"])
        self.assertEqual(len(self.products()), 1)
        (note,) = self.catalog()["notes"]["75315333:10"]
        self.assertEqual(note["file"], "compra.pdf")
        self.assertEqual(note["href"], note_url(1))
        pdf = self.client().get(note["href"])
        self.assertEqual(pdf.status_code, 200)
        pdf.close()

    def test_erro_no_meio_nao_impede_os_outros_e_nao_fica_em_data(self):
        response = self.upload(
            ("a.pdf", note_text(item("10"), number=1)),
            ("ruim.pdf", "corrompido"),
            ("b.pdf", note_text(item("20"), number=2, issued="05/10/2026")),
        )
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual([(r["name"], r["status"]) for r in body["results"]],
                         [("a.pdf", "NOVA"), ("ruim.pdf", "ERRO"), ("b.pdf", "NOVA")])
        self.assertIn("pdftotext falhou", body["results"][1]["message"])
        self.assertEqual(body["summary"], {"new": 2, "existing": 0, "error": 1})
        self.assertEqual(self.data_files(), [f"2026-10-02_{KEY}.pdf", f"2026-10-05_{make_key(number=2)}.pdf"])
        self.assertEqual(len(self.products()), 2)

    def test_pasta_de_dados_ainda_inexistente_e_criada(self):
        self.data.rmdir()
        response = self.upload(("a.pdf", note_text(item("10"), number=1)))
        self.assertEqual(response.get_json()["results"][0]["status"], "NOVA")
        self.assertEqual(self.data_files(), [f"2026-10-02_{KEY}.pdf"])

    def test_reenvio_de_nota_com_pdf_e_ja_tem_sem_arquivo_novo(self):
        client = self.client()
        self.upload(("a.pdf", note_text(item("10"), number=1)), client=client)
        response = self.upload(("copia.pdf", note_text(item("10"), number=1)), client=client)
        (result,) = response.get_json()["results"]
        self.assertEqual(result["status"], "JÁ TEM")
        self.assertEqual(response.get_json()["summary"], {"new": 0, "existing": 1, "error": 0})
        self.assertEqual(self.data_files(), [f"2026-10-02_{KEY}.pdf"])
        (note,) = self.catalog()["notes"]["75315333:10"]
        self.assertEqual(note["file"], "a.pdf")

    def test_loja_sem_cadastro_sinalizada_uma_vez_por_envio(self):
        response = self.upload(("a.pdf", note_text(item("10"), number=1)),
                               ("b.pdf", note_text(item("20"), number=2)))
        flags = [(r["cnpj_root"], r["unregistered_store"]) for r in response.get_json()["results"]]
        self.assertEqual(flags, [("75315333", True), ("75315333", False)])

    def test_loja_cadastrada_nao_e_sinalizada(self):
        self.write_legacy("stores.json", {"75315333": {"store": "Atacadão", "category": "Mercado"}})
        response = self.upload(("a.pdf", note_text(item("10"))))
        self.assertFalse(response.get_json()["results"][0]["unregistered_store"])

    def test_pagina_import_envia_com_o_cabecalho_proprio(self):
        client = self.client()
        page = client.get("/import")
        self.assertEqual(page.status_code, 200)
        html = page.get_data(as_text=True)
        page.close()
        self.assertRegex(html, r'<input[^>]*type="file"[^>]*multiple[^>]*accept="[^"]*pdf')
        script = client.get("/static/import/app.js")
        self.assertEqual(script.status_code, 200)
        self.assertIn('"X-Pricetrail": "1"', script.get_data(as_text=True))
        script.close()

    def test_origin_do_proprio_servidor_e_aceito(self):
        for origin in ("http://localhost", "http://127.0.0.1:8000"):
            host = origin.removeprefix("http://")
            with self.subTest(origin=origin):
                response = self.upload(("a.pdf", note_text(item("10"))),
                                       headers={**UPLOAD_HEADERS, "Origin": origin, "Host": host})
                self.assertEqual(response.status_code, 200)

    def test_recusa_envio_de_outro_site(self):
        for headers in (
            {},
            {"X-Pricetrail": "0"},
            {**UPLOAD_HEADERS, "Origin": "http://evil.example"},
            {**UPLOAD_HEADERS, "Origin": "null"},
            {**UPLOAD_HEADERS, "Origin": "http://localhost:9999", "Host": "localhost:8000"},
            {**UPLOAD_HEADERS, "Host": "evil.example"},
        ):
            with self.subTest(headers=headers):
                response = self.upload(("a.pdf", note_text(item("10"))), headers=headers)
                self.assertEqual(response.status_code, 403)
        self.assertEqual(self.products(), [])
        self.assertEqual(self.data_files(), [])

    def test_sem_arquivos_ou_sem_multipart_retorna_422(self):
        client = self.client()
        for response in (
            self.upload(client=client),
            client.post("/api/import", data={"outro": "x"}, headers=UPLOAD_HEADERS,
                        content_type="multipart/form-data"),
            client.post("/api/import", json={"files": []}, headers=UPLOAD_HEADERS),
            client.post("/api/import", headers=UPLOAD_HEADERS),
        ):
            with self.subTest(request=response.request.content_type):
                self.assertEqual(response.status_code, 422)
                self.assertIn("PDF", response.get_json()["error"])

    def test_acima_de_20_mb_retorna_413(self):
        big = "x" * (20 * 1024 * 1024)
        response = self.upload(("grande.pdf", big))
        self.assertEqual(response.status_code, 413)
        self.assertIn("20 MB", response.get_json()["error"])
        self.assertEqual(self.data_files(), [])

    def test_upload_registra_no_mesmo_log_do_cli(self):
        log = self.root / "t.log"
        self.write_pdf("antiga.pdf", item("10"), number=1)
        self.import_data()  # o CLI grava em t.log
        client = create_app(self.db, self.data, self.legacy, log).test_client()
        self.upload(("ruim.pdf", "corrompido"), client=client)
        text = log.read_text(encoding="utf-8")
        self.assertIn("importação iniciada", text)
        self.assertRegex(text, r"\d{4}-\d{2}-\d{2} [\d:,]+ ERROR .*ruim\.pdf: pdftotext falhou")

    def test_serve_log_escolhe_o_arquivo(self):
        log = self.root / "servidor.log"

        def fake_run(app, **_kwargs):
            app.test_client().post("/api/import", data={"files": [(io.BytesIO(b"%PDF-corrompido"), "ruim.pdf")]},
                                   headers=UPLOAD_HEADERS, content_type="multipart/form-data")

        with mock.patch("flask.Flask.run", fake_run):
            code, _, _ = run_cli("serve", "--db", self.db, "--data", self.data, "--log", log)
        self.assertEqual(code, 0)
        self.assertIn("ruim.pdf: pdftotext falhou", log.read_text(encoding="utf-8"))

    def test_importacao_pela_pasta_ignora_temporario_de_upload(self):
        (self.data / ".tmpabc.upload").write_text(note_text(item("10"), number=1), encoding="utf-8")
        self.import_data()
        self.assertEqual(self.products(), [])


class UploadFileCaseTests(UploadTestCase):
    def test_nota_existente_sem_pdf_tem_arquivo_gravado_e_link_religado(self):
        self.add_note(item("10"), number=1, issued="02/10/2026")
        self.assertIsNone(self.catalog()["notes"]["75315333:10"][0]["href"])
        response = self.upload(("compra.pdf", note_text(item("10"), number=1, issued="02/10/2026")))
        (result,) = response.get_json()["results"]
        self.assertEqual(result["status"], "JÁ TEM")
        self.assertIn("PDF religado", result["message"])
        self.assertEqual(self.data_files(), [f"2026-10-02_{KEY}.pdf"])
        (note,) = self.catalog()["notes"]["75315333:10"]
        self.assertEqual(note["href"], note_url(1))

    def test_nota_existente_com_arquivo_ausente_tem_pdf_religado(self):
        client = self.client()
        self.upload(("a.pdf", note_text(item("10"), number=1)), client=client)
        (self.data / f"2026-10-02_{KEY}.pdf").unlink()
        self.assertIsNone(self.catalog()["notes"]["75315333:10"][0]["href"])
        (result,) = self.upload(("b.pdf", note_text(item("10"), number=1)), client=client).get_json()["results"]
        self.assertEqual(result["status"], "JÁ TEM")
        self.assertIn("PDF religado", result["message"])
        self.assertEqual(self.data_files(), [f"2026-10-02_{KEY}.pdf"])
        self.assertEqual(self.catalog()["notes"]["75315333:10"][0]["href"], note_url(1))

    def test_mesma_nota_duas_vezes_no_envio_grava_um_arquivo(self):
        response = self.upload(("a.pdf", note_text(item("10"), number=1)),
                               ("b.pdf", note_text(item("10"), number=1)))
        body = response.get_json()
        self.assertEqual([r["status"] for r in body["results"]], ["NOVA", "JÁ TEM"])
        self.assertEqual(body["summary"], {"new": 1, "existing": 1, "error": 0})
        self.assertNotIn("religado", body["results"][1].get("message") or "")
        self.assertEqual(self.data_files(), [f"2026-10-02_{KEY}.pdf"])

    def test_conteudo_sem_assinatura_de_pdf_e_recusado_sem_chamar_o_parser(self):
        response = self.upload(("texto.pdf", note_text(item("10"), number=1)), signed=False)
        (result,) = response.get_json()["results"]
        self.assertEqual(result["status"], "ERRO")
        self.assertEqual(result["message"], "não é um PDF")
        self.assertEqual(response.get_json()["summary"], {"new": 0, "existing": 0, "error": 1})
        self.assertEqual(self.pdftotext_calls, [])
        self.assertEqual(self.data_files(), [])
        self.assertEqual(self.products(), [])

    def test_nome_padronizado_ja_em_disco_nao_e_sobrescrito(self):
        existing = self.data / f"2026-10-02_{KEY}.pdf"
        existing.write_text("conteudo antigo", encoding="utf-8")
        response = self.upload(("a.pdf", note_text(item("10"), number=1)))
        self.assertEqual(response.get_json()["results"][0]["status"], "NOVA")
        self.assertEqual(existing.read_text(encoding="utf-8"), "conteudo antigo")
        self.assertEqual(self.data_files(), [f"2026-10-02_{KEY}.pdf"])

    def test_falha_inesperada_ao_gravar_um_arquivo_vira_erro_e_os_outros_seguem(self):
        real_save = importer.save_note

        def save_note(conn, note, source_file):
            if source_file == "quebra.pdf":
                raise OSError("disco cheio")
            return real_save(conn, note, source_file)

        with mock.patch("pricetrail.importer.save_note", save_note):
            response = self.upload(
                ("a.pdf", note_text(item("10"), number=1)),
                ("quebra.pdf", note_text(item("20"), number=2)),
                ("b.pdf", note_text(item("30"), number=3, issued="05/10/2026")),
            )
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual([(r["name"], r["status"]) for r in body["results"]],
                         [("a.pdf", "NOVA"), ("quebra.pdf", "ERRO"), ("b.pdf", "NOVA")])
        self.assertTrue(body["results"][1]["unexpected"])
        self.assertEqual(body["results"][1]["message"], "erro inesperado")
        self.assertEqual(body["summary"], {"new": 2, "existing": 0, "error": 1})
        self.assertEqual(self.data_files(), [f"2026-10-02_{KEY}.pdf", f"2026-10-05_{make_key(number=3)}.pdf"])

    def test_falha_inesperada_ao_mover_o_pdf_vira_erro_sem_temporario(self):
        with mock.patch("pathlib.Path.replace", side_effect=OSError("sem permissão")):
            response = self.upload(("a.pdf", note_text(item("10"), number=1)))
        self.assertEqual(response.status_code, 200)
        (result,) = response.get_json()["results"]
        self.assertEqual(result["status"], "ERRO")
        self.assertTrue(result["unexpected"])
        self.assertEqual(result["message"], "erro inesperado")
        self.assertEqual(self.data_files(), [])

    def test_mais_de_50_arquivos_por_envio_retorna_422(self):
        files = [(f"n{i}.pdf", note_text(item("10"), number=i + 1)) for i in range(51)]
        response = self.upload(*files)
        self.assertEqual(response.status_code, 422)
        self.assertIn("50", response.get_json()["error"])
        self.assertEqual(self.products(), [])
        self.assertEqual(self.data_files(), [])
