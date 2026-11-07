"""Páginas estáticas: respondem 200 e têm links entre si."""
from tests.api_case import ApiTestCase


class PagesTest(ApiTestCase):
    def html(self, path):
        response = self.client().get(path)
        try:
            self.assertEqual(response.status_code, 200, path)
            return response.get_data(as_text=True)
        finally:
            response.close()

    def test_paginas_e_estaticos_do_import_respondem_200(self):
        self.html("/import")
        for path in ("/static/import/app.js", "/static/import/style.css", "/static/common.js"):
            response = self.client().get(path)
            self.assertEqual(response.status_code, 200, path)
            response.close()

    def test_grafico_groups_e_import_tem_links_entre_si(self):
        for page, targets in (
            ("/", ('href="/groups"', 'href="/import"')),
            ("/groups", ('href="/"', 'href="/import"')),
            ("/import", ('href="/"', 'href="/groups"')),
        ):
            body = self.html(page)
            for target in targets:
                self.assertIn(target, body, (page, target))

    def test_import_liga_para_a_secao_de_lojas_do_groups(self):
        self.assertIn('id="h-stores"', self.html("/groups"))
        self.assertIn('href="/groups#h-stores"', self.html("/import"))
