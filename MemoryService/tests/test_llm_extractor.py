import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import db  # noqa: E402
import llm_extractor  # noqa: E402


class LlmExtractorTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.conn = db.init_db(Path(self.tmp.name) / "memory.db")
        self.user_event, _ = db.add_event(
            self.conn, turn_id="llm-1", occurred_at="2026-11-25T10:00:00.000Z",
            actor="owner", role="user", content="我最近在学吉他，喜欢民谣。",
        )
        self.assistant_event, _ = db.add_event(
            self.conn, turn_id="llm-2", occurred_at="2026-11-25T10:01:00.000Z",
            actor="dafeiyu", role="assistant", content="听起来不错。",
        )

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def _call(self, items):
        return lambda prompt: json.dumps({"memories": items}, ensure_ascii=False)

    def test_extract_two_candidates(self):
        created = llm_extractor.extract_with_model(
            self.conn, event_id=self.user_event,
            call_model=self._call([
                {"body": "最近在学吉他", "kind": "interest", "importance": 3, "confidence": 0.8},
                {"body": "喜欢民谣", "kind": "user_preference", "importance": 4, "confidence": 0.9},
            ]),
        )
        self.assertEqual(len(created), 2)
        rows = self.conn.execute(
            "SELECT kind, status, tags FROM memories ORDER BY kind"
        ).fetchall()
        self.assertTrue(all(r["status"] == "candidate" for r in rows))
        self.assertTrue(all(r["tags"] == "model-extract" for r in rows))

    def test_single_object_output(self):
        created = llm_extractor.extract_with_model(
            self.conn, event_id=self.user_event,
            call_model=lambda prompt: '{"body": "最近在学吉他", "kind": "interest", "importance": 3, "confidence": 0.8}',
        )
        self.assertEqual(len(created), 1)

    def test_malformed_output_returns_empty(self):
        created = llm_extractor.extract_with_model(
            self.conn, event_id=self.user_event, call_model=lambda prompt: "不是 JSON",
        )
        self.assertEqual(created, [])

    def test_sensitive_and_unknown_kind_skipped(self):
        created = llm_extractor.extract_with_model(
            self.conn, event_id=self.user_event,
            call_model=self._call([
                {"body": "我的密码是 abc123", "kind": "user_fact"},
                {"body": "喜欢民谣", "kind": "not_a_kind"},
            ]),
        )
        self.assertEqual(created, [])

    def test_assistant_message_not_extracted(self):
        created = llm_extractor.extract_with_model(
            self.conn, event_id=self.assistant_event,
            call_model=self._call([{"body": "用户喜欢民谣", "kind": "user_preference"}]),
        )
        self.assertEqual(created, [])

    def test_duplicate_body_not_created_twice(self):
        items = [{"body": "喜欢民谣", "kind": "user_preference"}]
        first = llm_extractor.extract_with_model(
            self.conn, event_id=self.user_event, call_model=self._call(items),
        )
        second = llm_extractor.extract_with_model(
            self.conn, event_id=self.user_event, call_model=self._call(items),
        )
        self.assertEqual(len(first), 1)
        self.assertEqual(second, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
