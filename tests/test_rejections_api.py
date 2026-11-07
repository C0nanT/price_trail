"""POST e DELETE /api/rejections e o efeito dos pares rejeitados nas sugestões."""
import sqlite3
import unittest

from pricetrail.db import MigrationError
from tests.api_case import ApiTestCase, item

A, B, C, D = (f"75315333:{n}" for n in (1, 2, 3, 4))


class RejectionTests(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.add_note(item("1"), item("2"), item("3"))
        self.web = self.client()

    def post(self, refs):
        return self.web.post("/api/rejections", json=refs)

    def delete(self, refs):
        return self.web.delete("/api/rejections", json=refs)

    def catalog_now(self):
        return self.web.get("/api/catalog").get_json()

    def suggestion_refs(self):
        return [s["refs"] for s in self.catalog_now()["suggestions"]]

    def test_sugestao_inicial_tem_os_tres(self):
        self.assertEqual(self.suggestion_refs(), [[A, B, C]])

    def test_rejeitar_todos_os_pares_da_sugestao_a_remove(self):
        self.assertEqual(self.post([A, B, C]).status_code, 200)
        self.assertEqual(self.suggestion_refs(), [])

    def test_um_par_so_nao_tira_ninguem_da_sugestao(self):
        self.post([A, B])
        self.assertEqual(self.suggestion_refs(), [[A, B, C]])

    def test_produto_sai_quando_todos_os_seus_pares_estao_rejeitados(self):
        self.post([C, A])
        self.post([B, C])
        self.assertEqual(self.suggestion_refs(), [[A, B]])

    def test_desfazer_faz_a_sugestao_voltar(self):
        self.post([A, B, C])
        self.assertEqual(self.delete([C, B, A]).status_code, 200)
        self.assertEqual(self.suggestion_refs(), [[A, B, C]])

    def test_rejeicoes_aparecem_no_catalogo_em_ordem_canonica_e_sem_duplicidade(self):
        self.post([B, A])
        self.post([A, B])
        self.assertEqual(self.catalog_now()["rejections"], [[A, B]])

    def test_resposta_traz_o_catalogo_atualizado(self):
        self.assertEqual(self.post([A, B, C]).get_json()["suggestions"], [])

    def test_lista_com_menos_de_duas_referencias_da_422(self):
        for refs in ([], [A], [A, A]):
            self.assertEqual(self.post(refs).status_code, 422, refs)

    def test_referencia_mal_formada_da_422_e_nada_muda(self):
        self.assertEqual(self.post([A, "DET.LIQ"]).status_code, 422)
        self.assertEqual(self.catalog_now()["rejections"], [])

    def test_corpo_que_nao_e_lista_de_texto_da_422(self):
        self.assertEqual(self.post({"refs": [A, B]}).status_code, 422)
        self.assertEqual(self.post([A, 3]).status_code, 422)

    def test_sem_json_e_recusado(self):
        response = self.web.post("/api/rejections", data="x", content_type="text/plain")
        self.assertEqual(response.status_code, 415)


class ThirdPartyTests(ApiTestCase):
    def test_par_rejeitado_nao_afeta_sugestao_com_terceiros(self):
        # 1 e 2 têm a mesma descrição; 3 tem uma parecida: sai "mesma descrição" {1,2} e "parecidas" {1,2,3}.
        self.add_note(item("1", "DETERGENTE YPE"), item("2", "DETERGENTE YPE"), item("3", "DETERGENTE YPE X"))
        web = self.client()
        self.assertEqual({tuple(s["refs"]) for s in web.get("/api/catalog").get_json()["suggestions"]},
                         {(A, B), (A, B, C)})
        web.post("/api/rejections", json=[A, B])
        refs = [s["refs"] for s in web.get("/api/catalog").get_json()["suggestions"]]
        self.assertEqual(refs, [[A, B, C]])


class RejectionMigrationTests(ApiTestCase):
    def test_arquivo_vira_todos_os_pares_de_cada_grupo(self):
        self.write_legacy("products.rejected.json", {"x": [C, A, B], "y": [D]})
        self.add_note(item("1"), item("2"), item("3"))
        self.assertEqual(self.catalog()["rejections"], [[A, B], [A, C], [B, C]])
        self.assertEqual(self.catalog()["suggestions"], [])

    def test_carga_roda_uma_vez_e_catalogo_nao_le_mais_o_json(self):
        self.add_note(item("1"), item("2"), item("3"))
        web = self.client()
        self.write_legacy("products.rejected.json", {"x": [A, B, C]})
        data = web.get("/api/catalog").get_json()
        self.assertEqual(data["rejections"], [])
        self.assertEqual(len(data["suggestions"]), 1)

    def test_banco_na_versao_2_recebe_a_carga_ao_abrir(self):
        self.add_note(item("1"), item("2"))
        conn = sqlite3.connect(self.db)
        conn.execute("DROP TABLE rejected_pairs")
        conn.execute("DROP INDEX group_refs_group_id")
        conn.execute("PRAGMA user_version = 2")
        conn.commit()
        conn.close()
        self.write_legacy("products.rejected.json", {"x": [A, B]})
        self.assertEqual(self.catalog()["rejections"], [[A, B]])

    def test_referencia_mal_formada_aborta_a_migracao(self):
        self.write_legacy("products.rejected.json", {"x": ["DET.LIQ", A]})
        with self.assertRaises(MigrationError):
            self.client()


if __name__ == "__main__":
    unittest.main()
