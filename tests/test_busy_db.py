"""Banco ocupado: database is locked que estoura o busy_timeout vira 503 JSON com log de aviso."""
import sqlite3
from contextlib import closing
from unittest import mock

from pricetrail import db
from tests.api_case import ApiTestCase


class BusyDatabaseTest(ApiTestCase):
    def test_escrita_com_o_banco_travado_por_outra_conexao_responde_503_json(self):
        client = self.client()
        with closing(sqlite3.connect(self.db, isolation_level=None)) as other, \
                mock.patch.object(db, "BUSY_TIMEOUT_MS", 50):
            other.execute("BEGIN IMMEDIATE")
            with self.assertLogs("pricetrail", "WARNING") as logs:
                response = client.put("/api/stores/75315333", json={"store": "Atacadão", "category": "Mercado"})
            other.execute("ROLLBACK")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.get_json(), {"error": "Banco ocupado, tente de novo."})
        self.assertEqual(len(logs.records), 1)
        self.assertEqual(logs.records[0].levelname, "WARNING")

    def test_banco_liberado_volta_a_aceitar_a_escrita(self):
        client = self.client()
        with mock.patch.object(db, "BUSY_TIMEOUT_MS", 50):
            response = client.put("/api/stores/75315333", json={"store": "Atacadão", "category": "Mercado"})
        self.assertEqual(response.status_code, 200)
