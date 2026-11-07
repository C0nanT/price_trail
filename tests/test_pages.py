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
        for path in ("/static/import/app.js", "/static/common.js"):
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

    def test_import_tem_viewport_e_linka_o_css_unico_servido(self):
        body = self.html("/import")
        self.assertIn('name="viewport"', body)
        self.assertIn('href="/static/app.css"', body)
        self.assertNotIn("/static/import/style.css", body)
        response = self.client().get("/static/app.css")
        try:
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.get_data())
        finally:
            response.close()

    def test_import_tem_nav_com_as_tres_paginas_e_marca_a_atual(self):
        body = self.html("/import")
        nav = body[body.index("<nav"):body.index("</nav>")]
        for target in ('href="/"', 'href="/groups"', 'href="/import"'):
            self.assertIn(target, nav)
        self.assertEqual(nav.count('aria-current="page"'), 1)
        self.assertRegex(nav, r'href="/import"[^>]*aria-current="page"|aria-current="page"[^>]*href="/import"')

    def test_groups_tem_viewport_css_unico_e_nav_com_agrupar_atual(self):
        body = self.html("/groups")
        self.assertIn('name="viewport"', body)
        self.assertIn('href="/static/app.css"', body)
        self.assertNotIn("/static/group/style.css", body)
        nav = body[body.index("<nav"):body.index("</nav>")]
        for target in ('href="/"', 'href="/groups"', 'href="/import"'):
            self.assertIn(target, nav)
        self.assertEqual(nav.count('aria-current="page"'), 1)
        self.assertRegex(nav, r'href="/groups"[^>]*aria-current="page"|aria-current="page"[^>]*href="/groups"')

    def test_groups_tem_ancoras_das_secoes_e_barra_de_criar_grupo(self):
        body = self.html("/groups")
        for anchor in ("h-products", "h-draft", "h-suggestions", "h-groups", "h-stores"):
            self.assertIn(f'id="{anchor}"', body)
            self.assertIn(f'href="#{anchor}"', body)
        bar = body[body.index('id="selection-bar"'):]
        self.assertIn('id="create"', bar)
        self.assertIn('id="clear"', bar)
