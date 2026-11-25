r"""本地备份：记忆库（一致性快照）+ tail 状态 + 人设 + profile 配置。

只打包运行所需的最小集合；不包含 `.credentials.yaml`、会话日志、插件源码。
备份落在 `D:\大肥鱼\Backups\`（被 .gitignore 排除），可手动复制到别处。
"""

from __future__ import annotations

import argparse
import json
import shutil
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


def restore(
    zip_path: Path,
    *,
    memory_db: Path | None = None,
    persona_dir: Path | None = None,
    config_file: Path | None = None,
    force: bool = False,
) -> dict:
    """从备份恢复。默认拒绝覆盖已有记忆库；force=True 时先把旧库另存。"""
    memory_db = memory_db or HOME / ".dsh" / "memory-v2" / "memory.db"
    persona_dir = persona_dir or Path(r"D:\大肥鱼\人格")
    config_file = config_file or HOME / ".dsh" / "profiles" / "desktop" / "cordis.patch.yml"
    info = verify(zip_path)
    if memory_db.exists() and not force:
        raise ValueError(f"目标记忆库已存在，拒绝覆盖：{memory_db}（需要 force=True）")

    restored = []
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(tmpdir)
        src_db = tmpdir / "memory.db"
        if not src_db.exists():
            raise ValueError("备份缺少 memory.db")
        conn = sqlite3.connect(str(src_db))
        try:
            check = conn.execute("PRAGMA integrity_check").fetchone()[0]
        finally:
            conn.close()
        if check != "ok":
            raise ValueError(f"备份数据库完整性检查失败：{check}")
        if memory_db.exists():
            shutil.copy2(memory_db, memory_db.with_name(f"memory.db.pre-restore-{stamp}"))
            restored.append("existing-db-backup")
        memory_db.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_db, memory_db)
        restored.append("memory.db")
        persona_src = tmpdir / "persona"
        if persona_src.exists() and persona_dir:
            persona_dir.mkdir(parents=True, exist_ok=True)
            for p in persona_src.glob("*.md"):
                shutil.copy2(p, persona_dir / p.name)
                restored.append(f"persona/{p.name}")
        cfg_src = tmpdir / "config" / "cordis.patch.yml"
        if cfg_src.exists() and config_file:
            config_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(cfg_src, config_file)
            restored.append("config")
    return {"restored": restored, "counts": info["counts"], "zip": str(zip_path)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", type=Path, default=None)
    ap.add_argument("--verify", type=Path, default=None)
    ap.add_argument("--restore", type=Path, default=None)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    if args.restore:
        print(json.dumps(restore(args.restore, force=args.force), ensure_ascii=False, indent=2))
        return 0
    if args.verify:
        print(json.dumps(verify(args.verify), ensure_ascii=False, indent=2))
        return 0
    path = create(args.target)
    print(json.dumps({"backup": str(path), "verify": verify(path)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
