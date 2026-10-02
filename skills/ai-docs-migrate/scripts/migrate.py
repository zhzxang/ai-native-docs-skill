#!/usr/bin/env python3
"""Inventory, preview and apply explicitly mapped Markdown document migrations.

Python >=3.10; standard library only. Initialization and semantic classification
are separate operations. The review plan contains every proposed file's content.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import posixpath
import re
import sys
import tempfile
from typing import Any
from urllib.parse import quote, unquote, urlsplit

SKIP = {".git", "node_modules", ".venv", "venv", "__pycache__", ".cache", ".next", "dist", "build"}
CONFIG = "docs/.ai-docs.json"
LOCK = "docs/.docctl.lock"
FORMAT = "ai-docs-migration-plan-v1"
ENTRY_FILES = {"README.md", "AGENTS.md", "docs/README.md", "docs/AGENTS.md"}
SINGLETONS = {
    "project-overview": "docs/_templates/reference/project/overview.md",
    "architecture-overview": "docs/_templates/reference/engineering/architecture/overview.md",
    "development-guide": "docs/_templates/reference/engineering/development/quickstart.md",
}


class MigrationError(ValueError):
    """An unsafe or unsupported migration; no semantic guesses are made."""


def digest(data: bytes | str) -> str:
    return hashlib.sha256(data.encode("utf-8") if isinstance(data, str) else data).hexdigest()


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def load_tool(source: Path):
    path = source / "docs/_tools/docctl.py"
    spec = importlib.util.spec_from_file_location("ai_docs_migration_docctl", path)
    if spec is None or spec.loader is None:
        raise MigrationError(f"缺少 Skill 校验工具：{path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    previous = sys.dont_write_bytecode
    try:
        sys.dont_write_bytecode = True
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
    return module


def reject_symlinks(path: Path) -> None:
    path = path.absolute()
    for candidate in (path, *path.parents):
        # macOS's system-owned temporary directory aliases are stable platform paths.
        if candidate.is_symlink() and str(candidate) not in {"/tmp", "/var"}:
            raise MigrationError(f"拒绝符号链接或符号链接祖先：{candidate}")


def safe_path(root: Path, relative: str) -> Path:
    if (not isinstance(relative, str) or not relative or Path(relative).is_absolute()
            or any(part in {"..", ".git"} for part in Path(relative).parts)
            or "\\" in relative or "\x00" in relative):
        raise MigrationError(f"需要安全的仓库相对路径：{relative}")
    path = root / relative
    reject_symlinks(path)
    if not path.resolve().is_relative_to(root.resolve()):
        raise MigrationError(f"路径越过仓库边界：{relative}")
    return path


def tree(root: Path) -> list[Path]:
    """Enumerate repository material without following symbolic links."""
    paths = []
    for directory, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = sorted(d for d in dirs if d not in SKIP)
        for name in dirs + sorted(files):
            paths.append(Path(directory) / name)
    return sorted(paths)


def markdown_files(root: Path) -> list[Path]:
    files = []
    for path in tree(root):
        if path.suffix.lower() == ".md":
            safe_path(root, path.relative_to(root).as_posix())
            if path.is_file():
                files.append(path)
    return files


def snapshot(root: Path) -> dict[str, str]:
    paths = markdown_files(root)
    for path in tree(root / "docs/_generated"):
        if path.is_file():
            safe_path(root, path.relative_to(root).as_posix())
            paths.append(path)
    config = safe_path(root, CONFIG)
    if config.is_file():
        paths.append(config)
    return {path.relative_to(root).as_posix(): digest(path.read_bytes()) for path in sorted(set(paths))}


def resource_hashes(source: Path) -> dict[str, str]:
    for path in tree(source):
        reject_symlinks(path)
    return {path.relative_to(source).as_posix(): digest(path.read_bytes())
            for path in tree(source) if path.is_file() and not path.is_symlink()
            and path.suffix != ".pyc"}


def inventory(target: Path, source: Path) -> dict[str, Any]:
    reject_symlinks(target)
    reject_symlinks(source)
    root = target.resolve()
    if not root.is_dir():
        raise MigrationError("盘点需要已有项目根目录")
    tool = load_tool(source.resolve())
    documents = []
    for path in markdown_files(root):
        raw = path.read_text(encoding="utf-8")
        record = {"path": path.relative_to(root).as_posix(), "sha256": digest(path.read_bytes()),
                  "bytes": path.stat().st_size, "anchors": sorted(tool.markdown_anchors(raw))}
        try:
            entries = tool.document_entries(raw, record["path"])
            record["entries"] = [{"meta": e["meta"], "title": e["title"]} for e in entries]
            record["format"] = "redirect" if tool.has_redirect_marker(raw) else "compact" if len(entries) > 1 else "frontmatter" if tool.parse_frontmatter(raw) is not None else "markdown"
        except ValueError as exc:
            record.update(format="unsupported-meta", error=str(exc))
        documents.append(record)
    return {"target": str(root), "initialized": (root / CONFIG).is_file(),
            "documents": documents, "ignored_directories": sorted(SKIP),
            "limits": "只读盘点 Markdown，不进行语义分类；依赖、缓存和构建产物目录不扫描。"}


def normalized_mapping(mapping: Any) -> list[dict[str, Any]]:
    entries = mapping.get("documents") if isinstance(mapping, dict) else mapping
    if not isinstance(entries, list) or not entries:
        raise MigrationError("mapping 需要非空 documents 数组")
    result = []
    sources = set()
    ids = set()
    for record in entries:
        if not isinstance(record, dict) or set(record) - {"source", "type", "id", "title", "slug", "meta", "destination"}:
            raise MigrationError("mapping 仅支持 source/type/id/title/slug/meta/destination")
        if any(not isinstance(record.get(key), str) or not record[key].strip()
               for key in ("source", "type", "id", "title", "slug")):
            raise MigrationError("每项映射必须显式指定 source/type/id/title/slug")
        if "\n" in record["title"] or "\r" in record["title"]:
            raise MigrationError("标题必须为单行文字")
        if record["source"] in sources or record["id"] in ids:
            raise MigrationError("映射包含重复 source 或 ID")
        if not isinstance(record.get("meta", {}), dict):
            raise MigrationError("mapping.meta 必须为对象，且只能补全原文不存在的事实")
        sources.add(record["source"])
        ids.add(record["id"])
        result.append({**record, "meta": record.get("meta", {})})
    return result


def adapt_body(tool, text: str, doc_id: str) -> tuple[str, dict[str, str]]:
    """Keep every body line; adjust ATX heading levels and retain section anchors."""
    visible = tool.without_code_fences(text)
    if re.search(r"^\s*(?:=+|-+)\s*$", visible, re.MULTILINE):
        # A standalone thematic break also matches. Distinguish an actual setext title.
        lines = visible.splitlines()
        if any(i and line.strip() and re.fullmatch(r"\s*(?:=+|-+)\s*", line)
               and lines[i - 1].strip() and not lines[i - 1].startswith(("#", ">", "-", "*"))
               for i, line in enumerate(lines)):
            raise MigrationError("迁移暂不支持 Setext 标题；请先显式转换为 # 标题")
    if re.search(r"\[\[|!?\[[^\]\n]*\]\([^\n)]*\(", visible):
        raise MigrationError("迁移暂不支持 Wiki 链接或目的地址内未转义的括号")
    if "```yaml doc-meta" in text:
        raise MigrationError("迁移输入必须为单个 Markdown 对象，不支持正文中的 doc-meta 或多对象旧集合")
    minimum = min((len(m.group(1)) for m in re.finditer(r"^(#{1,6})\s+", visible, re.MULTILINE)), default=3)
    amount = max(0, 3 - minimum)
    aliases = {}
    counts = {}
    lines = []
    fence = None
    for line in text.splitlines(keepends=True):
        marker = re.match(r"^\s*(`{3,}|~{3,})", line)
        if marker:
            if fence is None:
                fence = marker.group(1)
            elif marker.group(1)[0] == fence[0] and len(marker.group(1)) >= len(fence):
                fence = None
            lines.append(line)
            continue
        if fence is None:
            def anchor_replace(match):
                old = match.group(1)
                new = old if old == doc_id.lower() or old.startswith(doc_id.lower() + "--") else doc_id.lower() + "--" + old
                aliases[old] = new
                return f'<a id="{new}"></a>'
            line = tool.ANCHOR_RE.sub(anchor_replace, line)
            heading = re.match(r"^(#{1,6})\s+(.+?)(?:\s+#+)?\s*$", line)
            if heading:
                anchor = tool.heading_anchor(heading.group(2))
                count = counts.get(anchor, 0)
                counts[anchor] = count + 1
                old = anchor + (f"-{count}" if count else "")
                new = doc_id.lower() + "--" + old
                aliases[old] = new
                lines.append(f'<a id="{new}"></a>\n')
                line = re.sub(r"^(#{1,6})(\s+)", lambda m: "#" * min(6, len(m.group(1)) + amount) + m.group(2), line)
        lines.append(line)
    body = "".join(lines)
    return body if body.endswith("\n") else body + "\n", aliases


def split_destination(raw: str) -> tuple[str, str, bool]:
    if raw.startswith("<") and ">" in raw:
        closing = raw.index(">")
        return raw[1:closing], raw[closing + 1:], True
    match = re.match(r"(\S+)(.*)", raw, re.DOTALL)
    return (match.group(1), match.group(2), False) if match else (raw, "", False)


def rewrite_links(tool, root: Path, text: str, old: str, new: str,
                  locations: dict[str, dict[str, Any]]) -> str:
    """Repair ordinary inline/reference links and root-relative metadata *_ref."""
    def destination(value: str, metadata: bool = False) -> str:
        parsed = urlsplit(value)
        if parsed.scheme or parsed.netloc or tool.PLACEHOLDER_RE.search(value):
            return value
        if parsed.path.startswith("/"):
            if old != new:
                raise MigrationError(f"{old}: 绝对本地链接需人工处理：{value}")
            return value
        resolved = posixpath.normpath(posixpath.join("" if metadata else posixpath.dirname(old), unquote(parsed.path))) if parsed.path else old
        if resolved == ".." or resolved.startswith("../"):
            if old != new:
                raise MigrationError(f"{old}: 出链越过仓库边界：{value}")
            return value
        location = locations.get(resolved)
        fragment = unquote(parsed.fragment)
        if location:
            target = location["path"]
            if fragment:
                if fragment not in location["anchors"]:
                    raise MigrationError(f"{old}: 旧锚点无法唯一迁移：{value}")
                target, fragment = location["anchors"][fragment]
            else:
                fragment = location.get("anchor", "")
        else:
            target = resolved
        if not metadata and old == new and not location:
            return value
        if metadata:
            relative = target
        else:
            relative = "" if target == new and fragment else posixpath.relpath(target, posixpath.dirname(new) or ".")
        return quote(relative, safe="/-._~") + ("?" + parsed.query if parsed.query else "") + ("#" + quote(fragment, safe="-._~") if fragment else "")

    def ordinary(match):
        value, suffix, wrapped = split_destination(match.group(1))
        rewritten = destination(value)
        value = ("<" + rewritten + ">" if wrapped else rewritten) + suffix
        return match.group(0)[:match.start(1) - match.start()] + value + match.group(0)[match.end(1) - match.start():]

    lines = []
    fence = None
    metadata_fence = False
    frontmatter = text.lstrip("\ufeff").startswith("---\n")
    delimiters = 0
    for line in text.splitlines(keepends=True):
        if frontmatter and line.strip() == "---":
            delimiters += 1
            if delimiters == 2:
                frontmatter = False
            lines.append(line)
            continue
        marker = re.match(r"^\s*(`{3,}|~{3,})(.*)", line)
        if marker:
            if fence is None:
                fence = marker.group(1)
                metadata_fence = marker.group(2).strip() == "yaml doc-meta"
            elif marker.group(1)[0] == fence[0] and len(marker.group(1)) >= len(fence):
                fence = None
                metadata_fence = False
            lines.append(line)
            continue
        if frontmatter or metadata_fence:
            match = re.match(r"^([a-z][a-z0-9_]*_ref):\s*(.+?)(\r?\n)?$", line)
            if match:
                try:
                    value = json.loads(match.group(2))
                except json.JSONDecodeError:
                    value = None
                if isinstance(value, str):
                    line = match.group(1) + ": " + json.dumps(destination(value, True), ensure_ascii=False) + (match.group(3) or "")
        elif fence is None:
            for match in re.finditer(r"\b(?:href|src)\s*=\s*[\"']([^\"']+)[\"']", line, re.IGNORECASE):
                value = match.group(1)
                if destination(value) != value:
                    raise MigrationError(f"{old}: 本地 HTML href/src 引用需人工转换：{value}")
            for regex in (tool.LINK_RE, tool.REFERENCE_RE):
                line = regex.sub(ordinary, line)
        lines.append(line)
    return "".join(lines)


def stage_tree(root: Path, staged: Path) -> None:
    """Copy Markdown/config bytes; other assets are existence-only placeholders."""
    for path in tree(root):
        relative = path.relative_to(root)
        target = staged / relative
        if path.is_dir() and not path.is_symlink():
            target.mkdir(parents=True, exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            if path.suffix.lower() == ".md" or relative.as_posix() == CONFIG or relative.parts[:2] in (("docs", "_system"), ("docs", "_generated")):
                safe_path(root, relative.as_posix())
                target.write_bytes(path.read_bytes())
            else:
                target.touch()


def plan_migration(target: Path, source: Path, mapping: Any) -> dict[str, Any]:
    reject_symlinks(target)
    reject_symlinks(source)
    root = target.resolve()
    source = source.resolve()
    if root.is_relative_to(source) or source.is_relative_to(root):
        raise MigrationError("目标项目和共享 Skill 资源不得互相包含")
    if not safe_path(root, CONFIG).is_file():
        raise MigrationError("先初始化最小 AI 文档系统，再独立规划已授权范围的迁移")
    tool = load_tool(source)
    # Version and configuration compatibility are checked before processing bodies.
    tool.runtime(root)
    reg = tool.registry(root, resources=source)
    if reg.get("schema_version") != 2:
        raise MigrationError("迁移要求 schema_version 2 的集合布局")
    choices = {item["key"]: item for item in reg["collections"]}
    for typ, template in SINGLETONS.items():
        template_meta = tool.parse_frontmatter(tool.template_path(root, template).read_text(encoding="utf-8"), template)
        choices[typ] = {"key": typ, "template": template, "prefix": template_meta["id"].split("-", 1)[0],
                        "singleton_path": template.replace("docs/_templates/reference/", "docs/", 1)}
    records = normalized_mapping(mapping)
    before = snapshot(root)
    raw_files = {relative: (root / relative).read_text(encoding="utf-8")
                 for relative in before if relative.lower().endswith(".md")}
    groups = {}
    source_paths = {record["source"] for record in records}
    known_ids = {}
    for relative, raw in raw_files.items():
        if relative in source_paths:
            continue
        try:
            for entry in tool.document_entries(raw, relative):
                doc_id = entry["meta"].get("id")
                if isinstance(doc_id, str):
                    known_ids[doc_id] = relative
        except ValueError:
            pass
    for record in records:
        path = safe_path(root, record["source"])
        if record["source"] in ENTRY_FILES:
            raise MigrationError("不能整文件迁移协议入口 README/AGENTS；先在明确授权范围提取业务对象并保留托管入口")
        if any(part in SKIP for part in path.relative_to(root).parts) or path.suffix.lower() != ".md" or not path.is_file():
            raise MigrationError(f"仅支持扫描范围内的既有 Markdown 文件：{record['source']}")
        if record["type"] not in choices:
            raise MigrationError(f"未知文档类型：{record['type']}")
        item = choices[record["type"]]
        if not tool.ID_RE.fullmatch(record["id"]) or not record["id"].startswith(item["prefix"] + "-") or not tool.SLUG_RE.fullmatch(record["slug"]):
            raise MigrationError(f"ID/slug 与 {record['type']} 协议不兼容")
        if record["id"] in known_ids:
            raise MigrationError(f"ID 已存在：{record['id']} ({known_ids[record['id']]})")
        if "singleton_path" in item:
            destination = record.get("destination", item["singleton_path"])
            safe_path(root, destination)
            if (not destination.startswith("docs/") or Path(destination).suffix != ".md"
                    or any(part.startswith("_") or part.startswith(".") for part in Path(destination).parts)
                    or Path(destination).name in {"README.md", "AGENTS.md"}):
                raise MigrationError("单例 destination 必须为 docs/ 下的安全业务 Markdown 路径")
        else:
            if "destination" in record:
                raise MigrationError("集合布局由注册表决定，不接受 destination")
            base = item["base_path"]
            if record["source"] == base + ".md" or record["source"].startswith(base + "/"):
                raise MigrationError("输入已在所选集合中；请直接维护原条目")
        raw = path.read_text(encoding="utf-8")
        if tool.has_redirect_marker(raw) or tool.parse_compact_entries(raw, record["source"]):
            raise MigrationError("仅支持一个旧文件对应一个对象；薄入口和旧紧凑集合不能作为迁移输入")
        original = tool.parse_frontmatter(raw, record["source"])
        template = tool.template_path(root, item["template"]).read_text(encoding="utf-8")
        template_meta = tool.parse_frontmatter(template, item["template"])
        if not template_meta or template_meta.get("type") != record["type"] or template_meta.get("status") != "template":
            raise MigrationError("共享模板的 type/status 与集合不匹配")
        meta = {key: None for key in template_meta}
        meta.update(id=record["id"], type=record["type"], status="draft", authority=template_meta["authority"], slug=record["slug"])
        for key, value in (original or {}).items():
            if key in {"id", "type", "slug"} and value != record[key]:
                raise MigrationError(f"映射不得改变既有元数据 {key}：{record['source']}")
            meta[key] = value
        for key, value in record["meta"].items():
            if key in (original or {}) and original[key] != value:
                raise MigrationError(f"mapping.meta 不得覆盖既有事实 {key}：{record['source']}")
            if key in {"id", "type", "slug", "status", "authority"} and meta[key] != value:
                raise MigrationError(f"mapping.meta 不得改变身份、状态或authority：{key}")
            meta[key] = value
        if not hasattr(tool, "validate_meta"):
            raise MigrationError("共享资源缺少按类型 validate_meta；请使用匹配版本资源")
        meta_errors = tool.validate_meta(meta, record["source"], resources=source)
        if meta_errors:
            raise MigrationError("迁移元数据校验失败：" + "；".join(meta_errors))
        body, aliases = adapt_body(tool, tool.strip_frontmatter(raw.lstrip("\ufeff")), record["id"])
        entry = {"meta": meta, "title": record["title"], "slug": record["slug"],
                 "anchor": record["id"].lower(), "body": body,
                 "source": record["source"], "aliases": aliases}
        groups.setdefault(record["type"], []).append(entry)
    writes = {}
    locations = {}
    destination_records = []
    for typ, new_entries in groups.items():
        item = choices[typ]
        if "singleton_path" in item:
            if len(new_entries) != 1:
                raise MigrationError(f"单例类型 {typ} 一次只能映射一个对象")
            entry = new_entries[0]
            record = next(record for record in records if record["source"] == entry["source"])
            path = record.get("destination", item["singleton_path"])
            target_path = safe_path(root, path)
            if target_path.exists() and path != entry["source"]:
                raise MigrationError(f"拒绝覆盖既有单例：{path}；请先判断是否应合并同一对象")
            locations[entry["source"]] = {"path": path, "anchor": entry["anchor"],
                                        "anchors": {old: (path, new) for old, new in entry["aliases"].items()}}
            destination_records.append({"source": entry["source"], "path": path, "anchor": entry["anchor"],
                                        "id": entry["meta"]["id"], "type": typ, "meta": entry["meta"],
                                        "old_anchors": locations[entry["source"]]["anchors"]})
            writes[path] = {"text": tool.expanded_text(entry), "origin": entry["source"]}
            continue
        base = item["base_path"]
        compact = safe_path(root, base + ".md")
        expanded = safe_path(root, base)
        errors = tool.collection_errors(root, item)
        if errors:
            raise MigrationError("目标集合结构异常：" + "；".join(errors))
        old_entries = tool.parse_compact_entries(compact.read_text(encoding="utf-8"), base + ".md") if compact.is_file() else []
        existing = list(old_entries)
        if expanded.is_dir():
            existing = [entry for p in expanded.glob("*.md") for entry in tool.document_entries(p.read_text(encoding="utf-8"), str(p))]
        for entry in new_entries:
            for old_entry in existing + [other for other in new_entries if other is not entry]:
                if entry["slug"] == old_entry["meta"].get("slug") or tool.normalize_title(entry["title"]) == tool.normalize_title(old_entry["title"]):
                    raise MigrationError(f"同主题条目需人工查重：{entry['meta']['id']}")
        expand = expanded.is_dir() or len(old_entries) + len(new_entries) > 2
        if expand and old_entries:
            compact_anchors = {}
            # Global Markdown heading duplication counts differ after expansion.
            collection_anchor = tool.heading_anchor(item["title"])
            compact_anchors[collection_anchor] = (base, "")
            heading_counts = {collection_anchor: 1}
            for entry in old_entries:
                doc_id = entry["meta"]["id"]
                path = f"{base}/{doc_id}-{entry['slug']}.md"
                body, aliases = adapt_body(tool, entry["body"], doc_id)
                original_body = entry["body"]
                entry = {**entry, "body": body}
                writes[path] = {"text": tool.expanded_text(entry), "origin": base + ".md"}
                compact_anchors[entry["anchor"]] = (path, entry["anchor"])
                title_anchor = tool.heading_anchor(doc_id + " · " + entry["title"])
                title_count = heading_counts.get(title_anchor, 0)
                heading_counts[title_anchor] = title_count + 1
                compact_anchors[title_anchor + (f"-{title_count}" if title_count else "")] = (path, title_anchor)
                local_counts = {}
                # Explicit anchors retain their names; generated heading anchors use
                # document-wide numbering in the old aggregate, per-entry after expansion.
                for old_anchor in tool.ANCHOR_RE.findall(tool.without_code_fences(original_body)):
                    if old_anchor in compact_anchors and old_anchor != entry["anchor"]:
                        raise MigrationError("旧紧凑集合含重复显式锚点，无法唯一迁移")
                    compact_anchors[old_anchor] = (path, aliases.get(old_anchor, old_anchor))
                for match in re.finditer(r"^#{1,6}\s+(.+?)(?:\s+#+)?$", tool.without_code_fences(original_body), re.MULTILINE):
                    heading_anchor = tool.heading_anchor(match.group(1))
                    local_count = local_counts.get(heading_anchor, 0)
                    local_counts[heading_anchor] = local_count + 1
                    old_local = heading_anchor + (f"-{local_count}" if local_count else "")
                    global_count = heading_counts.get(heading_anchor, 0)
                    heading_counts[heading_anchor] = global_count + 1
                    old_global = heading_anchor + (f"-{global_count}" if global_count else "")
                    compact_anchors[old_global] = (path, aliases[old_local])
            locations[base + ".md"] = {"path": base, "anchor": "", "anchors": compact_anchors}
            writes[base + ".md"] = {"text": '<!-- doc-redirect -->\n# ' + item["title"] + '\n\n集合已迁移展开，以下为新位置。\n\n' + "\n".join(f'- [{e["meta"]["id"]}]({posixpath.basename(base)}/{e["meta"]["id"]}-{e["slug"]}.md#{e["anchor"]})' for e in old_entries) + "\n", "origin": base + ".md", "redirect": True}
        for entry in new_entries:
            path = f"{base}/{entry['meta']['id']}-{entry['slug']}.md" if expand else base + ".md"
            if expand and safe_path(root, path).exists():
                raise MigrationError(f"拒绝覆盖迁移目标：{path}")
            anchor = entry["anchor"]
            locations[entry["source"]] = {"path": path, "anchor": anchor,
                                        "anchors": {old: (path, new) for old, new in entry["aliases"].items()}}
            destination_records.append({"source": entry["source"], "path": path, "anchor": anchor,
                                        "id": entry["meta"]["id"], "type": typ, "meta": entry["meta"],
                                        "old_anchors": locations[entry["source"]]["anchors"]})
            if expand:
                writes[path] = {"text": tool.expanded_text(entry), "origin": entry["source"]}
        if not expand:
            # Bodies must be relocated separately before their relative origin is lost.
            parts = [tool.compact_entry_text(e) for e in old_entries]
            parts.extend(rewrite_links(tool, root, tool.compact_entry_text(e), e["source"], base + ".md", locations) for e in new_entries)
            writes[base + ".md"] = {"text": "# " + item["title"] + "\n\n" + "\n".join(parts), "origin": base + ".md", "pre_relocated": True}
    # Re-run compact relocation once every type's final target is known (cross-type links).
    for typ, entries in groups.items():
        if "singleton_path" in choices[typ]:
            continue
        base = choices[typ]["base_path"]
        if writes.get(base + ".md", {}).get("pre_relocated"):
            old_entries = tool.parse_compact_entries(raw_files.get(base + ".md", ""), base + ".md")
            parts = [tool.compact_entry_text(e) for e in old_entries]
            parts.extend(rewrite_links(tool, root, tool.compact_entry_text(e), e["source"], base + ".md", locations) for e in entries)
            writes[base + ".md"]["text"] = "# " + choices[typ]["title"] + "\n\n" + "\n".join(parts)
    for relative, data in list(writes.items()):
        if not data.get("redirect"):
            data["text"] = rewrite_links(tool, root, data["text"], data["origin"], relative, locations)
    for record in destination_records:
        source_path = record["source"]
        if source_path == record["path"]:
            continue
        relative = posixpath.relpath(record["path"], posixpath.dirname(source_path) or ".")
        writes[source_path] = {"text": '<!-- doc-redirect -->\n# ' + record["id"] + '\n\n正文已迁移，以下为新位置。\n\n' + f'<a id="{record["id"].lower()}"></a>\n' + f'[{record["id"]}]({quote(relative, safe="/-._~")}#{record["anchor"]})\n', "origin": source_path, "redirect": True}
    for relative, raw in raw_files.items():
        if relative in writes:
            continue
        rewritten = rewrite_links(tool, root, raw, relative, relative, locations)
        if rewritten != raw:
            writes[relative] = {"text": rewritten, "origin": relative}
    actions = []
    for relative, data in sorted(writes.items()):
        path = safe_path(root, relative)
        content = data["text"]
        original = path.read_bytes() if path.is_file() else None
        if original is not None and original == content.encode("utf-8"):
            continue
        actions.append({"operation": "update" if original is not None else "create", "path": relative,
                        "before_sha256": digest(original) if original is not None else None,
                        "content": content, "content_sha256": digest(content)})
    baseline = tool.validate(root, resources=source)
    with tempfile.TemporaryDirectory(prefix="ai-docs-migration-preview-") as temporary:
        staged = Path(temporary).resolve()
        stage_tree(root, staged)
        for action in actions:
            path = staged / action["path"]
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(action["content"], encoding="utf-8")
        if any((root / "docs/_generated" / name).exists() for name in ("indexes", "catalog")):
            for name in ("indexes", "catalog"):
                safe_path(root, "docs/_generated/" + name)
            tool.generate_indexes(staged, resources=source)
            generated_paths = {relative for relative in before
                               if relative.startswith(("docs/_generated/indexes/", "docs/_generated/catalog/"))}
            generated_paths.update(path.relative_to(staged).as_posix() for path in tree(staged / "docs/_generated")
                                   if path.is_file() and path.relative_to(staged).as_posix().startswith(
                                       ("docs/_generated/indexes/", "docs/_generated/catalog/")))
            actions = [action for action in actions if action["path"] not in generated_paths]
            for relative in sorted(generated_paths):
                original = safe_path(root, relative)
                candidate = staged / relative
                content = candidate.read_text(encoding="utf-8") if candidate.is_file() else None
                old_hash = before.get(relative)
                new_hash = digest(content) if content is not None else None
                if old_hash != new_hash:
                    actions.append({"operation": "delete" if content is None else "update" if old_hash else "create",
                                    "path": relative, "before_sha256": old_hash,
                                    "content": content, "content_sha256": new_hash})
            actions.sort(key=lambda action: action["path"])
        after = tool.validate(staged, resources=source)
        # Validate links in Markdown outside docs too, including legacy entry points.
        before_links = [error for rel, raw in raw_files.items() for error in tool.relative_link_errors(root, root / rel, raw)]
        after_links = [error for path in markdown_files(staged) for error in tool.relative_link_errors(staged, path, path.read_text(encoding="utf-8"))]
        new_errors = sorted((set(after["errors"]) - set(baseline["errors"])) | (set(after_links) - set(before_links)))
        validation = {"baseline": baseline, "candidate": after, "new_errors": new_errors,
                      "all_repository_links_checked": len(raw_files)}
    plan = {"format": FORMAT, "target": str(root), "source": str(source), "mapping": records,
            "inventory": before, "resources": resource_hashes(source), "documents": destination_records,
            "actions": actions, "validation": validation,
            "status": "blocked" if new_errors else "planned", "conflicts": new_errors,
            "limits": "仅支持一个 Markdown 文件对应一个显式对象；不分类、不批准、不移动附件，不更改既有事实。仓库外链接需调用方另行修复。"}
    plan["plan_sha256"] = digest(canonical(plan))
    if snapshot(root) != before:
        raise MigrationError("生成计划时仓库内容并发改变，请重新盘点")
    return plan


def atomic_write(path: Path, content: bytes, mode: int | None = None, *, exclusive: bool = False) -> None:
    descriptor, name = tempfile.mkstemp(prefix=".ai-docs-migrate-", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        if mode is not None:
            temporary.chmod(mode)
        if exclusive:
            os.link(temporary, path)
        else:
            os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def apply_plan(target: Path, source: Path, plan: dict[str, Any]) -> dict[str, Any]:
    reject_symlinks(target)
    reject_symlinks(source)
    root, source = target.resolve(), source.resolve()
    if plan.get("format") != FORMAT or plan.get("target") != str(root) or plan.get("source") != str(source):
        raise MigrationError("计划格式、目标或共享资源与调用参数不一致")
    unsigned = {key: value for key, value in plan.items() if key != "plan_sha256"}
    if digest(canonical(unsigned)) != plan.get("plan_sha256"):
        raise MigrationError("计划内容哈希不一致；请重新生成计划")
    if plan.get("status") != "planned" or plan.get("conflicts"):
        raise MigrationError("不能应用受阻计划；先处理冲突并重新预览")
    lock = safe_path(root, LOCK)
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise MigrationError("另一个文档写入操作持有 docs/.docctl.lock；遗留锁须人工确认后清理") from exc
    backups = {}
    written = []
    made_dirs = []
    try:
        if snapshot(root) != plan.get("inventory") or resource_hashes(source) != plan.get("resources"):
            raise MigrationError("仓库文档、配置或共享资源已改变；拒绝应用陈旧计划")
        # Reconstruct the deterministic plan to reject edited actions, even with a recomputed hash.
        fresh = plan_migration(root, source, plan["mapping"])
        if canonical(fresh) != canonical(plan):
            raise MigrationError("计划与当前输入重建结果不一致；请重新生成并审阅")
        for action in fresh["actions"]:
            path = safe_path(root, action["path"])
            original = path.read_bytes() if path.is_file() else None
            if (digest(original) if original is not None else None) != action["before_sha256"]:
                raise MigrationError(f"写入前文件并发改变：{action['path']}")
            mode = path.stat().st_mode if original is not None else None
            backups[action["path"]] = (original, mode)
            missing = []
            directory = path.parent
            while not directory.exists():
                missing.append(directory)
                directory = directory.parent
            for directory in reversed(missing):
                directory.mkdir()
                made_dirs.append(directory)
            # Record the action before publication: replace/link/unlink can succeed
            # even if a subsequent flush, callback or injected failure raises.
            written.append(action)
            if action["operation"] == "delete":
                path.unlink()
            else:
                atomic_write(path, action["content"].encode("utf-8"), mode, exclusive=original is None)
        expected = dict(plan["inventory"])
        for action in plan["actions"]:
            if action["operation"] == "delete":
                expected.pop(action["path"], None)
            else:
                expected[action["path"]] = action["content_sha256"]
        if snapshot(root) != expected:
            raise MigrationError("应用过程中仓库文档或配置并发改变")
        return {"status": "applied", "applied": True, "actions": len(written),
                "documents": plan["documents"], "validation": plan["validation"]}
    except BaseException as exc:
        failures = []
        for action in reversed(written):
            try:
                path = safe_path(root, action["path"])
                current_hash = digest(path.read_bytes()) if path.is_file() else None
                if current_hash == action["before_sha256"] and not (path.exists() and not path.is_file()):
                    continue  # Publication failed before changing this action.
                if path.exists() and not path.is_file() or current_hash != action["content_sha256"]:
                    raise MigrationError("已写入文件又被其他执行者更改，不覆盖其修改")
                original, mode = backups[action["path"]]
                if original is None:
                    path.unlink()
                else:
                    atomic_write(path, original, mode)
            except (ValueError, OSError) as rollback_error:
                failures.append(f"{action['path']}: {rollback_error}")
        for directory in reversed(made_dirs):
            try:
                directory.rmdir()
            except OSError:
                pass
        if failures:
            raise MigrationError(f"{exc}；回滚未完成，保留并发修改：" + "；".join(failures)) from exc
        raise
    finally:
        os.close(descriptor)
        lock.unlink(missing_ok=True)


def save_plan(path: Path, target: Path, plan: dict[str, Any]) -> None:
    reject_symlinks(path)
    if path.resolve().is_relative_to(target.resolve()):
        raise MigrationError("完整迁移计划须保存在目标仓库之外")
    with path.open("x", encoding="utf-8") as stream:
        json.dump(plan, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--source", type=Path, default=Path(__file__).resolve().parents[2] / "ai-docs-check/assets/templates")
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--scan", "--inventory", dest="inventory", action="store_true",
                        help="只读盘点（--inventory 为兼容别名）")
    action.add_argument("--dry-run", action="store_true")
    action.add_argument("--apply", action="store_true")
    parser.add_argument("--mapping", type=Path, help="显式 source/type/id/title/slug 映射 JSON")
    parser.add_argument("--plan-file", type=Path, help="仓库外完整 JSON 计划；apply 必须读取同一计划")
    args = parser.parse_args(argv)
    try:
        if args.inventory:
            if args.mapping or args.plan_file:
                raise MigrationError("inventory 仅盘点，不接受 mapping 或 plan-file")
            result = inventory(args.target, args.source)
        elif args.apply:
            if not args.plan_file or args.mapping:
                raise MigrationError("apply 必须指定既有 --plan-file，不能另改 mapping")
            reject_symlinks(args.plan_file)
            if args.plan_file.resolve().is_relative_to(args.target.resolve()):
                raise MigrationError("应用计划必须位于目标仓库之外")
            plan = json.loads(args.plan_file.read_text(encoding="utf-8"))
            result = apply_plan(args.target, args.source, plan)
        else:
            if not args.mapping:
                raise MigrationError("预览需要 --mapping；不进行自动语义分类")
            result = plan_migration(args.target, args.source, json.loads(args.mapping.read_text(encoding="utf-8")))
            if args.plan_file:
                save_plan(args.plan_file, args.target, result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1 if result.get("status") == "blocked" else 0
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False, indent=2), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(cli())
