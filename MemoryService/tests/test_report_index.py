import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import report_index  # noqa: E402


class ReportIndexTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.bili = self.root / "bili"
        self.douyin = self.root / "douyin"
        self.bili.mkdir()
        self.douyin.mkdir()
        (self.bili / "2026-11-25.md").write_text(
            "# 日报\n\n### BV1AAA\n- 标题：第一条\n\n### BV1BBB\n- 标题：第二条\n", encoding="utf-8",
        )
        (self.douyin / "2026-11-24.md").write_text(
            "# 日报\n\n### 7300000000000000000\n**抖音条目** · @作者 · 30 秒\n", encoding="utf-8",
        )
        # 中间产物不应被当成日报
        (self.douyin / "forward-20261125-1758.md").write_text(
            "# 转发清单\n\n### 7300000000000000001\n- 标题：中间产物\n", encoding="utf-8",
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_build_index(self):
        out = report_index.build(self.bili, self.douyin, self.root / "index.md")
        text = out.read_text(encoding="utf-8")
        self.assertIn("2026-11-25", text)
        self.assertIn("B站", text)
        self.assertIn("第一条", text)
        self.assertIn("2026-11-24", text)
        self.assertIn("抖音", text)
        self.assertIn("抖音条目", text)
        self.assertNotIn("中间产物", text)

    def test_empty_folders(self):
        out = report_index.build(self.root / "none1", self.root / "none2", self.root / "empty.md")
        self.assertIn("还没有日报", out.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
