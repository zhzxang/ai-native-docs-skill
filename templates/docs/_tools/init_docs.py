#!/usr/bin/env python3
"""Initialize a lightweight AI documentation project using shared Skill resources.

Python >=3.10, standard library only. Every installation creates only four managed
entries and docs/.ai-docs.json; project facts and conflicting local edits survive.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import importlib.util
import copy
import json
import os
from pathlib import Path
import re
import sys
import tempfile


class InstallError(ValueError):
    pass


CONFIG = "docs/.ai-docs.json"
MANIFEST = CONFIG
LEGACY_MANIFEST = "docs/_system/installation.json"
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


def _json_file(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError("JSON 顶层需要为对象")
        return value
    except (OSError, UnicodeError, ValueError) as exc:
        raise InstallError(f"无法读取配置，保留现场并先修复：{path}: {exc}") from exc


def _validate_ownership(value: dict, target: Path, *, legacy: bool) -> dict:
    if (not isinstance(value, dict) or type(value.get("schema_version")) is not int or value["schema_version"] != 1
            or not isinstance(value.get("system_version"), str)
            or not isinstance(value.get("owned_blocks"), dict)
            or (legacy and not isinstance(value.get("owned_files"), dict))):
        raise InstallError("安装清单格式不兼容；不接管或覆盖现有文件")
    collections = [value["owned_blocks"]]
    if legacy:
        collections.append(value["owned_files"])
    elif "owned_files" in value:
        raise InstallError("轻量安装清单不应登记通用资源文件")
    for collection in collections:
        for relative, record in collection.items():
            _destination(target, relative)
            if (not isinstance(record, dict)
                    or not re.fullmatch(r"[0-9a-f]{64}", str(record.get("sha256", "")))):
                raise InstallError(f"安装清单基线无效：{relative}")
    for relative, record in value["owned_blocks"].items():
        if relative not in ENTRY_FILES or record.get("id") != BLOCK_ID:
            raise InstallError(f"安装清单包含未知托管区块：{relative}")
    if legacy:
        for relative in value["owned_files"]:
            if relative == LEGACY_MANIFEST:
                raise InstallError("旧安装清单不能把自身登记为资源资产")
            if not relative.startswith(("docs/_system/", "docs/_tools/", "docs/_templates/")):
                raise InstallError(f"旧安装清单包含未知资源路径：{relative}")
    return value


def _read_legacy_manifest(target: Path) -> dict | None:
    path = _destination(target, LEGACY_MANIFEST)
    return _validate_ownership(_json_file(path), target, legacy=True) if path.exists() else None


def _read_manifest(target: Path) -> dict | None:
    path = _destination(target, CONFIG)
    if path.exists():
        config = _json_file(path)
        if type(config.get("schema_version")) is not int or config["schema_version"] != 1:
            raise InstallError("docs/.ai-docs.json 格式不兼容；先显式迁移，保留原文")
        if "installation" not in config:
            return None
        return _validate_ownership(config["installation"], target, legacy=False)
    return _read_legacy_manifest(target)


def _runtime(source: Path):
    path = source / "docs/_tools/ai_docs_runtime.py"
    if not path.is_file() or path.is_symlink():
        raise InstallError("参考包缺少有效轻量资源定位工具：docs/_tools/ai_docs_runtime.py")
    name = "_ai_docs_runtime_" + _sha(str(path).encode())[:12]
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


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
            "installation_error": installation_error,
            "installation_origin": CONFIG if (target / CONFIG).exists() else
            LEGACY_MANIFEST if (target / LEGACY_MANIFEST).exists() else None,
            "project_files": sorted(project_files),
            "markdown_documents": documents, "symlinks": sorted(symlinks), "truncated": truncated}


def installation_files(source: Path) -> dict[str, bytes]:
    """The project receives only entry points; shared resources remain in the Skill."""
    source = source.resolve()
    files = {}
    for old, new in {"_AGENTS.md": "AGENTS.md", "_README.md": "README.md",
                     "docs/_AGENTS.md": "docs/AGENTS.md", "docs/_README.md": "docs/README.md"}.items():
        path = source / old
        if not path.is_file() or path.is_symlink():
            raise InstallError(f"缺少有效入口源：{old}")
        files[new] = path.read_bytes()
    return files


def install(source: Path, target: Path, *, dry_run: bool = False,
            overview_title: str | None = None, overview_summary: str | None = None) -> dict:
    """Compatibility API: strictly initialize an empty target using the light protocol."""
    result = bootstrap(source, target, "init", dry_run=dry_run,
                       overview_title=overview_title, overview_summary=overview_summary)
    if result["status"] == "blocked":
        raise InstallError("目标已有内容或配置冲突；请使用 adopt/auto 增量接入，拒绝覆盖")
    result["files"] = sorted(action["path"] for action in result["actions"]
                             if action["operation"] != "delete")
    return result


def _system_version(source: Path) -> str:
    package = _json_file(source / "docs/_system/package.json")
    version = package.get("system_version", package.get("version"))
    if not isinstance(version, str) or not version.strip():
        raise InstallError("参考包需要非空 system_version")
    return version.strip()


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


def _route_resources(source: Path, value: dict) -> dict:
    routes = value.get("overrides", {}).get("routes", {}).get("routes", [])
    for route in routes:
        refs = list(route.get("must_read", [])) + list(route.get("write_back", []))
        for condition in route.get("read_when", []):
            refs.extend(condition.get("paths", []))
        for ref in refs:
            relative = ref if isinstance(ref, str) else ref.get("optional_path")
            if (isinstance(relative, str) and relative not in CONFIG_FILES
                    and relative.startswith(("docs/_system/", "docs/_templates/", "docs/_tools/"))):
                resource = _destination(source, relative)
                if not resource.is_file():
                    raise InstallError(f"自定义路由引用不存在的共享 Skill 资源：{relative}；需显式迁移后再接入")
    return value


def _configuration(source: Path, target: Path, expected: dict, conflicts: list) -> dict:
    runtime = _runtime(source)
    path = _destination(target, CONFIG)
    expected[CONFIG] = _snapshot(path)
    if path.exists():
        value = _json_file(path)
        if "installation" not in value:
            value["installation"] = {"schema_version": 1,
                                     "system_version": value["system"].get("version")
                                     if isinstance(value.get("system"), dict) else None,
                                     "status": "installed", "owned_blocks": {}}
        try:
            runtime.validate_config(value, resources=source, check_version=False)
        except ValueError as exc:
            raise InstallError(str(exc)) from exc
        return _route_resources(source, value)
    value = runtime.default_config(resources=source)
    legacy = {}
    for relative in sorted(CONFIG_FILES):
        current = _destination(target, relative)
        expected[relative] = _snapshot(current)
        if not current.exists():
            continue
        data = _json_file(current)
        if relative.endswith("project-map.json"):
            if type(data.get("schema_version")) is not int or data["schema_version"] != 1:
                raise InstallError("旧 project-map 配置 schema_version 不兼容；需显式迁移")
            mapped = {"project", "work_tracking", "locations", "readiness", "schema_version"}
            for key in ("project", "work_tracking", "locations", "readiness"):
                if key in data:
                    value[key] = copy.deepcopy(data[key])
            remaining = {key: copy.deepcopy(item) for key, item in data.items() if key not in mapped}
            if remaining:
                legacy[relative] = remaining
        elif relative.endswith("commands.json"):
            if type(data.get("schema_version")) is not int or data["schema_version"] != 1:
                raise InstallError("旧 commands 配置 schema_version 不兼容；需显式迁移")
            value["commands"] = copy.deepcopy(data.get("commands", []))
            remaining = {key: copy.deepcopy(item) for key, item in data.items()
                         if key not in {"schema_version", "commands"}}
            if remaining:
                legacy[relative] = remaining
        else:
            reference = _json_file(source / relative)
            if data != reference:
                key = "collections" if relative.endswith("collections.json") else "routes"
                value.setdefault("overrides", {})[key] = copy.deepcopy(data)
    if legacy:
        # Only unmapped notes/fields survive here; each active fact has one editable source.
        value["migration"] = {"legacy_fields": legacy}
    try:
        runtime.validate_config(value, resources=source, check_version=False)
    except ValueError as exc:
        raise InstallError(f"旧配置与轻量协议不兼容；保留原文等待显式迁移：{exc}") from exc
    return _route_resources(source, value)


def _external_references(target: Path, relative: str, ignored: set[str],
                         entry_baselines: dict | None = None,
                         configuration: dict | None = None) -> list[str]:
    """Conservatively retain assets referenced outside entries or retired owned assets."""
    references = []
    if configuration:
        active = {key: value for key, value in configuration.items()
                  if key not in {"migration", "installation", "system", "overrides"}}
        raw_config = json.dumps(active, ensure_ascii=False)
        if relative in raw_config:
            references.append(CONFIG)
    if not target.exists():
        return references
    for directory, dirs, names in os.walk(target, followlinks=False):
        dirs[:] = [name for name in dirs if name not in (SCAN_EXCLUDED - {"_templates"})
                   and not (Path(directory) / name).is_symlink()]
        for name in names:
            path = Path(directory) / name
            rel = path.relative_to(target).as_posix()
            if rel in ignored or path.is_symlink() or not path.is_file():
                continue
            if path.suffix.lower() not in {".md", ".json", ".yaml", ".yml", ".txt", ".toml", ".py", ".js", ".sh"}:
                continue
            try:
                content = path.read_bytes()
                if rel in ENTRY_FILES and entry_baselines and rel in entry_baselines:
                    try:
                        block = _existing_block(content)
                    except InstallError:
                        block = None
                    if block is not None and _sha(block[2]) == entry_baselines[rel]["sha256"]:
                        content = content[:block[0]] + content[block[1]:]
                raw = content.decode("utf-8")
            except (OSError, UnicodeError):
                continue
            # Both repository-relative command paths and Markdown-relative links count.
            candidates = re.findall(r"[^\s\"'<>`\[\]()]+", raw)
            if relative in raw or any(
                os.path.normpath(os.path.relpath(path.parent / token.split("#")[0].split("?")[0], target)) == relative
                for token in candidates if "_system/" in token or "_tools/" in token or "_templates/" in token
            ):
                references.append(rel)
    return sorted(set(references))


def plan_install(source: Path, target: Path, mode: str = "auto", *,
                 overview_title: str | None = None, overview_summary: str | None = None) -> dict:
    """Build a reviewable same-plan update; planning never writes to the target."""
    if mode not in {"auto", "init", "adopt", "upgrade"}:
        raise InstallError(f"未知初始化模式：{mode}")
    overview = _overview_bytes(overview_title, overview_summary)
    source, target = source.resolve(), _target_root(target)
    if source == target or source in target.parents:
        raise InstallError("目标必须位于参考包之外")
    for relative in ENTRY_FILES | {CONFIG, LEGACY_MANIFEST}:
        _destination(target, relative)
    inventory = scan(target)
    selected_mode = inventory["mode_hint"] if mode == "auto" else mode
    files, version = installation_files(source), _system_version(source)
    plan = {"source": str(source), "target": str(target), "mode": selected_mode,
            "status": "planned", "system_version": version, "actions": [], "conflicts": [],
            "preserved": [], "stages": {"installed": False, "configured": None, "strict_ready": None},
            "business_documents": ["docs/project/overview.md"] if overview is not None else [],
            "_payloads": {}, "_expected": {},
            "note": "仅写入四个入口与 docs/.ai-docs.json；通用协议、工具和模板从 Skill 读取。未确认业务内容不创建。"}
    if inventory["installation_error"]:
        plan["conflicts"].append({"path": inventory["installation_origin"] or CONFIG,
                                  "reason": inventory["installation_error"], "blocking": True})
    if selected_mode == "init" and inventory["mode_hint"] != "init":
        plan["conflicts"].append({"path": ".", "reason": "init 仅用于空项目；已有内容请使用 adopt 或 auto", "blocking": True})
    if selected_mode == "upgrade" and not inventory["installation"]:
        plan["conflicts"].append({"path": CONFIG, "reason": "upgrade 需要有效安装清单；未登记项目请先 adopt", "blocking": True})
    if any(item["blocking"] for item in plan["conflicts"]):
        plan["status"] = "blocked"
        return plan
    expected = plan["_expected"]
    try:
        config = _configuration(source, target, expected, plan["conflicts"])
        legacy = _read_legacy_manifest(target)
        expected[LEGACY_MANIFEST] = _snapshot(_destination(target, LEGACY_MANIFEST))
    except InstallError as exc:
        plan["conflicts"].append({"path": CONFIG, "reason": str(exc), "blocking": True})
        plan["status"] = "blocked"
        return plan
    previous = inventory["installation"] or {}
    owned_blocks = copy.deepcopy(previous.get("owned_blocks", {}))

    def write(relative: str, content: bytes, reason: str) -> None:
        before = expected[relative]
        if before == _sha(content):
            return
        plan["actions"].append({"path": relative, "operation": "create" if before is None else "update",
                                "reason": reason, "before_sha256": before, "after_sha256": _sha(content)})
        plan["_payloads"][relative] = base64.b64encode(content).decode("ascii")

    def delete(relative: str, reason: str) -> None:
        plan["actions"].append({"path": relative, "operation": "delete", "reason": reason,
                                "before_sha256": expected[relative], "after_sha256": None})

    for relative in sorted(files):
        path = _destination(target, relative)
        before = expected[relative] = _snapshot(path)
        block = _entry_content(relative, files)
        if before is None:
            write(relative, block, "创建轻量托管入口")
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
                write(relative, raw + separator + block, "追加轻量入口，保留原文")
                owned_blocks[relative] = {"id": BLOCK_ID, "sha256": _sha(block)}
            else:
                start, end, current = current_block
                if not baseline:
                    raise InstallError("现有区块没有安装基线；不接管未知托管标记")
                if _sha(current) != baseline["sha256"]:
                    raise InstallError("托管区块已有本地修改；保留内容待合并")
                write(relative, raw[:start] + block + raw[end:], "更新未修改的托管入口")
                owned_blocks[relative] = {"id": BLOCK_ID, "sha256": _sha(block)}
                if current == block:
                    plan["preserved"].append({"path": relative, "reason": "托管区块已是当前版本"})
        except (UnicodeError, InstallError) as exc:
            plan["conflicts"].append({"path": relative, "reason": str(exc), "blocking": False})
    if overview is not None:
        relative = "docs/project/overview.md"
        before = expected[relative] = _snapshot(_destination(target, relative))
        if before is None:
            write(relative, overview, "按明确提供的内容创建项目总纲草案；业务正文由项目拥有")
        elif before == _sha(overview):
            plan["preserved"].append({"path": relative, "reason": "已有相同总纲草案；不接管业务正文"})
        else:
            plan["conflicts"].append({"path": relative, "reason": "项目总纲已存在；保留业务正文待合并", "blocking": False})
    if legacy:
        owned_files = legacy["owned_files"]
        retired = set(owned_files) | {LEGACY_MANIFEST, CONFIG}
        retained = []
        for relative, record in sorted(owned_files.items()):
            path = _destination(target, relative)
            before = expected[relative] = _snapshot(path)
            if before is None:
                continue
            if before != record["sha256"]:
                retained.append(relative)
                plan["conflicts"].append({"path": relative, "reason": "旧资源已有本地修改；保留原文及旧所有权清单待迁移", "blocking": False})
                continue
            refs = _external_references(target, relative, retired, previous.get("owned_blocks", {}), config)
            if refs:
                retained.append(relative)
                plan["conflicts"].append({"path": relative, "reason": "旧资源仍被项目引用，保留直到引用迁移：" + ", ".join(refs), "blocking": False})
            else:
                delete(relative, "迁出未修改且无项目引用的旧托管资源；项目事实已保存在单一配置中")
        # References from retained custom assets must also protect their dependencies.
        while True:
            deleted = {item["path"] for item in plan["actions"] if item["operation"] == "delete"}
            added = []
            for relative in sorted(deleted):
                refs = _external_references(target, relative, retired - set(retained), previous.get("owned_blocks", {}), config)
                if refs:
                    added.append(relative)
                    plan["conflicts"].append({"path": relative, "reason": "保留旧定制资源依赖：" + ", ".join(refs), "blocking": False})
            if not added:
                break
            retained.extend(added)
            plan["actions"] = [item for item in plan["actions"] if item["path"] not in added]
        if retained:
            plan["preserved"].append({"path": LEGACY_MANIFEST, "reason": "旧资源尚待迁移；保留原始所有权基线"})
        else:
            delete(LEGACY_MANIFEST, "旧通用资源迁出完成；安装基线转入 docs/.ai-docs.json")
    config = copy.deepcopy(config)
    config.setdefault("system", {})["name"] = "ai-docs-system"
    config["system"]["version"] = version
    installation = config.setdefault("installation", {})
    installation.update({"schema_version": 1, "system_version": version,
                         "status": "partial" if plan["conflicts"] else "installed",
                         "owned_blocks": owned_blocks})
    try:
        _runtime(source).validate_config(config, resources=source)
    except ValueError as exc:
        plan["actions"], plan["_payloads"] = [], {}
        plan["conflicts"].append({"path": CONFIG, "reason": str(exc), "blocking": True})
        plan["status"] = "blocked"
        return plan
    config_path = _destination(target, CONFIG)
    if config_path.is_file() and _json_file(config_path) == config:
        plan["preserved"].append({"path": CONFIG, "reason": "项目配置内容无变化，保留原格式"})
    else:
        write(CONFIG, (json.dumps(config, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(),
              "保存项目配置、协议版本及实际托管入口基线")
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
    actions = planned["actions"]
    action_paths = [item["path"] for item in actions]
    writes = {item["path"] for item in actions if item.get("operation") in {"create", "update"}}
    deletes = {item["path"] for item in actions if item.get("operation") == "delete"}
    if (len(set(action_paths)) != len(action_paths) or set(payloads) != writes
            or writes | deletes != set(action_paths)):
        raise InstallError("变更计划的动作与内容不一致")
    permitted = ENTRY_FILES | {CONFIG}
    if planned.get("business_documents") == ["docs/project/overview.md"]:
        permitted.add("docs/project/overview.md")
    legacy = _read_legacy_manifest(target)
    old_owned = legacy.get("owned_files", {}) if legacy else {}
    permitted_deletes = set(old_owned) | ({LEGACY_MANIFEST} if legacy else set())
    if not writes.issubset(permitted) or not deletes.issubset(permitted_deletes):
        raise InstallError("变更计划包含轻量安装入口以外的写入或未登记资产的删除")
    decoded = {}
    for item in actions:
        relative = item["path"]
        _destination(target, relative)
        if relative not in expected or item["before_sha256"] != expected[relative]:
            raise InstallError("变更计划的内容哈希不一致")
        if item["operation"] == "delete":
            if item["after_sha256"] is not None or expected[relative] in {None, "directory"}:
                raise InstallError("删除动作需要有效的原文基线")
            if relative in old_owned and expected[relative] != old_owned[relative]["sha256"]:
                raise InstallError("不能删除已有本地修改的旧资源")
            continue
        try:
            content = base64.b64decode(payloads[relative], validate=True)
        except (ValueError, TypeError) as exc:
            raise InstallError("变更计划内容编码无效") from exc
        if _sha(content) != item["after_sha256"]:
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
        if deletes:
            active_config = json.loads(decoded[CONFIG]) if CONFIG in decoded else _json_file(_destination(target, CONFIG))
            baselines = (_read_manifest(target) or {}).get("owned_blocks", {})
            ignored = deletes | {LEGACY_MANIFEST, CONFIG}
            for relative in sorted(deletes - {LEGACY_MANIFEST}):
                refs = _external_references(target, relative, ignored, baselines, active_config)
                if refs:
                    raise InstallError(f"计划生成后旧资源仍被项目引用；请重新盘点：{relative}: " + ", ".join(refs))
        for item in actions:
            relative = item["path"]
            path = _destination(target, relative)
            baseline = expected[relative]
            if _snapshot(path) != baseline:
                raise InstallError(f"应用期间目标已有变化：{relative}")
            original = path.read_bytes() if baseline is not None else None
            ensure_parent(path.parent)
            if item["operation"] == "delete":
                changes.append((path, original, None))
                path.unlink()
            else:
                content = decoded[relative]
                # Register before atomic publication so post-write failures recover as well.
                changes.append((path, original, _sha(content)))
                _atomic_write(path, content, create=baseline is None)
        # Only empty retired resource directories are removed; unknown assets survive.
        for folder in ("docs/_system", "docs/_tools", "docs/_templates"):
            if not any(relative.startswith(folder + "/") for relative in deletes):
                continue
            root = _destination(target, folder)
            if root.is_dir():
                for directory in sorted((item for item in root.rglob("*") if item.is_dir()),
                                        key=lambda item: len(item.parts), reverse=True):
                    try:
                        if not directory.is_symlink():
                            directory.rmdir()
                    except OSError:
                        pass
                try:
                    root.rmdir()
                except OSError:
                    pass
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
                _atomic_write(path, original, create=not path.exists())
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
