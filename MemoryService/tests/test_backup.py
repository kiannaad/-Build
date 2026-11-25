import json
import sqlite3
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import backup  # noqa: E402
import db  # noqa: E402


class BackupTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.db_path = self.root / "memory.db"
        conn = db.init_db(self.db_path)
        db.add_event(conn, turn_id="b-1", occurred_at="2026-11-25T10:00:00.000Z",
                     actor="owner", role="user", content="备份测试")
        db.add_memory(conn, kind="user_fact", body="备份测试记忆",
                      source_event_ids=[conn.execute("SELECT id FROM events LIMIT 1").fetchone()["id"]],
                      fact_owner="explicit_user", status="active")
        db.propose_core(conn, body="核心事实", reason="测试")
        conn.close()
        self.persona = self.root / "persona"
        self.persona.mkdir()
        (self.persona / "大肥鱼.md").write_text("# 测试人设\n", encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_create_and_verify(self):
        out = backup.create(
            self.root / "backups", memory_db=self.db_path,
            persona_dir=self.persona, include_config=False,
        )
        self.assertTrue(out.exists())
        info = backup.verify(out)
        self.assertEqual(info["counts"]["events"], 1)
        self.assertEqual(info["counts"]["memories"], 1)
        self.assertEqual(info["counts"]["core"], 1)
        self.assertTrue(info["has_memory_db"])
        with zipfile.ZipFile(out) as zf:
            names = zf.namelist()
            self.assertIn("memory.db", names)
            self.assertIn("persona/大肥鱼.md", names)
            self.assertNotIn("config/cordis.patch.yml", names)
            zf.extract("memory.db", self.root / "restore")
        restored = self.root / "restore" / "memory.db"
        conn = sqlite3.connect(restored)
        try:
            n = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(n, 1)

    def test_restore_to_new_path(self):
        out = backup.create(
            self.root / "backups", memory_db=self.db_path,
            persona_dir=self.persona, include_config=False,
        )
        target = self.root / "new" / "memory.db"
        result = backup.restore(
            out, memory_db=target, persona_dir=self.persona, config_file=self.root / "cfg.yml",
        )
        self.assertIn("memory.db", result["restored"])
        conn = sqlite3.connect(target)
        try:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM events").fetchone()[0], 1)
        finally:
            conn.close()

    def test_restore_refuses_overwrite_without_force(self):
        out = backup.create(
            self.root / "backups", memory_db=self.db_path,
            persona_dir=self.persona, include_config=False,
        )
        with self.assertRaises(ValueError):
            backup.restore(out, memory_db=self.db_path, persona_dir=self.persona,
                           config_file=self.root / "cfg.yml")
        result = backup.restore(out, memory_db=self.db_path, persona_dir=self.persona,
                                config_file=self.root / "cfg.yml", force=True)
        self.assertIn("existing-db-backup", result["restored"])
        self.assertTrue(list(self.db_path.parent.glob("memory.db.pre-restore-*")))

    def test_verify_rejects_non_backup(self):
        bad = self.root / "bad.zip"
        with zipfile.ZipFile(bad, "w") as zf:
            zf.writestr("readme.txt", "not a backup")
        with self.assertRaises(ValueError):
            backup.verify(bad)


if __name__ == "__main__":
    unittest.main(verbosity=2)
