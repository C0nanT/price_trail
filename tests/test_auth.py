"""Login de usuário único: sessão, CSRF, controle de acesso e eventos de log."""
import io
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from unittest import mock
from urllib.parse import parse_qs, urlsplit

from pricetrail import logs
from tests.api_case import TEST_PASSWORD, TEST_USER, ApiTestCase, run_cli


class AccessTests(ApiTestCase):
    def test_pagina_sem_sessao_redireciona_para_o_login_com_next(self):
        client = self.anon_client()
        for path, expected in (("/", "/"), ("/lista", "/lista"), ("/groups?x=1&y=2", "/groups?x=1&y=2")):
            with self.subTest(path=path):
                response = client.get(path)
                self.assertEqual(response.status_code, 302)
                location = urlsplit(response.headers["Location"])
                self.assertEqual(location.path, "/login")
                self.assertEqual(parse_qs(location.query)["next"], [expected])

    def test_api_e_notes_sem_sessao_respondem_401(self):
        client = self.anon_client()
        for method, path in (("GET", "/api/products"), ("GET", "/api/catalog"), ("PUT", "/api/groups"),
                             ("POST", "/api/import"), ("GET", "/notes/" + "1" * 44 + ".pdf")):
            with self.subTest(path=path):
                response = client.open(path, method=method)
                self.assertEqual(response.status_code, 401)
                self.assertIn("error", response.get_json())

    def test_rotas_livres_sem_sessao(self):
        client = self.anon_client()
        for path in ("/login", "/api/session", "/health", "/static/app.css", "/static/common.js",
                     "/static/login/app.js"):
            with self.subTest(path=path):
                response = client.get(path)
                self.assertEqual(response.status_code, 200)
                response.close()

    def test_cliente_logado_acessa_paginas_e_api(self):
        client = self.client()
        self.assertEqual(client.get("/api/products").status_code, 200)
        response = client.get("/lista")
        self.assertEqual(response.status_code, 200)
        response.close()


class PagesTests(ApiTestCase):
    def test_cada_pagina_tem_sair_e_carrega_o_script_comum(self):
        client = self.client()
        for path in ("/", "/groups", "/import", "/lista"):
            with self.subTest(path=path):
                response = client.get(path)
                body = response.get_data(as_text=True)
                response.close()
                self.assertRegex(body, r"<button[^>]*data-logout[^>]*>Sair</button>")
                self.assertIn('src="/static/common.js"', body)

    def test_pagina_de_login_tem_formulario_e_script(self):
        response = self.anon_client().get("/login")
        body = response.get_data(as_text=True)
        response.close()
        for hook in ('id="username"', 'type="password"', 'src="/static/login/app.js"', 'href="/static/app.css"'):
            self.assertIn(hook, body)


class LoginTests(ApiTestCase):
    def test_login_certo_grava_a_sessao_e_devolve_o_next(self):
        client = self.anon_client()
        response = self.login(client, next="/lista?x=1")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["next"], "/lista?x=1")
        self.assertEqual(client.get("/api/products").status_code, 200)
        self.assertTrue(client.get("/api/session").get_json()["loggedIn"])

    @mock.patch("pricetrail.login_limit.GLOBAL_MAX_FAILURES", 100)  # todo login conta no teto global de 10
    def test_next_externo_ou_ausente_vira_a_raiz(self):
        for next in (None, "", "//evil.com", "//evil.com/lista", "https://evil.com/", "http:/evil.com",
                     "/\\evil.com", "lista", "javascript:alert(1)", "/a\nb", 5):
            with self.subTest(next=next):
                response = self.login(self.anon_client(), next=next)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.get_json()["next"], "/")

    def test_usuario_errado_e_senha_errada_dao_a_mesma_resposta_401(self):
        responses = [
            # Um IP por tentativa: a terceira falha do mesmo IP já viria com o aviso de bloqueio.
            self.login(self.anon_client("203.0.113.1"), username="outro"),
            self.login(self.anon_client("203.0.113.2"), password="errada"),
            self.login(self.anon_client("203.0.113.3"), username="outro", password="errada"),
            self.login(self.anon_client("203.0.113.4"), username=None, password=None),
        ]
        for response in responses:
            self.assertEqual(response.status_code, 401)
        self.assertEqual({response.get_data() for response in responses}, {responses[0].get_data()})

    def test_login_errado_nao_abre_a_sessao(self):
        client = self.anon_client()
        self.login(client, password="errada")
        self.assertEqual(client.get("/api/products").status_code, 401)
        self.assertFalse(client.get("/api/session").get_json()["loggedIn"])

    def test_csrf_ausente_ou_errado_no_login_da_403(self):
        client = self.anon_client()
        self.csrf_token(client)
        no_header = client.post("/api/login", json={"username": TEST_USER, "password": TEST_PASSWORD})
        self.assertEqual(no_header.status_code, 403)
        self.assertEqual(self.login(client, token="errado").status_code, 403)
        # Sem sessão nenhuma (nunca buscou o token), um token qualquer também não vale.
        self.assertEqual(self.login(self.anon_client(), token="qualquer").status_code, 403)
        self.assertEqual(client.get("/api/products").status_code, 401)

    def test_cookie_da_sessao_e_httponly_secure_lax_e_dura_30_dias(self):
        response = self.login(self.anon_client())
        (cookie,) = [value for value in response.headers.getlist("Set-Cookie") if value.startswith("session=")]
        attributes = {part.strip().split("=")[0].lower(): part.strip() for part in cookie.split(";")[1:]}
        self.assertIn("httponly", attributes)
        self.assertIn("secure", attributes)
        self.assertEqual(attributes["samesite"].lower(), "samesite=lax")
        expires = parsedate_to_datetime(attributes["expires"].split("=", 1)[1])
        lifetime = expires - datetime.now(timezone.utc)
        self.assertLess(abs(lifetime - timedelta(days=30)), timedelta(minutes=1))


class LogoutTests(ApiTestCase):
    def test_logout_encerra_a_sessao(self):
        client = self.client()
        response = client.post("/api/logout", headers={"X-CSRF-Token": self.csrf_token(client)})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(client.get("/api/products").status_code, 401)
        self.assertEqual(client.get("/lista").status_code, 302)

    def test_logout_sem_csrf_ou_com_csrf_errado_da_403_e_mantem_a_sessao(self):
        client = self.client()
        self.assertEqual(client.post("/api/logout").status_code, 403)
        self.assertEqual(client.post("/api/logout", headers={"X-CSRF-Token": "errado"}).status_code, 403)
        self.assertEqual(client.get("/api/products").status_code, 200)


class OriginTests(ApiTestCase):
    def test_post_put_delete_com_origin_de_outro_site_da_403(self):
        client = self.client()
        for origin in ("http://evil.example", "null", "https://localhost", "http://localhost:9999"):
            for method, path, body in (("PUT", "/api/groups", {}), ("POST", "/api/rejections", {}),
                                       ("DELETE", "/api/rejections", {}), ("PUT", "/api/stores/75315333", {})):
                with self.subTest(origin=origin, method=method, path=path):
                    response = client.open(path, method=method, json=body, headers={"Origin": origin})
                    self.assertEqual(response.status_code, 403)

    def test_login_com_origin_de_outro_site_da_403(self):
        client = self.anon_client()
        token = self.csrf_token(client)
        response = client.post("/api/login", json={"username": TEST_USER, "password": TEST_PASSWORD},
                               headers={"X-CSRF-Token": token, "Origin": "http://evil.example"})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(client.get("/api/products").status_code, 401)

    def test_origin_do_proprio_site_ou_ausente_passa(self):
        client = self.client()
        for headers in ({}, {"Origin": "http://localhost"}):
            with self.subTest(headers=headers):
                response = client.put("/api/groups", json={}, headers=headers)
                self.assertEqual(response.status_code, 200)


class StartupTests(ApiTestCase):
    def test_sem_credenciais_o_servidor_nao_sobe_e_diz_o_que_falta(self):
        for name in ("AUTH_USERNAME", "AUTH_PASSWORD_HASH", "SECRET_KEY"):
            with self.subTest(name=name), mock.patch.dict(os.environ, {name: ""}), \
                    mock.patch("flask.Flask.run") as run:
                code, out, err = run_cli("serve", "--db", self.db, "--data", self.data)
                self.assertEqual(code, 2)
                self.assertIn(name, err)
                run.assert_not_called()

    def test_hash_que_nao_e_argon2_nao_sobe(self):
        with mock.patch.dict(os.environ, {"AUTH_PASSWORD_HASH": "senha-em-texto"}), mock.patch("flask.Flask.run"):
            code, _, err = run_cli("serve", "--db", self.db, "--data", self.data)
        self.assertEqual(code, 2)
        self.assertIn("AUTH_PASSWORD_HASH", err)
        self.assertNotIn("senha-em-texto", err)


class HashPasswordTests(ApiTestCase):
    def test_hash_gerado_e_aceito_no_login(self):
        with mock.patch("getpass.getpass", side_effect=["outra senha", "outra senha"]):
            code, out, _ = run_cli("hash-password")
        self.assertEqual(code, 0)
        with mock.patch.dict(os.environ, {"AUTH_PASSWORD_HASH": out.strip()}):
            client = self.anon_client()
        self.assertEqual(self.login(client, password="outra senha").status_code, 200)
        self.assertNotIn("outra senha", out)

    def test_senhas_diferentes_ou_vazias_nao_geram_hash(self):
        for typed in (["a", "b"], ["", ""]):
            with self.subTest(typed=typed), mock.patch("getpass.getpass", side_effect=typed):
                code, out, err = run_cli("hash-password")
            self.assertEqual(code, 2)
            self.assertEqual(out, "")
            self.assertTrue(err)


class LoginLogTests(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.stream = io.StringIO()
        handler = logging.StreamHandler(self.stream)
        handler.setFormatter(logs.JsonFormatter())
        log = logging.getLogger("pricetrail.auth")
        log.addHandler(handler)
        self.addCleanup(log.removeHandler, handler)
        self.addCleanup(log.setLevel, log.level)
        log.setLevel(logging.INFO)

    def events(self):
        return [json.loads(line) for line in self.stream.getvalue().splitlines()]

    def test_eventos_de_login_e_logout_em_json_com_ip_e_user_sem_senha(self):
        client = self.anon_client()
        self.login(client, password="senha errada digitada")
        self.login(client, username="senha no campo errado", password="x")
        self.login(client)
        client.post("/api/logout", headers={"X-CSRF-Token": self.csrf_token(client)})
        events = self.events()
        self.assertEqual([event["event"] for event in events], ["login_falhou", "login_falhou", "login_ok", "logout"])
        self.assertEqual([event["user"] for event in events], [TEST_USER, "desconhecido", TEST_USER, TEST_USER])
        for event in events:
            self.assertEqual(event["ip"], "127.0.0.1")
        everything = self.stream.getvalue()
        for secret in ("senha errada digitada", "senha no campo errado", TEST_PASSWORD):
            self.assertNotIn(secret, everything)
