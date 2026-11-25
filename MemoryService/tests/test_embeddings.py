import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import db  # noqa: E402
import embeddings  # noqa: E402


class FakeEmbedder:
    model = "fake-3d"

    def embed(self, text):
        return [
            1.0 if "猫" in text else 0.0,
            1.0 if "茶" in text else 0.0,
            1.0 if "狗" in text else 0.0,
        ]


class EmbeddingsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.conn = db.init_db(Path(self.tmp.name) / "memory.db")
        eid, _ = db.add_event(
            self.conn, turn_id="emb-1", occurred_at="2026-11-25T10:00:00.000Z",
            actor="owner", role="user", content="猫茶狗",
        )
        self.ids = {}
        for body in ("我喜欢猫", "我喜欢茶", "我喜欢狗"):
            self.ids[body] = db.add_memory(
                self.conn, kind="user_preference", body=body, source_event_ids=[eid],
                fact_owner="explicit_user", status="active",
            )
        self.embedder = FakeEmbedder()

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def test_pack_roundtrip(self):
        vec = [0.5, -1.25, 3.0]
        self.assertEqual(embeddings.unpack(embeddings.pack(vec)), vec)

    def test_cosine(self):
        self.assertAlmostEqual(embeddings.cosine([1, 0], [1, 0]), 1.0)
        self.assertAlmostEqual(embeddings.cosine([1, 0], [0, 1]), 0.0)
        self.assertAlmostEqual(embeddings.cosine([1, 0], [0, 0]), 0.0)

    def test_embed_missing_and_semantic(self):
        self.assertEqual(embeddings.embed_missing(self.conn, self.embedder), 3)
        self.assertEqual(embeddings.embed_missing(self.conn, self.embedder), 0)
        hits = embeddings.semantic_candidates(
            self.conn, query_vec=[1.0, 0.0, 0.0], model=self.embedder.model
        )
        self.assertEqual(hits[0][0], self.ids["我喜欢猫"])
        self.assertGreater(hits[0][1], 0.99)

    def test_restricted_excluded(self):
        eid = self.conn.execute("SELECT id FROM events LIMIT 1").fetchone()["id"]
        secret_id = db.add_memory(
            self.conn, kind="user_fact", body="秘密的猫", source_event_ids=[eid],
            fact_owner="explicit_user", status="active", sensitivity="restricted",
        )
        embeddings.embed_missing(self.conn, self.embedder)
        hits = embeddings.semantic_candidates(
            self.conn, query_vec=[1.0, 0.0, 0.0], model=self.embedder.model
        )
        self.assertNotIn(secret_id, [mid for mid, _ in hits])
        # restricted 不发送给嵌入服务，因此永远没有向量
        self.assertNotIn(secret_id, embeddings.load_embeddings(self.conn, self.embedder.model))

    def test_large_set_uses_vectorized_path(self):
        eid = self.conn.execute("SELECT id FROM events LIMIT 1").fetchone()["id"]
        for i in range(40):
            body = f"批量记忆{i} 猫茶狗"
            db.add_memory(
                self.conn, kind="user_preference", body=body, source_event_ids=[eid],
                fact_owner="explicit_user", status="active",
            )
        embeddings.embed_missing(self.conn, self.embedder)
        hits = embeddings.semantic_candidates(
            self.conn, query_vec=[1.0, 0.0, 0.0], model=self.embedder.model, limit=5,
        )
        self.assertEqual(len(hits), 5)
        self.assertTrue(all(0.0 <= sim <= 1.0001 for _, sim in hits))

    def test_model_isolation(self):
        embeddings.embed_missing(self.conn, self.embedder)
        self.assertEqual(embeddings.load_embeddings(self.conn, "another-model"), {})


if __name__ == "__main__":
    unittest.main(verbosity=2)
