#!/usr/bin/env python3
"""Install documentation instructions and reference sources without business shells.

Python >=3.10, standard library only. Legacy install strictly refuses collisions.
Incremental modes preserve project facts and update only unchanged owned baselines.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile


class InstallError(ValueError):
    pass


MANIFEST = "docs/_system/installation.json"
LOCK = ".ai-docs-init.lock"
BLOCK_ID = "ai-docs-init"
BLOCK_BEGIN = "<!-- ai-docs-init:begin -->"
BLOCK_END = "<!-- ai-docs-init:end -->"
CONFIG_FILES = {
    "docs/_system/project-map.json", "docs/_system/commands.json",
    "docs/_system/collections.json", "docs/_system/routes.json",
}
ENTRY_FILES = {"AGENTS.md", "README.md", "docs/AGENTS.md", "docs/README.md"}
SCAN_EXCLUDED = {
    ".git", ".hg", ".svn", "node_modules", "vendor", ".venv", "venv",
    "__pycache__", ".cache", "dist", "build", "coverage", "skills", "assets",
    "_templates", "_generated",
}


def _sha(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _target_root(target: Path) -> Path:
    original = Path(os.path.abspath(target))
    for candidate in (original, *original.parents):
        # macOS exposes these standard temporary-directory aliases as symlinks.
        if candidate.is_symlink() and str(candidate) not in {"/tmp", "/var"}:
            raise InstallError(f"目标路径不能经过符号链接：{candidate}")
        if candidate.exists() and not candidate.is_dir():
            raise InstallError(f"目标根及祖先必须是普通目录：{candidate}")
    return original.resolve()


def _destination(target: Path, relative: str) -> Path:
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise InstallError(f"需要非空仓库相对路径：{relative}")
    if any(part in {"..", ".git"} for part in Path(relative).parts):
        raise InstallError(f"目标路径越界或触及 Git 数据：{relative}")
    path = target / relative
    if not path.resolve().is_relative_to(target):
        raise InstallError(f"目标路径越界：{relative}")
    current = path
    while current != target:
        if current.is_symlink():
            raise InstallError(f"目标路径不能包含符号链接：{current}")
        if current != path and current.exists() and not current.is_dir():
            raise InstallError(f"目标祖先不是普通目录：{current}")
        current = current.parent
    return path


def _snapshot(path: Path) -> str | None:
    if path.is_symlink():
        raise InstallError(f"目标不能包含符号链接：{path}")
    if not path.exists():
        return None
    if not path.is_file():
        return "directory"
    return _sha(path.read_bytes())


def _read_manifest(target: Path) -> dict | None:
    path = _destination(target, MANIFEST)
    if not path.exists():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise InstallError(f"无法读取安装清单，保留现场并先修复：{exc}") from exc
    if (not isinstance(value, dict) or value.get("schema_version") != 1
            or not isinstance(value.get("system_version"), str)
            or not isinstance(value.get("owned_files"), dict)
            or not isinstance(value.get("owned_blocks"), dict)):
        raise InstallError("安装清单格式不兼容；不接管或覆盖现有文件")
    for collection in (value["owned_files"], value["owned_blocks"]):
        for relative, record in collection.items():
            _destination(target, relative)
            if (not isinstance(record, dict)
                    or not re.fullmatch(r"[0-9a-f]{64}", str(record.get("sha256", "")))):
                raise InstallError(f"安装清单基线无效：{relative}")
    for relative, record in value["owned_blocks"].items():
        if relative not in ENTRY_FILES or record.get("id") != BLOCK_ID:
            raise InstallError(f"安装清单包含未知托管区块：{relative}")
    return value


def scan(target: Path, *, max_documents: int = 500) -> dict:
    """Inventory paths and headings only; never run project commands or read bodies back."""
    target = _target_root(target)
    if not isinstance(max_documents, int) or max_documents < 1:
        raise InstallError("max_documents 必须是正整数")
    installation = None
    installation_error = None
    try:
        installation = _read_manifest(target)
    except InstallError as exc:
        installation_error = str(exc)
    project_files = []
    documents = []
    symlinks = []
    truncated = False
    if target.exists():
        for directory, dirs, names in os.walk(target, followlinks=False):
            root = Path(directory)
            dirs[:] = sorted(name for name in dirs if name not in SCAN_EXCLUDED)
            for name in list(dirs):
                path = root / name
                if path.is_symlink():
                    symlinks.append(path.relative_to(target).as_posix())
                    dirs.remove(name)
            for name in sorted(names):
                path = root / name
                relative = path.relative_to(target).as_posix()
                if path.is_symlink():
                    symlinks.append(relative)
                    continue
                if (root == target and name not in {LOCK}) or name in {
                    "package.json", "pyproject.toml", "Cargo.toml", "go.mod", "pom.xml",
                }:
                    project_files.append(relative)
                if path.suffix.lower() != ".md":
                    continue
                if len(documents) >= max_documents:
                    truncated = True
                    continue
                try:
                    # Heading inventory has a bounded read and returns no prose.
                    with path.open("rb") as stream:
                        raw = stream.read(131072).decode("utf-8")
                except (OSError, UnicodeError):
                    documents.append({"path": relative, "headings": [], "has_doc_meta": False,
                                      "unreadable": True})
                    continue
                documents.append({"path": relative,
                                  "headings": re.findall(r"^#{1,3} (.+)$", raw, re.MULTILINE)[:8],
                                  "has_doc_meta": bool("```yaml doc-meta" in raw
                                                       or re.search(r"^id:\s*", raw, re.MULTILINE))})
    has_existing = bool(project_files or documents or (target.exists() and any(
        path.name not in SCAN_EXCLUDED and path.name != LOCK for path in target.iterdir())))
    return {"target": str(target), "mode_hint": "upgrade" if installation or installation_error else
            "adopt" if has_existing else "init", "installation": installation,
            "installation_error": installation_error, "project_files": sorted(project_files),
            "markdown_documents": documents, "symlinks": sorted(symlinks), "truncated": truncated}


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


def _system_version(files: dict[str, bytes]) -> str:
    try:
        package = json.loads(files["docs/_system/package.json"])
        version = package.get("system_version", package.get("version"))
        if not isinstance(version, str) or not version.strip():
            raise ValueError("需要非空 system_version")
        return version.strip()
    except (KeyError, ValueError, AttributeError) as exc:
        raise InstallError(f"参考包缺少有效 docs/_system/package.json：{exc}") from exc


def _overview_bytes(title: str | None, summary: str | None) -> bytes | None:
    for value in (title, summary):
        if value is not None and (not isinstance(value, str) or not value.strip()):
            raise InstallError("项目总纲标题与摘要不能只含空白")
    if bool(title) != bool(summary):
        raise InstallError("项目总纲需要同时提供 --overview-title 和 --overview-summary")
    if title is None:
        return None
    title, summary = title.strip(), summary.strip()
    if "\n" in title or "\r" in title:
        raise InstallError("总纲标题必须为单行")
    meta = {"id": "PROJECT-OVERVIEW", "type": "project-overview", "status": "draft",
            "summary": summary, "owner": None, "applies_to": "待确认", "verified_at": None,
            "verification_ref": None, "authority": "descriptive"}
    header = "\n".join(f"{key}: {json.dumps(value, ensure_ascii=False)}" for key, value in meta.items())
    return (f"---\n{header}\n---\n\n# {title}\n\n{summary}\n\n"
            "适用范围、责任主体和核验依据待确认；本草案不代表批准或上线。\n").encode("utf-8")


def _entry_content(relative: str, files: dict[str, bytes]) -> bytes:
    if relative == "README.md":
        text = ("## AI 文档系统\n\n"
                "从 [文档导航](docs/README.md) 查找项目资料；"
                "AI 执行约定见 [AGENTS.md](AGENTS.md)。\n"
                "写入前阅读 [写入协议](docs/_system/writing-policy.md)；"
                "实际代码位置与运行命令需要按项目事实核验。\n")
    else:
        text = files[relative].decode("utf-8").strip() + "\n"
    return (BLOCK_BEGIN + "\n" + text + BLOCK_END + "\n").encode("utf-8")


def _existing_block(raw: bytes) -> tuple[int, int, bytes] | None:
    text = raw.decode("utf-8")
    begins = list(re.finditer(re.escape(BLOCK_BEGIN), text))
    ends = list(re.finditer(re.escape(BLOCK_END), text))
    if not begins and not ends:
        return None
    if len(begins) != 1 or len(ends) != 1 or begins[0].start() > ends[0].start():
        raise InstallError("托管区块标记重复、缺失或顺序错误")
    # Offsets use bytes so all unowned Unicode, whitespace and line endings survive.
    start = len(text[:begins[0].start()].encode("utf-8"))
    end = len(text[:ends[0].end()].encode("utf-8"))
    if raw[end:end + 2] == b"\r\n":
        end += 2
    elif raw[end:end + 1] == b"\n":
        end += 1
    return start, end, raw[start:end]


def _configuration_conflicts(target: Path, files: dict[str, bytes]) -> list[dict]:
    """Check the retained configuration can be read by this protocol before installing it."""
    problems = []
    configs = {}
    for relative in sorted(CONFIG_FILES):
        path = _destination(target, relative)
        try:
            raw = path.read_bytes() if path.exists() else files[relative]
            data = json.loads(raw)
            expected = json.loads(files[relative])
            if not isinstance(data, dict) or data.get("schema_version") != expected.get("schema_version"):
                raise ValueError("配置 schema_version 与当前写入协议不兼容；需显式迁移配置后再安装")
            configs[relative] = data
        except (OSError, UnicodeError, ValueError, KeyError) as exc:
            problems.append({"path": relative, "reason": str(exc), "blocking": True})
    reg_path = "docs/_system/collections.json"
    reg = configs.get(reg_path)
    keys = set()
    if reg is not None:
        try:
            source_defaults = json.loads(files[reg_path])["defaults"]
            if reg.get("defaults") != source_defaults:
                raise ValueError("集合阈值、空壳创建或收拢规则与当前协议不兼容；保留原规则并等待明确迁移")
            if not isinstance(reg.get("page_size"), int) or not 1 <= reg["page_size"] <= 100:
                raise ValueError("page_size 需要为 1 到 100 的整数")
            if not isinstance(reg.get("collections"), list):
                raise ValueError("collections 需要为数组")
            bases = set()
            for item in reg["collections"]:
                if not isinstance(item, dict):
                    raise ValueError("集合登记需要为对象")
                key, base = item.get("key"), item.get("base_path")
                if not isinstance(key, str) or not re.fullmatch(r"[a-z][a-z0-9-]*", key) or key in keys:
                    raise ValueError(f"非法或重复集合键：{key}")
                if (not isinstance(base, str) or not base.startswith("docs/") or Path(base).suffix
                        or any(part.startswith("_") for part in Path(base).parts) or base in bases):
                    raise ValueError(f"非法或重复集合基础路径：{base}")
                _destination(target, base)
                template = item.get("template")
                if template != f"docs/_templates/{key}.md":
                    raise ValueError(f"集合模板路径不兼容：{key}")
                template_path = _destination(target, template)
                if template not in files and not template_path.is_file():
                    raise ValueError(f"集合模板缺失：{template}")
                if not isinstance(item.get("prefix"), str):
                    raise ValueError(f"集合 prefix 缺失：{key}")
                keys.add(key)
                bases.add(base)
        except (ValueError, KeyError, TypeError) as exc:
            problems.append({"path": reg_path, "reason": str(exc), "blocking": True})
    routes_path = "docs/_system/routes.json"
    route_config = configs.get(routes_path)
    if route_config is not None and reg is not None:
        try:
            routes = route_config.get("routes")
            if not isinstance(routes, list):
                raise ValueError("routes 需要为数组")
            seen = set()
            for route in routes:
                if not isinstance(route, dict) or not isinstance(route.get("id"), str) or route["id"] in seen:
                    raise ValueError("路由 ID 缺失或重复")
                seen.add(route["id"])
                if not isinstance(route.get("must_read"), list) or not isinstance(route.get("write_back"), list):
                    raise ValueError(f"路由 {route['id']} 的 must_read/write_back 需要为数组")
                refs = list(route["must_read"]) + list(route["write_back"])
                for condition in route.get("read_when", []):
                    if not isinstance(condition, dict) or not isinstance(condition.get("paths"), list):
                        raise ValueError(f"路由 {route['id']} 的条件路径格式错误")
                    refs.extend(condition["paths"])
                for ref in refs:
                    if isinstance(ref, str):
                        _destination(target, ref)
                    elif isinstance(ref, dict) and set(ref) == {"collection"}:
                        if ref["collection"] not in keys:
                            raise ValueError(f"路由 {route['id']} 引用未知集合：{ref['collection']}")
                    elif isinstance(ref, dict) and set(ref) == {"optional_path"}:
                        _destination(target, ref["optional_path"])
                    else:
                        raise ValueError(f"路由 {route['id']} 的定位引用格式不兼容")
        except (ValueError, KeyError, TypeError) as exc:
            problems.append({"path": routes_path, "reason": str(exc), "blocking": True})
    for relative, field in (("docs/_system/project-map.json", "locations"),
                            ("docs/_system/commands.json", "commands")):
        data = configs.get(relative)
        if data is not None and (not isinstance(data.get(field), list)
                                 or any(not isinstance(item, dict) for item in data.get(field, []))):
            problems.append({"path": relative, "reason": f"{field} 需要为对象数组", "blocking": True})
    return problems


def plan_install(source: Path, target: Path, mode: str = "auto", *,
                 overview_title: str | None = None, overview_summary: str | None = None) -> dict:
    """Build a reviewable, serializable plan. Planning never creates directories or files."""
    if mode not in {"auto", "init", "adopt", "upgrade"}:
        raise InstallError(f"未知初始化模式：{mode}")
    overview = _overview_bytes(overview_title, overview_summary)
    source = source.resolve()
    target = _target_root(target)
    if source == target or source in target.parents:
        raise InstallError("目标必须位于参考包之外")
    inventory = scan(target)
    selected_mode = inventory["mode_hint"] if mode == "auto" else mode
    files = installation_files(source)
    files.pop(MANIFEST, None)
    version = _system_version(files)
    plan = {"source": str(source), "target": str(target), "mode": selected_mode,
            "status": "planned", "system_version": version, "actions": [], "conflicts": [],
            "preserved": [], "stages": {"installed": False, "configured": None, "strict_ready": None},
            "business_documents": ["docs/project/overview.md"] if overview is not None else [],
            "_payloads": {}, "_expected": {},
            "note": "只安装执行入口、协议、工具和参考源；不移动历史文档、不创建业务壳、不执行项目命令。就绪状态需另行核验。"}
    if inventory["installation_error"]:
        plan["conflicts"].append({"path": MANIFEST, "reason": inventory["installation_error"], "blocking": True})
    if selected_mode == "init" and inventory["mode_hint"] != "init":
        plan["conflicts"].append({"path": ".", "reason": "init 仅用于空项目；已有内容请使用 adopt 或 auto", "blocking": True})
    if selected_mode == "upgrade" and not inventory["installation"]:
        plan["conflicts"].append({"path": MANIFEST, "reason": "upgrade 需要有效安装清单；未登记项目请先 adopt", "blocking": True})
    plan["conflicts"].extend(_configuration_conflicts(target, files))
    if any(item["blocking"] for item in plan["conflicts"]):
        plan["status"] = "blocked"
        return plan
    previous = inventory["installation"] or {}
    owned_files = dict(previous.get("owned_files", {}))
    owned_blocks = dict(previous.get("owned_blocks", {}))
    expected = plan["_expected"]

    def write(relative: str, content: bytes, reason: str) -> None:
        before = expected[relative]
        if before == _sha(content):
            return
        plan["actions"].append({"path": relative, "operation": "create" if before is None else "update",
                                "reason": reason, "before_sha256": before, "after_sha256": _sha(content)})
        plan["_payloads"][relative] = base64.b64encode(content).decode("ascii")

    for relative in sorted(files):
        path = _destination(target, relative)
        before = expected[relative] = _snapshot(path)
        desired = files[relative]
        if relative in ENTRY_FILES:
            block = _entry_content(relative, files)
            if before is None:
                write(relative, block, "创建托管入口")
                owned_blocks[relative] = {"id": BLOCK_ID, "sha256": _sha(block)}
                continue
            try:
                if before == "directory":
                    raise InstallError("入口路径已有目录")
                raw = path.read_bytes()
                current_block = _existing_block(raw)
                baseline = owned_blocks.get(relative)
                if current_block is None:
                    if baseline:
                        raise InstallError("已登记托管区块被删除；保留本地修改")
                    separator = b"\n\n" if raw and not raw.endswith(b"\n") else b"\n" if raw else b""
                    write(relative, raw + separator + block, "追加托管入口，保留原文")
                    owned_blocks[relative] = {"id": BLOCK_ID, "sha256": _sha(block)}
                else:
                    start, end, current = current_block
                    if not baseline:
                        raise InstallError("现有区块没有安装基线；不接管未知托管标记")
                    if _sha(current) != baseline["sha256"]:
                        raise InstallError("托管区块已有本地修改；保留内容待合并")
                    write(relative, raw[:start] + block + raw[end:], "更新未修改的托管区块")
                    owned_blocks[relative] = {"id": BLOCK_ID, "sha256": _sha(block)}
                    if current == block:
                        plan["preserved"].append({"path": relative, "reason": "托管区块已是当前版本"})
            except (UnicodeError, InstallError) as exc:
                plan["conflicts"].append({"path": relative, "reason": str(exc), "blocking": False})
            continue
        if before is None:
            write(relative, desired, "安装缺失系统资产")
            owned_files[relative] = {"sha256": _sha(desired)}
        elif before == "directory":
            plan["conflicts"].append({"path": relative, "reason": "文件路径已有目录；保留原结构", "blocking": False})
        elif relative in CONFIG_FILES:
            plan["preserved"].append({"path": relative, "reason": "保留项目配置及其原始安装基线"})
        elif relative in owned_files:
            if before != owned_files[relative]["sha256"]:
                plan["conflicts"].append({"path": relative, "reason": "系统资产已有本地修改；保留待合并", "blocking": False})
            else:
                write(relative, desired, "更新未修改的系统资产")
                owned_files[relative] = {"sha256": _sha(desired)}
        elif before == _sha(desired):
            plan["preserved"].append({"path": relative, "reason": "现有内容相同；跳过且不接管所有权"})
        else:
            plan["conflicts"].append({"path": relative, "reason": "未知同名文件；保留原文且不接管所有权", "blocking": False})
    if overview is not None:
        relative = "docs/project/overview.md"
        path = _destination(target, relative)
        before = expected[relative] = _snapshot(path)
        if before is None:
            write(relative, overview, "按显式提供的内容创建项目总纲草案；业务正文由项目拥有")
        elif before == _sha(overview):
            plan["preserved"].append({"path": relative, "reason": "已有相同总纲草案；不接管业务正文"})
        else:
            plan["conflicts"].append({"path": relative, "reason": "项目总纲已存在；保留业务正文待人工合并", "blocking": False})
    manifest = {"schema_version": 1, "system_version": version,
                "status": "partial" if plan["conflicts"] else "installed",
                "owned_files": owned_files, "owned_blocks": owned_blocks}
    manifest_path = _destination(target, MANIFEST)
    expected[MANIFEST] = _snapshot(manifest_path)
    content = (json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    write(MANIFEST, content, "记录实际托管的文件与区块基线")
    if plan["conflicts"]:
        plan["status"] = "partial"
    elif not plan["actions"]:
        plan["status"] = "noop"
        plan["stages"]["installed"] = True
    return plan


def _atomic_write(path: Path, content: bytes, *, create: bool) -> None:
    """Use an exclusive temporary sibling and atomic publication; never replace on create."""
    fd, temporary = tempfile.mkstemp(prefix=".ai-docs-write-", dir=path.parent)
    temporary_path = Path(temporary)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fchmod(stream.fileno(), (path.stat().st_mode & 0o777) if path.exists() else 0o644)
            os.fsync(stream.fileno())
        if create:
            os.link(temporary_path, path)
        else:
            os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)


def bootstrap(source: Path, target: Path, mode: str = "auto", *, dry_run: bool = True,
              plan: dict | None = None, overview_title: str | None = None,
              overview_summary: str | None = None) -> dict:
    """Incrementally install a reviewed plan, preserving local facts and conflicting edits."""
    source = source.resolve()
    target = _target_root(target)
    planned = plan_install(source, target, mode, overview_title=overview_title,
                           overview_summary=overview_summary) if plan is None else plan
    if planned.get("source") != str(source) or planned.get("target") != str(target):
        raise InstallError("变更计划的源或目标与本次调用不一致")
    result = {key: value for key, value in planned.items() if not key.startswith("_")}
    result.update({"dry_run": dry_run, "applied": False})
    result["stages"] = dict(planned["stages"])
    if dry_run or planned["status"] == "blocked":
        return result
    payloads = planned.get("_payloads", {})
    expected = planned.get("_expected", {})
    action_paths = [item["path"] for item in planned["actions"]]
    if len(set(action_paths)) != len(action_paths) or set(payloads) != set(action_paths):
        raise InstallError("变更计划的动作与内容不一致")
    permitted = set(installation_files(source)) | {MANIFEST}
    if planned.get("business_documents") == ["docs/project/overview.md"]:
        permitted.add("docs/project/overview.md")
    if not set(action_paths).issubset(permitted):
        raise InstallError("变更计划包含参考包以外的写入路径")
    decoded = {}
    for item in planned["actions"]:
        relative = item["path"]
        _destination(target, relative)
        try:
            content = base64.b64decode(payloads[relative], validate=True)
        except (ValueError, TypeError) as exc:
            raise InstallError("变更计划内容编码无效") from exc
        if relative not in expected or item["before_sha256"] != expected[relative] or _sha(content) != item["after_sha256"]:
            raise InstallError("变更计划的内容哈希不一致")
        decoded[relative] = content
    for relative, baseline in expected.items():
        if _snapshot(_destination(target, relative)) != baseline:
            raise InstallError(f"计划生成后目标已有变化；请重新盘点：{relative}")
    if not action_paths:
        result["applied"] = True
        return result
    created_dirs = []
    changes = []
    lock_path = target / LOCK
    lock_fd = None

    def ensure_parent(parent: Path) -> None:
        missing = []
        while not parent.exists():
            missing.append(parent)
            parent = parent.parent
        for directory in reversed(missing):
            directory.mkdir()
            created_dirs.append(directory)

    try:
        ensure_parent(target)
        try:
            lock_fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0), 0o600)
        except FileExistsError as exc:
            raise InstallError(f"安装锁已存在；先确认其他安装是否结束：{lock_path}") from exc
        os.write(lock_fd, f"pid={os.getpid()}\n".encode("ascii"))
        # Validate once more after taking the cooperative lock, then before each write.
        for relative, baseline in expected.items():
            if _snapshot(_destination(target, relative)) != baseline:
                raise InstallError(f"等待安装锁期间目标已有变化：{relative}")
        for relative in action_paths:
            path = _destination(target, relative)
            baseline = expected[relative]
            if _snapshot(path) != baseline:
                raise InstallError(f"应用期间目标已有变化：{relative}")
            original = path.read_bytes() if baseline is not None else None
            ensure_parent(path.parent)
            content = decoded[relative]
            # Register first so a failure after atomic publication is also rolled back.
            changes.append((path, original, _sha(content)))
            _atomic_write(path, content, create=baseline is None)
        result["applied"] = True
        result["status"] = "partial" if planned["conflicts"] else "installed"
        result["stages"]["installed"] = not bool(planned["conflicts"])
    except (OSError, ValueError):
        for path, original, written_hash in reversed(changes):
            # Do not erase someone else's concurrent change while recovering our writes.
            if _snapshot(path) != written_hash:
                continue
            if original is None:
                path.unlink(missing_ok=True)
            else:
                _atomic_write(path, original, create=False)
        raise
    finally:
        if lock_fd is not None:
            os.close(lock_fd)
            lock_path.unlink(missing_ok=True)
        for directory in reversed(created_dirs):
            try:
                directory.rmdir()
            except OSError:
                pass
    return result


def cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--mode", choices=("auto", "init", "adopt", "upgrade"))
    parser.add_argument("--apply", action="store_true", help="增量模式应用变更；默认只生成计划")
    parser.add_argument("--overview-title")
    parser.add_argument("--overview-summary")
    args = parser.parse_args(argv)
    try:
        if args.mode is None:
            if args.apply:
                raise InstallError("--apply 必须与 --mode 一起使用；旧安装接口仍严格拒绝覆盖")
            result = install(args.source, args.target, dry_run=args.dry_run,
                             overview_title=args.overview_title, overview_summary=args.overview_summary)
        else:
            if args.apply and args.dry_run:
                raise InstallError("--apply 与 --dry-run 不能同时使用")
            result = bootstrap(args.source, args.target, args.mode, dry_run=not args.apply,
                               overview_title=args.overview_title, overview_summary=args.overview_summary)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 2 if result.get("status") == "blocked" else 0
    except (InstallError, OSError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(cli())
