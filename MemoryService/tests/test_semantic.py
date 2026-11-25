import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import db  # noqa: E402
import semantic  # noqa: E402


class FakeEmbedder:
    model = "fake-3d"

    def embed(self, text):
        return [
            1.0 if "猫" in text else 0.0,
            1.0 if "茶" in text else 0.0,
            1.0 if "狗" in text else 0.0,
        ]


class SemanticRecallTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.conn = db.init_db(Path(self.tmp.name) / "memory.db")
        eid, _ = db.add_event(
            self.conn, turn_id="sem-1", occurred_at="2026-11-25T10:00:00.000Z",
            actor="owner", role="user", content="猫茶狗",
        )
        for body in ("主人喜欢猫", "主人喜欢茶", "主人喜欢狗"):
            db.add_memory(
                self.conn, kind="user_preference", body=body, source_event_ids=[eid],
                fact_owner="explicit_user", status="active",
            )
        self.embedder = FakeEmbedder()

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def test_no_embeddings_returns_empty(self):
        self.assertEqual(semantic.semantic_recall(self.conn, "猫", self.embedder), [])

    def test_embed_and_recall(self):
        self.assertEqual(semantic.embed_all(self.conn, self.embedder), 3)
        hits = semantic.semantic_recall(self.conn, "猫", self.embedder)
        self.assertTrue(hits)
        self.assertIn("猫", hits[0]["body"])
        self.assertGreater(hits[0]["similarity"], 0.99)
        self.assertGreater(hits[0]["score"], 0)

    def test_limit(self):
        semantic.embed_all(self.conn, self.embedder)
        hits = semantic.semantic_recall(self.conn, "猫茶狗", self.embedder, limit=2)
        self.assertEqual(len(hits), 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
