#!/usr/bin/env python3
"""Install documentation instructions and reference sources without business shells.

Python >=3.10, standard library only. Existing destination files are never replaced.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


class InstallError(ValueError):
    pass


def installation_files(source: Path) -> dict[str, bytes]:
    source = source.resolve()
    files: dict[str, bytes] = {}
    entries = {
        "_AGENTS.md": "AGENTS.md", "_README.md": "README.md",
        "docs/_AGENTS.md": "docs/AGENTS.md", "docs/_README.md": "docs/README.md",
    }
    for old, new in entries.items():
        path = source / old
        if not path.is_file() or path.is_symlink():
            raise InstallError(f"缺少有效入口源：{old}")
        files[new] = path.read_bytes()
    for name in ("_system", "_tools", "_templates"):
        directory = source / "docs" / name
        if not directory.is_dir() or directory.is_symlink():
            raise InstallError(f"缺少有效参考目录：docs/{name}")
        for path in sorted(directory.rglob("*")):
            if path.is_symlink():
                raise InstallError(f"参考源不能包含符号链接：{path}")
            if "__pycache__" in path.parts or path.suffix == ".pyc":
                continue
            if name == "_system" and path.name in {"directory-tree.txt", "checksums.sha256", "validation-report.md"}:
                continue
            if path.is_file():
                files[path.relative_to(source).as_posix()] = path.read_bytes()
    return files


def install(source: Path, target: Path, *, dry_run: bool = False,
            overview_title: str | None = None, overview_summary: str | None = None) -> dict:
    source = source.resolve()
    target = target.resolve()
    if source == target or source in target.parents:
        raise InstallError("目标必须位于参考包之外")
    for value in (overview_title, overview_summary):
        if value is not None and not value.strip():
            raise InstallError("项目总纲标题与摘要不能只含空白")
    if bool(overview_title) != bool(overview_summary):
        raise InstallError("项目总纲需要同时提供 --overview-title 和 --overview-summary")
    files = installation_files(source)
    if overview_title and overview_summary:
        overview_title = overview_title.strip()
        overview_summary = overview_summary.strip()
        if "\n" in overview_title or "\r" in overview_title:
            raise InstallError("总纲标题必须为单行")
        meta = {
            "id": "PROJECT-OVERVIEW", "type": "project-overview", "status": "draft",
            "summary": overview_summary, "owner": None, "applies_to": "待确认",
            "verified_at": None, "verification_ref": None, "authority": "descriptive",
        }
        header = "\n".join(f"{key}: {json.dumps(value, ensure_ascii=False)}" for key, value in meta.items())
        files["docs/project/overview.md"] = (
            f"---\n{header}\n---\n\n# {overview_title}\n\n{overview_summary}\n\n"
            "适用范围、责任主体和核验依据待确认；本草案不代表批准或上线。\n"
        ).encode("utf-8")
    conflicts = []
    for relative in files:
        path = target / relative
        if not path.resolve().is_relative_to(target):
            raise InstallError(f"目标路径越界：{relative}")
        if path.exists() or path.is_symlink():
            conflicts.append(relative)
        ancestor = path.parent
        while ancestor != target.parent:
            if ancestor.is_symlink() or (ancestor.exists() and not ancestor.is_dir()):
                raise InstallError(f"目标路径不是普通目录：{ancestor}")
            if ancestor == target:
                break
            ancestor = ancestor.parent
    if conflicts:
        raise InstallError("目标已有同名文件，请先逐项合并；拒绝覆盖：" + ", ".join(sorted(conflicts)))
    result = {
        "target": str(target), "dry_run": dry_run, "files": sorted(files),
        "business_documents": ["docs/project/overview.md"] if overview_title else [],
        "note": "只部署入口、协议、工具和集中参考源；未使用的业务文件、集合目录及索引不创建。",
    }
    if dry_run:
        return result
    created_files: list[Path] = []
    created_dirs: list[Path] = []
    try:
        for relative, content in files.items():
            path = target / relative
            missing = []
            parent = path.parent
            while not parent.exists():
                missing.append(parent)
                parent = parent.parent
            for directory in reversed(missing):
                directory.mkdir()
                created_dirs.append(directory)
            # Exclusive creation protects existing files if a concurrent installer writes.
            with path.open("xb") as stream:
                created_files.append(path)
                stream.write(content)
    except (OSError, ValueError):
        for path in reversed(created_files):
            path.unlink(missing_ok=True)
        for directory in reversed(created_dirs):
            try:
                directory.rmdir()
            except OSError:
                pass
        raise
    return result


def cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--overview-title")
    parser.add_argument("--overview-summary")
    args = parser.parse_args(argv)
    try:
        result = install(args.source, args.target, dry_run=args.dry_run,
                         overview_title=args.overview_title, overview_summary=args.overview_summary)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (InstallError, OSError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(cli())
