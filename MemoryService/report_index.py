"""生成 Journal/index.md：汇总 B站/抖音日报的日期、条数与标题。"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

HEADING = re.compile(r"^###\s+(BV[0-9A-Za-z]+|\d{6,})")
TITLE = re.compile(r"^-\s*标题[：:]\s*(.+)$")


def scan(folder: Path, platform: str) -> list[dict]:
    if not folder or not folder.exists():
        return []
    rows = []
    for path in sorted(folder.glob("*.md"), reverse=True):
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        items = []
        current = None
        for line in lines:
            m = HEADING.match(line.strip())
            if m:
                current = {"id": m.group(1), "title": ""}
                items.append(current)
                continue
            if current and not current["title"]:
                t = TITLE.match(line.strip())
                if t:
                    current["title"] = t.group(1).strip()
        rows.append({
            "date": path.stem,
            "platform": platform,
            "count": len(items),
            "titles": [i["title"] or i["id"] for i in items],
        })
    return rows


def render(rows: list[dict]) -> str:
    lines = ["# 日报索引", "", "> 由 `MemoryService/report_index.py` 生成；`Journal/` 不进 Git。", ""]
    if not rows:
        lines.append("（还没有日报）")
        return "\n".join(lines) + "\n"
    lines += ["| 日期 | 平台 | 条数 | 标题 |", "| --- | --- | ---: | --- |"]
    for r in sorted(rows, key=lambda x: (x["date"], x["platform"]), reverse=True):
        titles = "；".join(r["titles"][:5])
        if len(r["titles"]) > 5:
            titles += f" 等 {len(r['titles'])} 条"
        lines.append(f"| {r['date']} | {r['platform']} | {r['count']} | {titles} |")
    return "\n".join(lines) + "\n"


def build(bili_dir: Path, douyin_dir: Path, out: Path) -> Path:
    rows = scan(bili_dir, "B站") + scan(douyin_dir, "抖音")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(rows), encoding="utf-8")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bili", type=Path, default=Path.home() / ".dsh" / "bili-duty" / "out")
    ap.add_argument("--douyin", type=Path, default=Path.home() / ".dsh" / "douyin-duty" / "out")
    ap.add_argument("--out", type=Path, default=Path(r"D:\大肥鱼\Journal\index.md"))
    args = ap.parse_args()
    path = build(args.bili, args.douyin, args.out)
    print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
