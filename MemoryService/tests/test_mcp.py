import json
import os
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
        self.assertEqual(names, {"memory_recall", "memory_remember", "memory_forget", "memory_audit"})

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

    def test_remember_requires_source(self):
        responses = self._run([
            {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
             "params": {"name": "memory_remember",
                        "arguments": {"body": "无来源", "kind": "user_fact", "source_event_ids": []}}},
        ])
        self.assertIn("error", responses[0])


if __name__ == "__main__":
    unittest.main(verbosity=2)
