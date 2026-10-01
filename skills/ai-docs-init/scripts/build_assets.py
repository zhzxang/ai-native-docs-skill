#!/usr/bin/env python3
"""Build or verify the distributable skill assets from the sole template source."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import tempfile


EXCLUDED = {"checksums.sha256", "directory-tree.txt", "validation-report.md"}


def source_files(source: Path) -> dict[str, bytes]:
    entries = {}
    for path in sorted(source.rglob("*")):
        relative = path.relative_to(source)
        if any(part in {"__pycache__", ".git", "_generated"} for part in relative.parts):
            continue
        if path.is_symlink():
            raise ValueError(f"模板源不能包含符号链接：{relative}")
        if path.is_file() and path.suffix != ".pyc" and path.name not in EXCLUDED | {".DS_Store"}:
            entries[relative.as_posix()] = path.read_bytes()
    if not all(name in entries for name in ("_AGENTS.md", "docs/_tools/init_docs.py", "docs/_system/package.json")):
        raise ValueError("不是有效的文档模板源目录")
    return entries


def build(source: Path, destination: Path, *, check: bool = False) -> dict:
    source = source.resolve()
    destination = destination.resolve()
    if destination == source or source in destination.parents or destination in source.parents:
        raise ValueError("打包目标与模板源必须互不包含")
    entries = source_files(source)
    actual = source_files(destination) if destination.is_dir() else {}
    drift = sorted(name for name in entries.keys() | actual.keys() if entries.get(name) != actual.get(name))
    if not check:
        backup = destination.with_name(destination.name + ".previous")
        if backup.exists():
            raise ValueError(f"存在未处理的打包备份：{backup}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = Path(tempfile.mkdtemp(prefix=".ai-docs-assets-", dir=destination.parent))
        try:
            for name, data in entries.items():
                path = temporary / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
            if destination.exists():
                destination.rename(backup)
            try:
                temporary.rename(destination)
            except OSError:
                if backup.exists():
                    backup.rename(destination)
                raise
            if backup.exists():
                shutil.rmtree(backup)
        finally:
            shutil.rmtree(temporary, ignore_errors=True)
    return {"ok": not drift if check else True, "checked": check, "files": len(entries),
            "changed_files": len(drift), "drift": drift if check else [],
            "source": str(source), "destination": str(destination)}


def cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path(__file__).resolve().parents[3] / "templates")
    parser.add_argument("--destination", type=Path,
                        default=Path(__file__).resolve().parents[1] / "assets/templates")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = build(args.source, args.destination, check=args.check)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["ok"] else 1
    except (ValueError, OSError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(cli())
