import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import db  # noqa: E402


class McpServerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "memory.db"
        conn = db.init_db(self.db_path)
        event_id, _ = db.add_event(
            conn,
            turn_id="turn-mcp-1",
            occurred_at="2026-11-25T08:00:00.000Z",
            actor="owner",
            role="user",
            content="我养了一只橘猫。",
        )
        self.memory_id = db.add_memory(
            conn,
            kind="user_fact",
            body="主人养了一只橘猫",
            source_event_ids=[event_id],
            fact_owner="explicit_user",
            status="active",
        )
        conn.close()

    def tearDown(self):
        self.tmp.cleanup()

    def _run(self, requests):
        env = dict(os.environ)
        env["DSH_MEMORY_DB"] = str(self.db_path)
        payload = "\n".join(json.dumps(r, ensure_ascii=False) for r in requests) + "\n"
        proc = subprocess.run(
            [sys.executable, str(ROOT / "mcp_server.py")],
            input=payload.encode("utf-8"),
            capture_output=True,
            env=env,
            timeout=30,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace"))
        stdout = proc.stdout.decode("utf-8")
        return [json.loads(line) for line in stdout.splitlines() if line.strip()]

    def test_initialize_and_tools(self):
        responses = self._run([
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        ])
        self.assertEqual(responses[0]["result"]["serverInfo"]["name"], "dafeiyu-memory")
        names = {t["name"] for t in responses[1]["result"]["tools"]}
        self.assertEqual(names, {
            "memory_recall", "memory_remember", "memory_forget", "memory_audit",
            "memory_ingest", "memory_promote", "memory_decay",
            "memory_core_propose", "memory_core_confirm", "memory_core_list",
            "memory_digest_generate", "memory_digest_get", "memory_tick",
            "memory_candidates", "memory_reject", "memory_restore", "memory_stats",
            "memory_embed", "memory_semantic_recall", "memory_purge",
            "memory_extract_model",
        })

    def test_recall_and_forget(self):
        responses = self._run([
            {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
             "params": {"name": "memory_recall", "arguments": {"query": "橘猫"}}},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
             "params": {"name": "memory_forget", "arguments": {"memory_id": self.memory_id, "reason": "测试"}}},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
             "params": {"name": "memory_recall", "arguments": {"query": "橘猫"}}},
        ])
        first = json.loads(responses[0]["result"]["content"][0]["text"])
        self.assertEqual(len(first["hits"]), 1)
        self.assertTrue(json.loads(responses[1]["result"]["content"][0]["text"])["ok"])
        third = json.loads(responses[2]["result"]["content"][0]["text"])
        self.assertEqual(third["hits"], [])

    def test_restricted_memory_only_with_include_flag(self):
        conn = sqlite3.connect(self.db_path)
        event_id = conn.execute("SELECT id FROM events LIMIT 1").fetchone()[0]
        conn.close()
        self._run([
            {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
             "params": {"name": "memory_remember", "arguments": {
                 "kind": "relationship", "body": "敏感测试记忆",
                 "source_event_ids": [event_id], "sensitivity": "restricted",
                 "status": "active",
             }}},
        ])
        responses = self._run([
            {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
             "params": {"name": "memory_recall", "arguments": {"query": "敏感测试"}}},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
             "params": {"name": "memory_recall", "arguments": {
                 "query": "敏感测试", "include_restricted": True,
             }}},
        ])
        without = json.loads(responses[0]["result"]["content"][0]["text"])["hits"]
        with_flag = json.loads(responses[1]["result"]["content"][0]["text"])["hits"]
        self.assertEqual(without, [])
        self.assertTrue(any("敏感测试记忆" in h["body"] for h in with_flag))

    def test_model_extract_requires_chat_model_config(self):
        conn = sqlite3.connect(self.db_path)
        event_id = conn.execute("SELECT id FROM events LIMIT 1").fetchone()[0]
        conn.close()
        responses = self._run([
            {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
             "params": {"name": "memory_extract_model", "arguments": {"event_id": event_id}}},
        ])
        self.assertIn("error", responses[0])
        self.assertIn("DFY_CHAT_MODEL", responses[0]["error"]["message"])

    def test_purge_requires_confirm_and_removes_old_deleted(self):
        responses = self._run([
            {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
             "params": {"name": "memory_ingest",
                        "arguments": {"turn_id": "purge-1", "text": "我喜欢喝乌龙茶。"}}},
        ])
        candidate = json.loads(responses[0]["result"]["content"][0]["text"])["candidate_ids"][0]
        self._run([
            {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
             "params": {"name": "memory_reject", "arguments": {"memory_id": candidate}}},
        ])
        conn = sqlite3.connect(self.db_path)
        conn.execute("UPDATE memories SET updated_at='2020-01-01T00:00:00.000Z' WHERE id=?", (candidate,))
        conn.commit()
        conn.close()
        responses = self._run([
            {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
             "params": {"name": "memory_purge", "arguments": {}}},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
             "params": {"name": "memory_purge", "arguments": {"confirm": True}}},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
             "params": {"name": "memory_purge", "arguments": {"confirm": True}}},
        ])
        self.assertIn("error", responses[0])
        first = json.loads(responses[1]["result"]["content"][0]["text"])
        second = json.loads(responses[2]["result"]["content"][0]["text"])
        self.assertEqual(first["purged"], 1)
        self.assertEqual(second["purged"], 0)

    def test_stats(self):
        responses = self._run([
            {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
             "params": {"name": "memory_stats", "arguments": {}}},
        ])
        stats = json.loads(responses[0]["result"]["content"][0]["text"])
        self.assertEqual(stats["events"], 1)
        self.assertEqual(stats["memories"].get("active"), 1)

    def test_restore_rejected_candidate(self):
        responses = self._run([
            {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
             "params": {"name": "memory_ingest",
                        "arguments": {"turn_id": "restore-1", "text": "我喜欢喝乌龙茶。"}}},
        ])
        candidate = json.loads(responses[0]["result"]["content"][0]["text"])["candidate_ids"][0]
        self._run([
            {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
             "params": {"name": "memory_reject", "arguments": {"memory_id": candidate}}},
        ])
        responses = self._run([
            {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
             "params": {"name": "memory_restore", "arguments": {"memory_id": candidate}}},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
             "params": {"name": "memory_candidates", "arguments": {}}},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
             "params": {"name": "memory_restore", "arguments": {"memory_id": candidate}}},
        ])
        self.assertTrue(json.loads(responses[0]["result"]["content"][0]["text"])["ok"])
        entries = json.loads(responses[1]["result"]["content"][0]["text"])["entries"]
        self.assertIn(candidate, [e["id"] for e in entries])
        self.assertIn("error", responses[2])

    def test_candidate_list_and_reject(self):
        responses = self._run([
            {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
             "params": {"name": "memory_ingest",
                        "arguments": {"turn_id": "cand-1", "text": "我喜欢喝乌龙茶。"}}},
        ])
        candidate = json.loads(responses[0]["result"]["content"][0]["text"])["candidate_ids"][0]
        responses = self._run([
            {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
             "params": {"name": "memory_candidates", "arguments": {}}},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
             "params": {"name": "memory_reject", "arguments": {"memory_id": candidate}}},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
             "params": {"name": "memory_candidates", "arguments": {}}},
            {"jsonrpc": "2.0", "id": 4, "method": "tools/call",
             "params": {"name": "memory_reject", "arguments": {"memory_id": candidate}}},
        ])
        first = json.loads(responses[0]["result"]["content"][0]["text"])["entries"]
        self.assertEqual([e["id"] for e in first], [candidate])
        self.assertTrue(json.loads(responses[1]["result"]["content"][0]["text"])["ok"])
        self.assertEqual(json.loads(responses[2]["result"]["content"][0]["text"])["entries"], [])
        self.assertIn("error", responses[3])

    def test_ingest_promote_recall(self):
        responses = self._run([
            {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
             "params": {"name": "memory_ingest",
                        "arguments": {"turn_id": "mcp-ingest-1", "text": "我喜欢喝乌龙茶。"}}},
        ])
        payload = json.loads(responses[0]["result"]["content"][0]["text"])
        self.assertTrue(payload["created"])
        candidates = payload["candidate_ids"]
        self.assertEqual(len(candidates), 1)
        # 候选默认不参与召回
        second = self._run([
            {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
             "params": {"name": "memory_recall", "arguments": {"query": "乌龙茶"}}},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
             "params": {"name": "memory_promote", "arguments": {"memory_id": candidates[0]}}},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
             "params": {"name": "memory_recall", "arguments": {"query": "乌龙茶"}}},
        ])
        before = json.loads(second[0]["result"]["content"][0]["text"])
        after = json.loads(second[2]["result"]["content"][0]["text"])
        self.assertEqual(before["hits"], [])
        self.assertEqual(len(after["hits"]), 1)

    def test_digest_generate_and_get(self):
        responses = self._run([
            {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
             "params": {"name": "memory_digest_generate", "arguments": {"day": "2026-11-25"}}},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
             "params": {"name": "memory_digest_get", "arguments": {"day": "2026-11-25"}}},
        ])
        generated = json.loads(responses[0]["result"]["content"][0]["text"])["digest"]
        fetched = json.loads(responses[1]["result"]["content"][0]["text"])["digest"]
        self.assertEqual(generated["day"], "2026-11-25")
        self.assertIn("用户 1", generated["summary"])
        self.assertEqual(fetched["summary"], generated["summary"])

    def test_core_propose_confirm_list(self):
        responses = self._run([
            {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
             "params": {"name": "memory_core_propose",
                        "arguments": {"body": "大肥鱼运行在本机 DSH", "reason": "测试"}}},
        ])
        core_id = json.loads(responses[0]["result"]["content"][0]["text"])["core_id"]
        responses = self._run([
            {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
             "params": {"name": "memory_core_confirm", "arguments": {"core_id": core_id}}},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
             "params": {"name": "memory_core_list", "arguments": {}}},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
             "params": {"name": "memory_core_confirm", "arguments": {"core_id": core_id}}},
        ])
        self.assertTrue(json.loads(responses[0]["result"]["content"][0]["text"])["ok"])
        entries = json.loads(responses[1]["result"]["content"][0]["text"])["entries"]
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["status"], "confirmed")
        self.assertIn("error", responses[2])
        # 已确认核心记忆应进入召回，且排在普通记忆前
        recall = self._run([
            {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
             "params": {"name": "memory_recall", "arguments": {"query": "DSH"}}},
        ])
        hits = json.loads(recall[0]["result"]["content"][0]["text"])["hits"]
        self.assertTrue(hits)
        self.assertEqual(hits[0]["kind"], "core")

    def test_decay_dry_run_then_apply(self):
        import datetime as _dt
        import db as _db
        conn = _db.init_db(self.db_path)
        event_id = conn.execute("SELECT id FROM events LIMIT 1").fetchone()["id"]
        mid = _db.add_memory(
            conn, kind="event", body="很旧的记忆", source_event_ids=[event_id],
            fact_owner="observed", status="active", half_life_days=30,
        )
        old = (_dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(days=365)).isoformat().replace("+00:00", "Z")
        conn.execute("UPDATE memories SET created_at = ? WHERE id = ?", (old, mid))
        conn.commit()
        conn.close()
        responses = self._run([
            {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
             "params": {"name": "memory_decay", "arguments": {"dry_run": True}}},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
             "params": {"name": "memory_decay", "arguments": {"dry_run": False}}},
        ])
        dry = json.loads(responses[0]["result"]["content"][0]["text"])
        applied = json.loads(responses[1]["result"]["content"][0]["text"])
        self.assertEqual(len(dry["archived"]), 1)
        self.assertTrue(dry["dry_run"])
        self.assertEqual(len(applied["archived"]), 1)
        self.assertFalse(applied["dry_run"])

    def test_remember_requires_source(self):
        responses = self._run([
            {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
             "params": {"name": "memory_remember",
                        "arguments": {"body": "无来源", "kind": "user_fact", "source_event_ids": []}}},
        ])
        self.assertIn("error", responses[0])


if __name__ == "__main__":
    unittest.main(verbosity=2)
