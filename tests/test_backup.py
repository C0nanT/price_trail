import json
import os
import sqlite3
from datetime import datetime
from unittest import mock

from pricetrail import backup
from tests.api_case import ApiTestCase, item, run_cli


class BackupTest(ApiTestCase):
    def backups(self):
        return sorted(p.name for p in (self.db.parent / "backups").iterdir())

    def test_backup_integro_com_o_que_so_estava_no_wal(self):
        self.add_note(item("1", "ARROZ"))
        # Conexão aberta mantém o -wal sem checkpoint, como o servidor rodando.
        live = sqlite3.connect(self.db)
        live.execute("PRAGMA wal_autocheckpoint = 0")
        live.execute("CREATE TABLE extra (x)")
        live.execute("INSERT INTO extra VALUES (42)")
        live.commit()
        self.assertGreater(os.path.getsize(str(self.db) + "-wal"), 0)
        code, _, _ = run_cli("backup", "--db", self.db)
        live.close()
        self.assertEqual(code, 0)
        (name,) = self.backups()
        self.assertRegex(name, r"^app-\d{8}-\d{6}\.db$")
        copy = sqlite3.connect(self.db.parent / "backups" / name)
        self.assertEqual(copy.execute("PRAGMA integrity_check").fetchone()[0], "ok")
        self.assertEqual(copy.execute("SELECT x FROM extra").fetchone()[0], 42)
        copy.close()

    def test_log_json_so_com_nome_tamanho_apagados_e_duracao(self):
        self.add_note(item("1"))
        _, out, _ = run_cli("backup", "--db", self.db)
        event = json.loads(out.strip().splitlines()[-1])
        self.assertEqual(set(event) - {"ts", "level", "logger"}, {"msg", "file", "bytes", "deleted", "seconds"})
        self.assertEqual(event["file"], self.backups()[0])
        self.assertEqual(event["deleted"], 0)

    def test_mantem_so_os_n_mais_novos(self):
        self.add_note(item("1"))
        for second in (1, 2, 3):
            backup.run_backup(self.db, keep=2, now=datetime(2026, 1, 1, 0, 0, second))
        self.assertEqual(self.backups(), ["app-20260101-000002.db", "app-20260101-000003.db"])

    def test_backup_keep_do_ambiente_e_nao_mexe_em_outros_arquivos(self):
        self.add_note(item("1"))
        folder = self.db.parent / "backups"
        folder.mkdir()
        (folder / "manual.db").write_text("x")
        for second in (1, 2):
            backup.run_backup(self.db, keep=5, now=datetime(2026, 1, 1, 0, 0, second))
        with mock.patch.dict(os.environ, {"BACKUP_KEEP": "1"}):
            code, _, _ = run_cli("backup", "--db", self.db)
        self.assertEqual(code, 0)
        self.assertEqual(len(self.backups()), 2)
        self.assertIn("manual.db", self.backups())

    def test_keep_invalido_sai_com_2(self):
        self.add_note(item("1"))
        with mock.patch.dict(os.environ, {"BACKUP_KEEP": "0"}):
            code, _, err = run_cli("backup", "--db", self.db)
        self.assertEqual(code, 2)
        self.assertIn("BACKUP_KEEP", err)

    def test_banco_inexistente_sai_com_2_sem_criar_nada(self):
        code, _, _ = run_cli("backup", "--db", self.root / "nada" / "app.db")
        self.assertEqual(code, 2)
        self.assertFalse((self.root / "nada").exists())

    def test_app_sobre_o_backup_devolve_os_mesmos_produtos(self):
        self.add_note(item("1", "ARROZ"), item("2", "FEIJAO", price="7,00"))
        before = self.products()
        run_cli("backup", "--db", self.db)
        (name,) = self.backups()
        restored = self.root / "restored" / "app.db"
        restored.parent.mkdir()
        (self.db.parent / "backups" / name).rename(restored)
        self.db = restored
        self.assertEqual(self.products(), before)
