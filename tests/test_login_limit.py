"""Bloqueio de tentativas de login: por IP, teto global e persistência no SQLite."""
import sqlite3
from unittest import mock

from pricetrail import db
from tests.api_case import TEST_PASSWORD, TEST_USER, ApiTestCase, item

WRONG = "senha errada"
START = 1_800_000_000
CLOUDFLARE = "172.70.1.1"


class LockoutTests(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.now = START
        patcher = mock.patch("pricetrail.login_limit.now", lambda: self.now)
        patcher.start()
        self.addCleanup(patcher.stop)

    def advance(self, minutes=0, seconds=0):
        self.now += minutes * 60 + seconds

    def attempt(self, ip, password=WRONG, client=None):
        client = client or self.anon_client()
        token = self.csrf_token(client)
        return client.post("/api/login", json={"username": TEST_USER, "password": password},
                           headers={"X-CSRF-Token": token, "X-Forwarded-For": ip})

    def fail(self, ip, times=1):
        for _ in range(times):
            self.assertEqual(self.attempt(ip).status_code, 401)

    def assertLocked(self, response, minutes):
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.get_json()["minutesLeft"], minutes)
        self.assertIn(f"{minutes} min", response.get_json()["error"])

    def test_tres_falhas_do_mesmo_ip_dao_429_mesmo_com_a_senha_certa(self):
        self.fail("203.0.113.5", times=3)
        self.assertLocked(self.attempt("203.0.113.5"), 20)
        self.advance(minutes=5, seconds=30)
        self.assertLocked(self.attempt("203.0.113.5", password=TEST_PASSWORD), 15)

    def test_outro_ip_continua_podendo_tentar(self):
        self.fail("203.0.113.5", times=3)
        self.assertEqual(self.attempt("198.51.100.7", password=TEST_PASSWORD).status_code, 200)

    def test_depois_de_20_minutos_o_ip_volta_a_tentar(self):
        self.fail("203.0.113.5", times=3)
        self.advance(minutes=19, seconds=59)
        self.assertLocked(self.attempt("203.0.113.5"), 1)
        self.advance(seconds=1)
        self.assertEqual(self.attempt("203.0.113.5", password=TEST_PASSWORD).status_code, 200)

    def test_falhas_espacadas_mais_de_20_minutos_nao_se_somam(self):
        self.fail("203.0.113.5", times=2)
        self.advance(minutes=20)
        response = self.attempt("203.0.113.5")
        self.assertEqual(response.status_code, 401)
        self.assertNotIn("lockMinutesIfWrong", response.get_json())

    def test_login_certo_zera_a_contagem_do_ip(self):
        self.fail("203.0.113.5", times=2)
        self.assertEqual(self.attempt("203.0.113.5", password=TEST_PASSWORD).status_code, 200)
        self.fail("203.0.113.5", times=2)
        self.assertEqual(self.attempt("203.0.113.5", password=TEST_PASSWORD).status_code, 200)

    def test_a_ultima_tentativa_avisa_os_minutos_de_bloqueio(self):
        for _ in range(2):
            response = self.attempt("203.0.113.5")
            self.assertEqual(response.status_code, 401)
            self.assertNotIn("lockMinutesIfWrong", response.get_json())
        response = self.attempt("203.0.113.5")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.get_json()["lockMinutesIfWrong"], 20)

    def test_teto_global_recusa_todos_ate_a_falha_mais_antiga_sair_da_janela(self):
        for n in range(9):
            self.fail(f"203.0.113.{n}")
            self.advance(minutes=1)
        # A décima falha bate o teto: o aviso é do teto global, mais longo que o bloqueio do IP.
        response = self.attempt("203.0.113.9")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.get_json()["lockMinutesIfWrong"], 24 * 60 - 9)
        # A primeira falha foi há 9 min: faltam 24h - 9 min para ela sair da janela.
        self.assertLocked(self.attempt("198.51.100.7", password=TEST_PASSWORD), 24 * 60 - 9)
        self.advance(minutes=24 * 60 - 10, seconds=59)
        self.assertLocked(self.attempt("198.51.100.7", password=TEST_PASSWORD), 1)
        self.advance(seconds=1)
        self.assertEqual(self.attempt("198.51.100.7", password=TEST_PASSWORD).status_code, 200)

    def test_bloqueio_persiste_entre_dois_apps_sobre_o_mesmo_banco(self):
        self.fail("203.0.113.5", times=3)
        # Cada attempt monta um create_app novo: o estado só pode vir do banco.
        self.assertLocked(self.attempt("203.0.113.5", password=TEST_PASSWORD), 20)

    @mock.patch("pricetrail.login_limit.MAX_TRACKED_IPS", 2)
    def test_teto_de_ips_rastreados_descarta_os_menos_ativos(self):
        self.fail("203.0.113.1", times=2)
        self.advance(seconds=1)
        self.fail("203.0.113.2")
        self.advance(seconds=1)
        self.fail("203.0.113.3")
        self.advance(seconds=1)
        # O .1 foi descartado ao entrar o .3: esta é a primeira falha dele, não a última.
        response = self.attempt("203.0.113.1")
        self.assertEqual(response.status_code, 401)
        self.assertNotIn("lockMinutesIfWrong", response.get_json())

    def test_x_forwarded_for_forjado_a_esquerda_nao_troca_o_ip(self):
        for forged in ("1.1.1.1", "2.2.2.2", "3.3.3.3"):
            self.fail(f"{forged}, 203.0.113.5, {CLOUDFLARE}")
        self.assertLocked(self.attempt(f"9.9.9.9, 203.0.113.5, {CLOUDFLARE}", password=TEST_PASSWORD), 20)


    def test_bloqueio_e_teto_global_saem_no_log_com_ip_e_user(self):
        with self.assertLogs("pricetrail.auth", "WARNING") as logs:
            for n in range(10):
                self.fail(f"203.0.113.{n}")
            self.attempt("198.51.100.7")
            self.attempt("198.51.100.8")
        events = [(r.event, r.ip, r.user) for r in logs.records if r.event != "login_falhou"]
        self.assertEqual(events, [
            ("teto_global_atingido", "203.0.113.9", TEST_USER),
            ("login_bloqueado", "198.51.100.7", TEST_USER),
            ("login_bloqueado", "198.51.100.8", TEST_USER),
        ])


class LockoutMigrationTests(ApiTestCase):
    def test_banco_na_versao_4_ganha_o_bloqueio_sem_perder_dados(self):
        with mock.patch.object(db, "MIGRATIONS", db.MIGRATIONS[:4]):
            self.add_note(item("10", description="DETERGENTE"))
        conn = sqlite3.connect(self.db)
        self.assertEqual(conn.execute("PRAGMA user_version").fetchone()[0], 4)
        conn.close()
        self.assertEqual([p["description"] for p in self.products()], ["DETERGENTE"])
        client = self.anon_client()
        for _ in range(3):
            self.login(client, password=WRONG)
        self.assertEqual(self.login(client).status_code, 429)
