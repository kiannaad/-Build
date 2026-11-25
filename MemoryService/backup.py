r"""本地备份：记忆库（一致性快照）+ tail 状态 + 人设 + profile 配置。

只打包运行所需的最小集合；不包含 `.credentials.yaml`、会话日志、插件源码。
备份落在 `D:\大肥鱼\Backups\`（被 .gitignore 排除），可手动复制到别处。
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

DEFAULT_TARGET = Path(r"D:\大肥鱼\Backups")
HOME = Path.home()


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _counts(db_path: Path) -> dict:
    conn = sqlite3.connect(str(db_path), timeout=10)
    try:
        return {
            "events": conn.execute("SELECT COUNT(*) FROM events").fetchone()[0],
            "memories": conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0],
            "core": conn.execute("SELECT COUNT(*) FROM core_memories").fetchone()[0],
        }
    finally:
        conn.close()


def _snapshot_db(src: Path, dst: Path) -> None:
    source = sqlite3.connect(str(src), timeout=10)
    target = sqlite3.connect(dst)
    try:
        source.backup(target)
    finally:
        target.close()
        source.close()


def create(
    target: Path | None = None,
    *,
    memory_db: Path | None = None,
    persona_dir: Path | None = None,
    config_file: Path | None = None,
    include_config: bool = True,
) -> Path:
    target = target or DEFAULT_TARGET
    memory_db = memory_db or HOME / ".dsh" / "memory-v2" / "memory.db"
    persona_dir = persona_dir or Path(r"D:\大肥鱼\人格")
    config_file = config_file or HOME / ".dsh" / "profiles" / "desktop" / "cordis.patch.yml"
    target.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out = target / f"dafeiyu-{stamp}.zip"
    counts = _counts(memory_db)
    manifest = {"created_at": _now(), "counts": counts, "include_config": include_config}

    with tempfile.TemporaryDirectory() as tmp:
        tmp_db = Path(tmp) / "memory.db"
        _snapshot_db(memory_db, tmp_db)
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(tmp_db, "memory.db")
            state = HOME / ".dsh" / "memory-v2" / "tail_state.json"
            if state.exists():
                zf.write(state, "tail_state.json")
            if persona_dir and persona_dir.exists():
                for p in sorted(persona_dir.glob("*.md")):
                    zf.write(p, f"persona/{p.name}")
            if include_config and config_file.exists():
                zf.write(config_file, "config/cordis.patch.yml")
            zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
    return out


def verify(zip_path: Path) -> dict:
    with zipfile.ZipFile(zip_path) as zf:
        bad = zf.testzip()
        if bad:
            raise ValueError(f"备份损坏: {bad}")
        names = zf.namelist()
        if "manifest.json" not in names:
            raise ValueError("缺少 manifest.json")
        manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
    manifest["files"] = len(names)
    manifest["has_memory_db"] = "memory.db" in names
    return manifest


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", type=Path, default=None)
    ap.add_argument("--verify", type=Path, default=None)
    args = ap.parse_args()
    if args.verify:
        print(json.dumps(verify(args.verify), ensure_ascii=False, indent=2))
        return 0
    path = create(args.target)
    print(json.dumps({"backup": str(path), "verify": verify(path)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
