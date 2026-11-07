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


    def test_grafico_tem_viewport_css_unico_e_nav_com_o_grafico_marcado(self):
        body = self.html("/")
        self.assertIn('name="viewport"', body)
        self.assertIn('href="/static/app.css"', body)
        self.assertNotIn("/static/chart/style.css", body)
        nav = body[body.index("<nav"):body.index("</nav>")]
        for target in ('href="/"', 'href="/groups"', 'href="/import"'):
            self.assertIn(target, nav)
        self.assertEqual(nav.count('aria-current="page"'), 1)
        self.assertRegex(nav, r'href="/"[^>]*aria-current="page"|aria-current="page"[^>]*href="/"')

    def test_grafico_deixa_busca_e_produto_fora_do_painel_de_filtros(self):
        body = self.html("/")
        panel = body[body.index("<details"):body.index("</details>")]
        self.assertIn("Filtros", panel)
        for outside in ('id="search"', 'id="product"'):
            self.assertIn(outside, body)
            self.assertNotIn(outside, panel)
        for inside in ('id="category"', 'id="store"', 'id="from"', 'id="to"', 'id="sort"'):
            self.assertIn(inside, panel)

    def test_grafico_preco_atual_abre_teclado_numerico_e_veredito_e_aria_live(self):
        body = self.html("/")
        self.assertRegex(body, r'id="current"[^>]*inputmode="decimal"')
        self.assertRegex(body, r'id="verdict"[^>]*aria-live="polite"')
        self.assertLess(body.index('id="verdict"'), body.index('id="chart"'))

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

    def test_grafico_serve_elementos_que_o_js_usa_e_tabela_com_as_cinco_colunas(self):
        body = self.html("/")
        for hook in ('id="chart"', 'id="tooltip"', 'id="cards"', 'id="rows"'):
            self.assertIn(hook, body)
        table = body[body.index("<table"):body.index("</table>")]
        for column in ("Data", "Loja", "Preço", "Quantidade", "Total"):
            self.assertIn(f">{column}</th>", table)
