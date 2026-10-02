#!/usr/bin/env python3
"""Documentation helper. Python >=3.10; standard library only.

Never executes registered commands, calls a network service, approves a document,
or changes source record state. Only `new` and `index` write files.
Front matter and compact `yaml doc-meta` blocks use key: JSON scalar.
"""
from __future__ import annotations

import argparse
from contextvars import ContextVar
from functools import wraps
import hashlib
import importlib.util
import json
import os
import posixpath
import re
import shutil
import sys
import tempfile
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit

_runtime_spec = importlib.util.spec_from_file_location(
    "_ai_docs_runtime", Path(__file__).with_name("ai_docs_runtime.py"))
if _runtime_spec is None or _runtime_spec.loader is None:
    raise ImportError("无法加载 Skill 文档资源定位器 ai_docs_runtime.py")
ai_docs_runtime = importlib.util.module_from_spec(_runtime_spec)
_runtime_spec.loader.exec_module(ai_docs_runtime)
_RESOURCES: ContextVar[Path | None] = ContextVar("ai_docs_resources", default=None)

STATUSES = {"template", "draft", "active", "deprecated", "archived"}
AUTHORITIES = {"normative", "descriptive", "evidence", "procedure"}
TASK_STATES = {"queued", "ready", "doing", "blocked", "done", "deferred", "cancelled"}
TASK_KINDS = {"feature", "bug", "chore", "docs", "research"}
RELEASE_STATES = {"planned", "built", "deployed", "verified", "rolled_back"}
REQUIRED = {"id", "type", "status", "summary", "owner", "applies_to",
            "verified_at", "verification_ref", "authority"}
ID_RE = re.compile(r"^[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)+$")
TYPE_RE = re.compile(r"^[a-z][a-z0-9-]*$")
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
PLACEHOLDER_RE = re.compile(r"\{\{[^{}]+\}\}")
LINK_RE = re.compile(r"!?\[[^\]\n]*\]\(([^)\n]+)\)")
REFERENCE_RE = re.compile(r"^\s{0,3}\[[^\]\n]+\]:\s*(\S+)", re.MULTILINE)
ANCHOR_RE = re.compile(r'<a\s+(?:id|name)=[\"\']([^\"\']+)[\"\']\s*></a>', re.IGNORECASE)
ENTRY_RE = re.compile(r'^<a id="([^"\n]+)"></a>\s*\n## ([A-Z][A-Z0-9]*(?:-[A-Z0-9]+)+) · (.+)\n', re.MULTILINE)
REDIRECT_MARKER = "<!-- doc-redirect -->"


class DocError(ValueError):
    """An actionable configuration or document error."""


def resource_scope(function):
    """Keep explicit resource selection local to a single library/CLI operation."""
    @wraps(function)
    def wrapped(*args, resources: Path | None = None, **kwargs):
        token = _RESOURCES.set(Path(resources) if resources is not None else _RESOURCES.get())
        try:
            return function(*args, **kwargs)
        finally:
            _RESOURCES.reset(token)
    return wrapped


def runtime(root: Path):
    try:
        return ai_docs_runtime.Runtime(root, _RESOURCES.get())
    except ai_docs_runtime.RuntimeError as exc:
        raise DocError(str(exc)) from exc


def template_path(root: Path, relative: str) -> Path:
    try:
        return runtime(root).template(relative)
    except ai_docs_runtime.RuntimeError as exc:
        raise DocError(str(exc)) from exc


def require_project_write_target(root: Path) -> None:
    resources = ai_docs_runtime.resource_root(_RESOURCES.get())
    if root.resolve().is_relative_to(resources):
        raise DocError("拒绝写入共享 Skill 资源目录；请用 --root 指定资源包之外的项目根目录")


def safe_path(root: Path, relative: str) -> Path:
    """Resolve a repository-relative path and reject traversal / symlink escape."""
    if not isinstance(relative, str) or not relative.strip():
        raise DocError("路径必须是非空字符串")
    candidate = Path(relative)
    if candidate.is_absolute():
        raise DocError(f"需要仓库相对路径，不能使用绝对路径：{relative}")
    resolved = (root / candidate).resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise DocError(f"路径越过仓库边界：{relative}")
    return resolved


def load_json(root: Path, relative: str) -> Any:
    try:
        return runtime(root).load(relative)
    except ai_docs_runtime.RuntimeError as exc:
        raise DocError(str(exc)) from exc


def parse_frontmatter(text: str, label: str = "<text>") -> dict[str, Any] | None:
    """Parse only flat key: JSON-scalar YAML, not arbitrary YAML."""
    text = text.lstrip("\ufeff")
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    result: dict[str, Any] = {}
    for number, line in enumerate(lines[1:], start=2):
        if line.strip() == "---":
            return result
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        match = re.fullmatch(r"([a-z][a-z0-9_]*):\s*(.+)", line)
        if not match:
            raise DocError(f"{label}:{number}: 元数据须为 key: JSON标量")
        key, raw = match.groups()
        if key in result:
            raise DocError(f"{label}:{number}: 元数据键重复：{key}")
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise DocError(f"{label}:{number}: 字符串请用双引号，未知用 null：{key}") from exc
        if isinstance(value, (list, dict)):
            raise DocError(f"{label}:{number}: 本套件元数据不使用嵌套或数组：{key}")
        result[key] = value
    raise DocError(f"{label}: front matter 缺少关闭的 ---")


def parse_compact_entries(text: str, label: str = "<text>") -> list[dict[str, Any]]:
    """Read entries with explicit stable anchors and independent flat metadata."""
    if has_redirect_marker(text) or parse_frontmatter(text, label) is not None:
        return []
    # Ignore examples and headings inside fenced body content.
    masked = []
    fence = None
    doc_meta_blocks = 0
    for line in text.splitlines(keepends=True):
        marker = re.match(r"^\s*(`{3,}|~{3,})(.*)", line)
        if marker and fence is None:
            fence = marker.group(1)
            if marker.group(2).strip() == "yaml doc-meta":
                doc_meta_blocks += 1
            masked.append(" " * (len(line) - (1 if line.endswith("\n") else 0)) + ("\n" if line.endswith("\n") else ""))
        elif marker and marker.group(1)[0] == fence[0] and len(marker.group(1)) >= len(fence):
            fence = None
            masked.append(" " * (len(line) - (1 if line.endswith("\n") else 0)) + ("\n" if line.endswith("\n") else ""))
        elif fence is not None:
            masked.append(" " * (len(line) - (1 if line.endswith("\n") else 0)) + ("\n" if line.endswith("\n") else ""))
        else:
            masked.append(line)
    headers = list(ENTRY_RE.finditer("".join(masked)))
    if not headers:
        if doc_meta_blocks:
            raise DocError(f"{label}: doc-meta 必须属于带稳定锚点的 ## ID · 标题 条目")
        return []
    prefix = text[:headers[0].start()]
    if not re.fullmatch(r"\s*# [^\n]+\s*", prefix):
        raise DocError(f"{label}: 紧凑集合只允许一个 # 集合标题，条目前不得有正文或公共元数据")
    entries = []
    for n, match in enumerate(headers):
        end = headers[n + 1].start() if n + 1 < len(headers) else len(text)
        section = text[match.end():end].lstrip("\n")
        meta_match = re.match(r"```yaml doc-meta\s*\n(.*?)\n```(?:\n|$)", section, re.DOTALL)
        if not meta_match:
            raise DocError(f"{label}#{match.group(1)}: 条目标题后需要独立 yaml doc-meta")
        meta = parse_frontmatter("---\n" + meta_match.group(1) + "\n---", f"{label}#{match.group(1)}")
        if meta.get("id") != match.group(2):
            raise DocError(f"{label}#{match.group(1)}: 标题 ID 与元数据 id 不一致")
        if match.group(1) != match.group(2).lower():
            raise DocError(f"{label}: 条目锚点必须为 ID 小写：{match.group(2).lower()}")
        body = section[meta_match.end():].strip() + "\n"
        body_visible = without_code_fences(body)
        if re.search(r"^#{1,2}\s+", body_visible, re.MULTILINE):
            raise DocError(f"{label}#{match.group(1)}: 条目正文从 ### 开始，不按章节计数")
        if re.search(r"^```yaml doc-meta\s*$", body, re.MULTILINE):
            raise DocError(f"{label}#{match.group(1)}: 条目只能有一份 doc-meta")
        entries.append({"meta": meta, "title": match.group(3).strip(),
                        "anchor": match.group(1), "slug": meta.get("slug"), "body": body})
    return entries


def document_entries(text: str, label: str) -> list[dict[str, Any]]:
    meta = parse_frontmatter(text, label)
    if meta is None:
        return parse_compact_entries(text, label)
    title = re.search(r"^#\s+(.+)$", without_code_fences(text), re.MULTILINE)
    stable_anchor = str(meta.get("id", "")).lower()
    return [{"meta": meta, "title": title.group(1).strip() if title else "",
             "anchor": stable_anchor if stable_anchor in ANCHOR_RE.findall(without_code_fences(text)) else None,
             "body": text}]


def is_template(path: Path) -> bool:
    return (any(p.startswith("_template") for p in path.parts)
            or path.name.endswith(".template.md"))


def source_markdown(root: Path) -> list[Path]:
    directory = root / "docs"
    if not directory.is_dir():
        raise DocError(f"没有 docs 目录：{root}")
    result = []
    for path in directory.rglob("*.md"):
        rel = path.relative_to(root)
        if "_generated" in rel.parts:
            continue
        safe_path(root, str(rel))
        if path.is_file():
            result.append(path)
    return sorted(result)


def collect_records(root: Path, include_archive: bool = False) -> list[dict[str, Any]]:
    root = root.resolve()
    records = []
    for path in source_markdown(root):
        rel = path.relative_to(root)
        if is_template(rel):
            continue
        if not include_archive and "archive" in rel.parts:
            continue
        raw = path.read_text(encoding="utf-8")
        for entry in document_entries(raw, rel.as_posix()):
            meta = entry["meta"]
            if meta.get("status") == "template" or (not include_archive and meta.get("status") == "archived"):
                continue
            records.append({**meta, "path": rel.as_posix(), "anchor": entry["anchor"],
                            "title": entry["title"],
                            "source_sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest()})
    return records


def without_code_fences(text: str) -> str:
    output: list[str] = []
    fence_char: str | None = None
    fence_size = 0
    for line in text.splitlines():
        match = re.match(r"^\s*(`{3,}|~{3,})", line)
        if match:
            marker = match.group(1)
            if fence_char is None:
                fence_char, fence_size = marker[0], len(marker)
                continue
            if marker[0] == fence_char and len(marker) >= fence_size:
                fence_char = None
                continue
        if fence_char is None:
            output.append(line)
    return "\n".join(output)


def markdown_targets(text: str):
    """Yield destinations outside fenced examples, including reference links."""
    visible = without_code_fences(text)
    for regex in (LINK_RE, REFERENCE_RE):
        yield from (match.group(1).strip() for match in regex.finditer(visible))


def heading_anchor(title: str) -> str:
    title = re.sub(r"<[^>]+>", "", title).casefold()
    title = re.sub(r"[^\w\-\s]", "", title, flags=re.UNICODE)
    return re.sub(r"\s", "-", title)


def markdown_anchors(text: str) -> set[str]:
    visible = without_code_fences(text)
    anchors = set(ANCHOR_RE.findall(visible))
    counts: dict[str, int] = defaultdict(int)
    for match in re.finditer(r"^#{1,6}\s+(.+?)(?:\s+#+)?$", visible, re.MULTILINE):
        anchor = heading_anchor(match.group(1))
        count = counts[anchor]
        counts[anchor] += 1
        anchors.add(anchor + (f"-{count}" if count else ""))
    return anchors


def entry_point_path(root: Path, path: Path) -> Path:
    """The distributable kit stores entry files with underscores to be inert."""
    if not path.exists() and path.name in ("README.md", "AGENTS.md") and path.parent in (root, root / "docs"):
        candidate = path.with_name("_" + path.name)
        if candidate.is_file():
            return candidate
    return path


def repository_ref_errors(root: Path, reference: str, label: str) -> list[str]:
    parsed = urlsplit(reference)
    if parsed.scheme or parsed.netloc:
        return []
    path = safe_path(root, unquote(parsed.path))
    if not path.is_file():
        return [f"{label}: 引用目标不存在：{reference}"]
    if parsed.fragment and unquote(parsed.fragment) not in markdown_anchors(path.read_text(encoding="utf-8")):
        return [f"{label}: 引用锚点不存在：{reference}"]
    return []


def relative_link_errors(root: Path, path: Path, text: str) -> list[str]:
    """Check repository-relative file links and local explicit/heading anchors."""
    errors = []
    for target in markdown_targets(text):
        # Our templates use normal inline links; optional titles are ignored.
        if target.startswith("<") and ">" in target:
            target = target[1:target.index(">")]
        else:
            target = target.split(' "', 1)[0].split(" '", 1)[0]
        if not target or PLACEHOLDER_RE.search(target):
            continue
        parsed = urlsplit(target)
        if parsed.scheme or parsed.netloc:
            continue
        decoded = unquote(parsed.path)
        if decoded.startswith("/"):
            errors.append(f"{path.relative_to(root)}: 请使用仓库内相对链接：{target}")
            continue
        try:
            relative = (path.parent / decoded).relative_to(root).as_posix() if decoded else path.relative_to(root).as_posix()
            destination = entry_point_path(root, safe_path(root, relative))
            if not destination.exists():
                errors.append(f"{path.relative_to(root)}: 相对链接目标不存在：{target}")
            elif parsed.fragment and destination.is_file() and destination.suffix == ".md":
                if unquote(parsed.fragment) not in markdown_anchors(destination.read_text(encoding="utf-8")):
                    errors.append(f"{path.relative_to(root)}: 链接锚点不存在：{target}")
        except (DocError, ValueError) as exc:
            errors.append(f"{path.relative_to(root)}: {exc}")
    return errors


def date_is_valid(value: Any) -> bool:
    if not isinstance(value, str) or not value:
        return False
    try:
        if len(value) == 10:
            date.fromisoformat(value)
        else:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                return False
        return True
    except ValueError:
        return False


@resource_scope
def registry(root: Path, *, resources: Path | None = None) -> dict[str, Any]:
    data = load_json(root, "docs/_system/collections.json")
    if not isinstance(data, dict) or not isinstance(data.get("collections"), list):
        raise DocError("collections.json 需要 collections 数组")
    if data.get("schema_version") not in (1, 2):
        raise DocError("collections.json schema_version 必须为 1 或 2；新写入要求 2")
    if not isinstance(data.get("page_size"), int) or not 1 <= data["page_size"] <= 100:
        raise DocError("page_size 必须为 1 到 100 的整数")
    if data["schema_version"] == 2:
        defaults = data.get("defaults", {})
        if defaults.get("compact_max_items") != 2:
            raise DocError("本协议 compact_max_items 必须为 2；不得通过调高阈值绕过门禁")
        for field in ("create_empty_business_documents", "create_empty_collection_directories", "auto_collapse"):
            if defaults.get(field) is not False:
                raise DocError(f"本协议 defaults.{field} 必须为 false")
    return data


def collection_state(root: Path, item: dict[str, Any]) -> dict[str, Any]:
    root = root.resolve()
    base = item.get("base_path", item.get("directory"))
    expanded = safe_path(root, base)
    compact = safe_path(root, base + ".md")
    entries = []
    if compact.is_file():
        entries = parse_compact_entries(compact.read_text(encoding="utf-8"), compact.relative_to(root).as_posix())
    expanded_count = 0
    if expanded.is_dir():
        for path in expanded.glob("*.md"):
            if not is_template(path.relative_to(root)):
                expanded_count += len(document_entries(path.read_text(encoding="utf-8"), path.relative_to(root).as_posix()))
    layout = "expanded" if expanded.is_dir() else "compact" if entries else "absent"
    return {"collection": item["key"], "layout": layout,
            "count": expanded_count if layout == "expanded" else len(entries),
            "path": base if layout == "expanded" else base + ".md" if entries else None,
            "planned_path": base + ".md"}


def resolve_reference(root: Path, ref: Any, choices: dict[str, Any], *, writing: bool = False) -> tuple[str | None, dict[str, Any] | None]:
    if isinstance(ref, str):
        context = runtime(root)
        try:
            path = entry_point_path(root, context.write_reference(ref) if writing else context.reference(ref))
        except ai_docs_runtime.RuntimeError as exc:
            raise DocError(str(exc)) from exc
        if not path.is_relative_to(root.resolve()):
            return path.as_posix(), {"resource_path": ref, "provider": "skill"}
        return path.relative_to(root).as_posix(), None
    if isinstance(ref, dict) and set(ref) == {"collection"}:
        key = ref["collection"]
        if key not in choices:
            raise DocError(f"路由引用未知集合：{key}")
        state = collection_state(root, choices[key])
        return state["path"], state
    if isinstance(ref, dict) and set(ref) == {"optional_path"}:
        path = ref["optional_path"]
        exists = safe_path(root, path).exists()
        return path if exists else None, {"optional_path": path, "exists": exists}
    raise DocError(f"非法路由引用：{ref}")


def has_redirect_marker(text: str) -> bool:
    return REDIRECT_MARKER in (line.strip() for line in without_code_fences(text).splitlines())


def thin_redirect(text: str) -> bool:
    if not has_redirect_marker(text) or parse_frontmatter(text) is not None or "```yaml doc-meta" in text:
        return False
    explanation = []
    links = 0
    for line in text.splitlines():
        line = line.strip()
        if not line or line == REDIRECT_MARKER or line.startswith("#"):
            continue
        if ANCHOR_RE.fullmatch(line):
            continue
        if not LINK_RE.search(line):
            explanation.append(line)
            continue
        residue = LINK_RE.sub("", line).strip(" -·|>*")
        if residue:
            return False
        links += 1
    return bool(links) and len(explanation) <= 3 and sum(map(len, explanation)) <= 300 and all(
        re.search(r"迁移|展开|跳转|新位置|新路径|旧入口", line) for line in explanation)


def collection_errors(root: Path, item: dict[str, Any]) -> list[str]:
    errors = []
    base = item["base_path"]
    compact = safe_path(root, base + ".md")
    expanded = safe_path(root, base)
    entries = []
    if compact.exists():
        if not compact.is_file():
            errors.append(f"{base}.md: 紧凑集合必须为文件")
        else:
            text = compact.read_text(encoding="utf-8")
            try:
                entries = parse_compact_entries(text, base + ".md")
                if has_redirect_marker(text):
                    if not expanded.is_dir() or not thin_redirect(text):
                        errors.append(f"{base}.md: doc-redirect 必须为展开后的薄跳转页，不得保留正文")
                elif not entries:
                    errors.append(f"{base}.md: 空业务壳文件或缺少逐条 doc-meta")
            except DocError as exc:
                errors.append(str(exc))
            if len(entries) > 2:
                errors.append(f"{base}.md: 紧凑集合有 {len(entries)} 条，超过 2 条必须展开")
            for entry in entries:
                meta = entry["meta"]
                if meta.get("type") != item["key"]:
                    errors.append(f"{base}.md#{entry['anchor']}: type 与登记集合不一致")
                if not isinstance(meta.get("slug"), str) or not SLUG_RE.fullmatch(meta["slug"]):
                    errors.append(f"{base}.md#{entry['anchor']}: 需要有效 slug 以保留迁移文件名")
    if expanded.exists() and not expanded.is_dir():
        errors.append(f"{base}: 已展开集合必须为目录")
    if expanded.is_dir():
        if entries:
            errors.append(f"{base}: 聚合文件与集合目录同时存在，不能保留双正文源")
        for path in expanded.rglob("*.md"):
            try:
                raw = path.read_text(encoding="utf-8")
                records = document_entries(raw, path.relative_to(root).as_posix())
            except DocError:
                continue
            if records and (parse_frontmatter(raw) is None or len(records) != 1):
                errors.append(f"{path.relative_to(root)}: 已展开文件须有一份 front matter，不能再存紧凑集合")
            for entry in records:
                meta = entry["meta"]
                if meta.get("status") == "template":
                    errors.append(f"{path.relative_to(root)}: 业务集合不得预放模板")
                if meta.get("type") != item["key"]:
                    errors.append(f"{path.relative_to(root)}: type 与登记集合不一致")
                if path.parent != expanded or path.name == "index.md":
                    errors.append(f"{path.relative_to(root)}: 独立条目直接放在集合目录，不再为条目建子目录")
                slug = meta.get("slug")
                if not isinstance(slug, str) or not SLUG_RE.fullmatch(slug):
                    errors.append(f"{path.relative_to(root)}: 独立条目需要有效 slug")
                elif path.name != f"{meta.get('id')}-{slug}.md":
                    errors.append(f"{path.relative_to(root)}: 文件名与 ID/slug 不一致")
    return errors


def empty_business_errors(root: Path) -> list[str]:
    errors = []
    for directory in (root / "docs").rglob("*"):
        rel = directory.relative_to(root)
        if any(part.startswith("_") for part in rel.parts):
            continue
        if directory.is_dir() and not any(p.is_file() for p in directory.rglob("*")):
            errors.append(f"{rel}: 空业务壳目录，不应为未发生内容预建目录")
        elif directory.is_file() and directory.suffix == ".md":
            text = directory.read_text(encoding="utf-8")
            if has_redirect_marker(text):
                continue
            # Detect physically empty shells, while leaving adequacy of content to review.
            plain = re.sub(r"<!--.*?-->", "", without_code_fences(strip_frontmatter(text)), flags=re.DOTALL)
            plain = ANCHOR_RE.sub("", plain)
            lines = [line.strip() for line in plain.splitlines() if line.strip()
                     and not line.lstrip().startswith("#")]
            if not lines or all(PLACEHOLDER_RE.fullmatch(line) for line in lines):
                errors.append(f"{rel}: 空业务壳文件，不应创建只有标题或占位符的文档")
    return errors


@resource_scope
def validate(root: Path, strict: bool = False, *, resources: Path | None = None) -> dict[str, Any]:
    root = root.resolve()
    errors: list[str] = []
    warnings: list[str] = []
    ids: dict[str, str] = {}
    record_metas: dict[str, dict[str, Any]] = {}
    paths = source_markdown(root)
    for generated_path in (root / "docs" / "_generated").rglob("*.md"):
        safe_path(root, generated_path.relative_to(root).as_posix())
        paths.append(generated_path)
    for rootfile in ("README.md", "AGENTS.md"):
        path = root / rootfile
        if not path.is_file() and (root / ("_" + rootfile)).is_file():
            path = root / ("_" + rootfile)
        if not path.is_file():
            errors.append(f"缺少入口：{rootfile}")
        else:
            paths.append(path)
    for path in sorted(paths):
        rel = path.relative_to(root).as_posix()
        text = path.read_text(encoding="utf-8")
        errors.extend(relative_link_errors(root, path, text))
        if is_template(Path(rel)) and path.name == "SKILL.md":
            # Agent Skills front matter follows its own YAML specification.
            continue
        try:
            entries = document_entries(text, rel)
        except DocError as exc:
            errors.append(str(exc))
            continue
        for entry in entries:
            meta = entry["meta"]
            label = rel + ("#" + entry["anchor"] if entry["anchor"] else "")
            missing = REQUIRED - meta.keys()
            if missing:
                errors.append(f"{label}: 缺少元数据 {', '.join(sorted(missing))}")
            if meta.get("status") not in STATUSES:
                errors.append(f"{label}: 非法 status")
            if meta.get("authority") not in AUTHORITIES:
                errors.append(f"{label}: 非法 authority")
            typ = meta.get("type")
            if not isinstance(typ, str) or not TYPE_RE.fullmatch(typ):
                errors.append(f"{label}: 非法 type")
            if meta.get("status") == "template" or is_template(Path(rel)):
                if meta.get("status") != "template":
                    errors.append(f"{label}: 模板文件的 status 必须为 template")
                continue
            doc_id = meta.get("id")
            if not isinstance(doc_id, str) or not ID_RE.fullmatch(doc_id):
                errors.append(f"{label}: 非法或未填写 id")
            elif doc_id in ids:
                errors.append(f"重复 ID {doc_id}: {ids[doc_id]} 与 {label}")
            else:
                ids[doc_id] = label
            record_metas[label] = meta
            verified = meta.get("verified_at")
            reference = meta.get("verification_ref")
            if bool(verified) != bool(reference):
                errors.append(f"{label}: verified_at 与 verification_ref 必须同时填写或同时为空")
            if verified is not None and not date_is_valid(verified):
                errors.append(f"{label}: verified_at 须为 ISO 日期或带时区的时间")
            if typ == "task":
                if meta.get("state") not in TASK_STATES:
                    errors.append(f"{label}: 非法任务 state")
                if meta.get("kind") not in TASK_KINDS:
                    errors.append(f"{label}: 非法任务 kind")
                if meta.get("handover_ref"):
                    try:
                        handover = urlsplit(meta["handover_ref"])
                        if handover.scheme or handover.netloc:
                            errors.append(f"{label}: handover_ref 须为仓库内路径与可选条目锚点")
                        else:
                            errors.extend(repository_ref_errors(root, meta["handover_ref"], label + ": handover_ref"))
                    except DocError as exc:
                        errors.append(f"{label}: {exc}")
            for field, value in meta.items():
                if field != "handover_ref" and field.endswith("_ref") and isinstance(value, str) and value.startswith("docs/"):
                    try:
                        errors.extend(repository_ref_errors(root, value, label + ": " + field))
                    except DocError as exc:
                        errors.append(f"{label}: {exc}")
            if typ == "release" and meta.get("release_state") not in RELEASE_STATES:
                errors.append(f"{label}: 非法 release_state")
            if meta.get("status") == "active":
                if PLACEHOLDER_RE.search(entry["body"] + json.dumps(meta, ensure_ascii=False)):
                    errors.append(f"{label}: active 文档仍包含未填写占位符")
                if not meta.get("owner"):
                    (errors if strict else warnings).append(f"{label}: active 文档缺少 owner")
                if not verified:
                    (errors if strict else warnings).append(f"{label}: active 文档缺少核验记录")
                if meta.get("authority") in ("normative", "procedure"):
                    if not meta.get("approved_by") or not meta.get("approval_ref"):
                        errors.append(f"{label}: 生效规范/程序缺少批准依据")
    try:
        context = runtime(root)
        if context.lightweight:
            for entry in ("docs/AGENTS.md", "docs/README.md"):
                if not safe_path(root, entry).is_file():
                    errors.append(f"缺少入口：{entry}")
        reg = registry(root)
        seen_keys: set[str] = set()
        seen_bases: set[str] = set()
        choices = {item["key"]: item for item in reg["collections"]}
        for item in reg["collections"]:
            key = item.get("key")
            if not isinstance(key, str) or not TYPE_RE.fullmatch(key) or key in seen_keys:
                errors.append(f"collections.json: 非法或重复类型键 {key}")
                continue
            seen_keys.add(key)
            for field in (("directory", "template") if reg["schema_version"] == 1 else ("template",)):
                dest = template_path(root, item.get(field, "")) if field == "template" else safe_path(root, item.get(field, ""))
                if not dest.exists():
                    errors.append(f"collections.json: {key}.{field} 不存在")
            if reg["schema_version"] == 2:
                base = item.get("base_path", "")
                safe_path(root, base)
                if base in seen_bases or Path(base).suffix or not base.startswith("docs/") or any(part.startswith("_") for part in Path(base).parts):
                    errors.append(f"collections.json: 非法或重复 base_path {base}")
                seen_bases.add(base)
                if item.get("template") != f"docs/_templates/{key}.md":
                    errors.append(f"collections.json: {key}.template 必须为集中模板路径 docs/_templates/{key}.md")
                errors.extend(collection_errors(root, item))
        if reg["schema_version"] == 2:
            for label, meta in record_metas.items():
                typ = meta.get("type")
                if typ in choices:
                    base = choices[typ]["base_path"]
                    path = label.split("#", 1)[0]
                    if path != base + ".md" and posixpath.dirname(path) != base:
                        errors.append(f"{label}: 登记类别 {typ} 的条目必须放在 {base}.md 或 {base}/")
        routes = load_json(root, "docs/_system/routes.json")["routes"]
        seen_routes: set[str] = set()
        for item in routes:
            if item["id"] in seen_routes:
                errors.append(f"重复路由 ID: {item['id']}")
            seen_routes.add(item["id"])
            refs = [(ref, False) for ref in item["must_read"]] + [(ref, True) for ref in item["write_back"]]
            for rule in item.get("read_when", []):
                refs.extend((ref, False) for ref in rule["paths"])
            for ref, writing in refs:
                resolved, _ = resolve_reference(root, ref, choices, writing=writing)
                if resolved is not None and not (Path(resolved) if Path(resolved).is_absolute() else safe_path(root, resolved)).exists():
                    errors.append(f"路由 {item['id']}: 路径不存在 {resolved}")
        if reg["schema_version"] == 2:
            errors.extend(empty_business_errors(root))
        project = load_json(root, "docs/_system/project-map.json")
        command_data = load_json(root, "docs/_system/commands.json")
        locations: dict[str, Any] = {}
        for item in project["locations"]:
            key = item["id"]
            if key in locations:
                errors.append(f"重复 location ID: {key}")
            locations[key] = item
            if item.get("enabled") is not None and not isinstance(item.get("enabled"), bool):
                errors.append(f"{key}: enabled 必须是 true / false / null")
            if not isinstance(item.get("paths"), list):
                errors.append(f"{key}: paths 必须是数组")
                continue
            if item.get("repository") == ".":
                for p in item["paths"]:
                    if not safe_path(root, p).exists():
                        errors.append(f"location {key}: 实际路径不存在 {p}")
            if item.get("enabled") is False and not item.get("not_applicable_reason"):
                (errors if strict else warnings).append(f"location {key}: 禁用但缺少不适用原因")
        commands: dict[str, Any] = {}
        for item in command_data["commands"]:
            key = item["id"]
            if key in commands:
                errors.append(f"重复 command ID: {key}")
            commands[key] = item
            argv = item.get("argv")
            if argv is not None and (not isinstance(argv, list) or not argv
                    or any(not isinstance(a, str) or not a for a in argv)):
                errors.append(f"command {key}: argv 必须为非空字符串数组或 null")
            cwd = item.get("cwd")
            if cwd is not None and not safe_path(root, cwd).is_dir():
                errors.append(f"command {key}: cwd 不存在")
            if item.get("timeout_seconds") is not None and (
                    not isinstance(item["timeout_seconds"], int) or item["timeout_seconds"] <= 0):
                errors.append(f"command {key}: timeout_seconds 必须为正整数或 null")
        if project.get("project", {}).get("operating_mode") not in ("bootstrap", "maintenance"):
            errors.append("operating_mode 必须是 bootstrap 或 maintenance")
        if project.get("work_tracking", {}).get("mode") not in ("repository", "external"):
            errors.append("work_tracking.mode 必须是 repository 或 external")
        if project.get("work_tracking", {}).get("mode") != "repository":
            warnings.append("外部任务系统模式：本工具不连接或同步该系统；不得再把仓库任务作为第二状态源。")
        if strict:
            readiness = project["readiness"]
            if project["project"].get("operating_mode") == "bootstrap":
                errors.append("项目仍处于 bootstrap，尚未声明文档就绪")
            if (not project["project"].get("name") or not project["project"].get("owner")
                    or PLACEHOLDER_RE.search(json.dumps(project["project"], ensure_ascii=False))):
                errors.append("项目名称或负责人未填写")
            for ref in readiness["required_documents"]:
                path_ref, _ = resolve_reference(root, ref, choices)
                if path_ref is None:
                    errors.append(f"必需文档不存在：{ref}")
                    continue
                p = safe_path(root, path_ref)
                if not p.is_file():
                    errors.append(f"必需文档不存在：{ref}")
                    continue
                content = p.read_text(encoding="utf-8")
                if PLACEHOLDER_RE.search(content):
                    errors.append(f"必需文档未填写：{ref}")
                relevant = [m for label, m in record_metas.items() if label == path_ref or label.startswith(path_ref + "#")]
                if any(m.get("status") != "active" for m in relevant):
                    errors.append(f"必需文档不是 active：{ref}")
            for key in readiness["required_locations"]:
                item = locations.get(key)
                if not item or item.get("enabled") is not True or not (
                        item.get("paths") or item.get("external_ref")):
                    errors.append(f"必需 location 未就绪：{key}")
                elif (not item.get("verified_at") or not item.get("verification_ref")
                      or PLACEHOLDER_RE.search(json.dumps(item, ensure_ascii=False))):
                    errors.append(f"必需 location 缺少核验或仍有占位符：{key}")
            for key in readiness["required_commands"]:
                item = commands.get(key)
                if not item or not item.get("argv") or item.get("cwd") is None:
                    errors.append(f"必需命令未配置：{key}")
                elif (not all(item.get(k) for k in ("environment", "timeout_seconds", "verified_at", "verification_ref"))
                      or PLACEHOLDER_RE.search(json.dumps(item, ensure_ascii=False))):
                    errors.append(f"必需命令缺少环境、超时或核验：{key}")
    except (DocError, KeyError, TypeError, ValueError) as exc:
        errors.append(f"配置结构错误：{exc}")
    return {"ok": not errors, "mode": "strict" if strict else "structure",
            "markdown_files_checked": len(paths), "records": len(record_metas),
            "errors": errors, "warnings": warnings,
            "limits": "不执行项目命令，不联网；检查本协议平面元数据及普通 Markdown 本地引用，不证明条目语义边界、批准真实性或外部权限。"}


@resource_scope
def make_new(root: Path, key: str, doc_id: str, slug: str, title: str,
             kind: str | None = None, *, resources: Path | None = None) -> Path:
    """Serialize lookup, counting, creation, migration and generated-index updates."""
    root = root.resolve()
    require_project_write_target(root)
    context = runtime(root)
    lock = safe_path(root, "docs/.docctl.lock" if context.lightweight else "docs/_system/.docctl-new.lock")
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise DocError("另一个 new 操作持有写入锁，请完成后重试；中断遗留的锁须人工确认后移除") from exc
    try:
        return _make_new(root, key, doc_id, slug, title, kind)
    finally:
        os.close(descriptor)
        lock.unlink(missing_ok=True)


def _make_new(root: Path, key: str, doc_id: str, slug: str, title: str,
              kind: str | None = None) -> Path:
    root = root.resolve()
    reg = registry(root)
    if reg["schema_version"] != 2:
        raise DocError("new 要求 collections.json schema_version 2；先迁移配置和参考模板，不能按旧布局写入")
    choices = {c["key"]: c for c in reg["collections"]}
    if key not in choices:
        raise DocError(f"未知模板类型 {key}; 可用类型：{', '.join(sorted(choices))}")
    item = choices[key]
    if not ID_RE.fullmatch(doc_id) or not doc_id.startswith(item["prefix"] + "-"):
        raise DocError(f"ID 必须为 {item['prefix']}- 开头的大写字母/数字/短横线标识")
    if not SLUG_RE.fullmatch(slug):
        raise DocError("slug 只允许小写英文字母、数字和分隔短横线，不允许路径")
    if not title.strip() or "\n" in title or "\r" in title:
        raise DocError("标题必须为非空单行文字")
    if key == "task" and load_json(root, "docs/_system/project-map.json").get("work_tracking", {}).get("mode") != "repository":
        raise DocError("任务状态已配置为外部系统；拒绝创建第二套本地任务状态")
    if kind is not None and (key != "task" or kind not in TASK_KINDS):
        raise DocError("--kind 只用于 task，且必须是允许的任务类别")
    records = collect_records(root, include_archive=True)
    for record in records:
        if record.get("id") == doc_id:
            raise DocError(f"ID 已存在：{doc_id}；请更新原条目 {record['path']}，不新增或覆盖")
        if record.get("type") == key and (record.get("slug") == slug or normalize_title(record.get("title", "")) == normalize_title(title)):
            raise DocError(f"同主题条目已存在：{record.get('id')}；请先核对并更新原条目 {record['path']}")
    structural = collection_errors(root, item)
    if structural:
        raise DocError("无法新增到结构异常的集合：" + "；".join(structural))
    source = template_path(root, item["template"]).read_text(encoding="utf-8")
    template_meta = parse_frontmatter(source, item["template"])
    if not template_meta or template_meta.get("type") != key or template_meta.get("status") != "template":
        raise DocError("所选模板的 type/status 与集合登记不一致")
    text = source.replace('id: "{{ID}}"', 'id: ' + json.dumps(doc_id), 1)
    text = text.replace('status: "template"', 'status: "draft"', 1)
    text = text.replace("# {{TITLE}}", "# " + title.strip(), 1)
    text = text.replace("> 模板用途：", "> 记录用途：", 1)
    text = text.replace("复制成新条目后填写；本模板不代表项目已实现或已批准任何内容。",
                        "创建时为草稿；有效性以适用范围、状态、核验和批准依据为准。", 1)
    if kind is not None:
        text = text.replace('kind: "feature"', 'kind: ' + json.dumps(kind), 1)
    meta = parse_frontmatter(text, item["template"])
    meta["slug"] = slug
    body = strip_frontmatter(text)
    body = re.sub(r"^# [^\n]+\n?", "", body, count=1).lstrip("\n")
    body = re.sub(r"^> 集中参考源；[^\n]*\n?", "", body, count=1).lstrip("\n")
    # Collection title and record title are independent; body headings start at ###.
    body = shift_headings(body, 1)
    entry = {"meta": meta, "title": title.strip(), "anchor": doc_id.lower(), "slug": slug, "body": body}
    base = item["base_path"]
    compact = safe_path(root, base + ".md")
    expanded = safe_path(root, base)
    state = collection_state(root, item)
    migrated = False
    if state["layout"] == "expanded":
        target = safe_path(root, f"{base}/{doc_id}-{slug}.md")
        write_exclusive(target, expanded_text(entry))
    else:
        entries = parse_compact_entries(compact.read_text(encoding="utf-8"), base + ".md") if compact.exists() else []
        if len(entries) < 2:
            target = compact
            compact_text = compact.read_text(encoding="utf-8") if compact.exists() else "# " + item.get("title", key) + "\n"
            compact_text = compact_text.rstrip() + "\n\n" + compact_entry_text(entry)
            if compact.exists():
                atomic_text_write(compact, compact_text)
            else:
                write_exclusive(compact, compact_text)
        else:
            target = expand_collection(root, item, entries + [entry])
            migrated = True
    if not migrated and ((root / "docs/_generated/indexes").exists() or (root / "docs/_generated/catalog").exists()):
        generate_indexes(root)
    return target


def normalize_title(title: str) -> str:
    return re.sub(r"\s+", " ", title).strip().casefold()


def strip_frontmatter(text: str) -> str:
    if parse_frontmatter(text) is None:
        return text
    return re.split(r"^---\s*$", text, maxsplit=2, flags=re.MULTILINE)[2].lstrip("\n")


def shift_headings(text: str, amount: int) -> str:
    lines = []
    fence = None
    for line in text.splitlines():
        marker = re.match(r"^\s*(`{3,}|~{3,})", line)
        if marker:
            if fence is None:
                fence = marker.group(1)
            elif marker.group(1)[0] == fence[0] and len(marker.group(1)) >= len(fence):
                fence = None
        if fence is None and not marker:
            line = re.sub(r"^(#{1,6})(\s+)", lambda m: "#" * max(1, min(6, len(m.group(1)) + amount)) + m.group(2), line)
        lines.append(line)
    return "\n".join(lines).rstrip() + "\n"


def metadata_text(meta: dict[str, Any]) -> str:
    return "\n".join(f"{key}: {json.dumps(value, ensure_ascii=False)}" for key, value in meta.items())


def compact_entry_text(entry: dict[str, Any]) -> str:
    return (f'<a id="{entry["anchor"]}"></a>\n## {entry["meta"]["id"]} · {entry["title"]}\n\n'
            + "```yaml doc-meta\n" + metadata_text(entry["meta"]) + "\n```\n\n" + entry["body"].rstrip() + "\n")


def expanded_text(entry: dict[str, Any]) -> str:
    old_heading_anchor = heading_anchor(entry["meta"]["id"] + " · " + entry["title"])
    return ("---\n" + metadata_text(entry["meta"]) + "\n---\n\n"
            + f'<a id="{entry["anchor"]}"></a>\n<a id="{old_heading_anchor}"></a>\n# {entry["title"]}\n\n'
            + shift_headings(entry["body"], -1))


def atomic_text_write(path: Path, text: str) -> None:
    fd, name = tempfile.mkstemp(prefix=".docctl-", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(text)
        if path.exists():
            temporary.chmod(path.stat().st_mode)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def write_exclusive(path: Path, text: str) -> None:
    missing_dirs = []
    directory = path.parent
    while not directory.exists():
        missing_dirs.append(directory)
        directory = directory.parent
    path.parent.mkdir(parents=True, exist_ok=True)
    created_file = False
    try:
        with path.open("x", encoding="utf-8") as stream:
            created_file = True
            stream.write(text)
    except FileExistsError as exc:
        raise DocError(f"文件已存在，拒绝覆盖：{path}") from exc
    except BaseException:
        if created_file:
            path.unlink(missing_ok=True)
        for directory in missing_dirs:
            try:
                directory.rmdir()
            except OSError:
                pass
        raise


def rewrite_local_links(root: Path, text: str, old_source: Path, new_source: Path,
                        compact: Path, anchors: dict[str, Path], expanded: Path) -> str:
    """Move relative outgoing links and repair incoming links to the old aggregate."""
    def rewrite(target: str) -> str:
        raw = target.strip()
        if raw.startswith("<") and ">" in raw:
            close = raw.index(">")
            destination, suffix, wrapped = raw[1:close], raw[close + 1:], True
        else:
            found = re.match(r"(\S+)(.*)", raw)
            if not found:
                return target
            destination, suffix, wrapped = found.group(1), found.group(2), False
        parsed = urlsplit(destination)
        if parsed.scheme or parsed.netloc or parsed.path.startswith("/") or PLACEHOLDER_RE.search(destination):
            return target
        resolved = (old_source.parent / unquote(parsed.path)).resolve() if parsed.path else old_source
        if not resolved.is_relative_to(root.resolve()):
            raise DocError(f"迁移时链接越过仓库边界：{destination}")
        if resolved == compact:
            if parsed.fragment:
                anchor = unquote(parsed.fragment)
                if anchor not in anchors:
                    raise DocError(f"旧集合锚点无法迁移：{destination}；请使用条目的稳定 ID 锚点")
                resolved = anchors[anchor]
            else:
                resolved = expanded
        relative = "" if resolved == new_source and parsed.fragment else posixpath.relpath(resolved.as_posix(), new_source.parent.as_posix())
        rewritten = relative + ("?" + parsed.query if parsed.query else "") + ("#" + parsed.fragment if parsed.fragment else "")
        return ("<" + rewritten + ">" if wrapped else rewritten) + suffix
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
            for regex in (LINK_RE, REFERENCE_RE):
                line = regex.sub(lambda m: m.group(0)[:m.start(1) - m.start()] + rewrite(m.group(1)) + m.group(0)[m.end(1) - m.start():], line)
        lines.append(line)
    rewritten = "".join(lines)
    # Flat metadata references are repository-relative, not relative to the document.
    # Only exact local paths to the moved aggregate are changed; record IDs and
    # external approval/evidence strings remain untouched.
    def rewrite_metadata(match):
        key, raw = match.group(1), match.group(2)
        if not key.endswith("_ref"):
            return match.group(0)
        try:
            value = json.loads(raw)
        except json.JSONDecodeError:
            return match.group(0)
        if not isinstance(value, str) or not value.startswith("docs/"):
            return match.group(0)
        parsed = urlsplit(value)
        if parsed.scheme or parsed.netloc or safe_path(root, unquote(parsed.path)) != compact:
            return match.group(0)
        if parsed.fragment:
            if unquote(parsed.fragment) not in anchors:
                raise DocError(f"旧集合元数据锚点无法迁移：{value}")
            destination = anchors[unquote(parsed.fragment)]
        else:
            if key == "handover_ref" and len(set(anchors.values())) > 1:
                raise DocError(f"交接引用无法唯一定位：{value}；迁移前请补稳定条目锚点")
            destination = expanded
        value = destination.relative_to(root).as_posix() + ("?" + parsed.query if parsed.query else "") + ("#" + parsed.fragment if parsed.fragment else "")
        return key + ": " + json.dumps(value, ensure_ascii=False)
    output = []
    frontmatter = rewritten.lstrip("\ufeff").startswith("---\n")
    delimiter_count = 0
    fence = None
    metadata_fence = False
    for line in rewritten.splitlines(keepends=True):
        if frontmatter and line.strip() == "---":
            delimiter_count += 1
            if delimiter_count == 2:
                frontmatter = False
            output.append(line)
            continue
        marker = re.match(r"^\s*(`{3,}|~{3,})(.*)", line)
        if marker:
            if fence is None:
                fence = marker.group(1)
                metadata_fence = marker.group(2).strip() == "yaml doc-meta"
            elif marker.group(1)[0] == fence[0] and len(marker.group(1)) >= len(fence):
                fence = None
                metadata_fence = False
            output.append(line)
            continue
        if frontmatter or metadata_fence:
            line = re.sub(r"^([a-z][a-z0-9_]*):\s*(.+)$", rewrite_metadata, line)
        output.append(line)
    return "".join(output)


def expand_collection(root: Path, item: dict[str, Any], entries: list[dict[str, Any]]) -> Path:
    compact = safe_path(root, item["base_path"] + ".md")
    expanded = safe_path(root, item["base_path"])
    targets = [safe_path(root, f"{item['base_path']}/{e['meta']['id']}-{e['slug']}.md") for e in entries]
    if any(p.exists() for p in targets) or expanded.exists():
        raise DocError("展开目标已存在；拒绝覆盖或留下双正文源")
    anchors = {e["anchor"]: p for e, p in zip(entries, targets)}
    # Preserve historical generated heading anchors as well as stable ID anchors.
    for entry, target in zip(entries, targets):
        anchors[heading_anchor(entry["meta"]["id"] + " · " + entry["title"])] = target
    writes = {target: rewrite_local_links(root, expanded_text(entry), compact, target, compact, anchors, expanded)
              for entry, target in zip(entries, targets)}
    old = {}
    skip = {".git", "node_modules", ".venv", "venv", "__pycache__", ".cache", ".next", "dist", "build"}
    paths = [p for p in root.rglob("*.md") if p.is_file()
             and not any(part in skip for part in p.relative_to(root).parts)]
    for path in sorted(set(paths)):
        safe_path(root, path.relative_to(root).as_posix())
        if path == compact:
            continue
        original = path.read_text(encoding="utf-8")
        rewritten = rewrite_local_links(root, original, path, path, compact, anchors, expanded)
        if original != rewritten:
            old[path] = original
            writes[path] = rewritten
    original_compact = compact.read_text(encoding="utf-8")
    created = []
    generated = safe_path(root, "docs/_generated")
    refresh_indexes = (generated / "indexes").exists() or (generated / "catalog").exists()
    backup = tempfile.TemporaryDirectory(prefix="docctl-migration-") if refresh_indexes else None
    old_views = {}
    if backup:
        for name in ("indexes", "catalog"):
            destination = generated / name
            safe_path(root, destination.relative_to(root).as_posix())
            if destination.is_symlink() or (destination.exists() and not destination.is_dir()):
                backup.cleanup()
                raise DocError(f"拒绝替换非法生成视图：{destination.relative_to(root)}")
            old_views[name] = destination.exists()
            if destination.exists():
                shutil.copytree(destination, Path(backup.name) / name)
    try:
        for path, content in writes.items():
            if path in targets:
                write_exclusive(path, content)
                created.append(path)
            else:
                atomic_text_write(path, content)
        compact.unlink()
        if refresh_indexes:
            generate_indexes(root)
    except Exception:
        for path, original in old.items():
            atomic_text_write(path, original)
        for path in created:
            path.unlink(missing_ok=True)
        if expanded.is_dir() and not any(expanded.iterdir()):
            expanded.rmdir()
        if not compact.exists():
            write_exclusive(compact, original_compact)
        if backup:
            for name, existed in old_views.items():
                destination = generated / name
                if destination.exists():
                    shutil.rmtree(destination)
                if existed:
                    shutil.copytree(Path(backup.name) / name, destination)
        raise
    finally:
        if backup:
            backup.cleanup()
    return targets[-1]


@resource_scope
def find_records(root: Path, typ: str | None = None, status: str | None = None,
                 state: str | None = None, kind: str | None = None,
                 query: str | None = None, limit: int = 20,
                 include_archive: bool = False, *, resources: Path | None = None) -> dict[str, Any]:
    runtime(root)  # Enforce the project version even though finding needs no templates.
    if limit < 1 or limit > 1000:
        raise DocError("limit 必须在 1 到 1000 之间")
    matches = []
    for record in collect_records(root, include_archive):
        if typ and record.get("type") != typ:
            continue
        if status and record.get("status") != status:
            continue
        if state and record.get("state") != state:
            continue
        if kind and record.get("kind") != kind:
            continue
        haystack = " ".join(str(record.get(k, "")) for k in ("id", "title", "summary", "path", "applies_to"))
        if query and query.casefold() not in haystack.casefold():
            continue
        matches.append(record)
    matches.sort(key=lambda r: (r.get("type", ""), r.get("id", "")))
    return {"total_matches": len(matches), "returned": min(len(matches), limit),
            "records": matches[:limit],
            "note": "模板和生成物不作为实例；默认不含归档。结果状态不等于功能已实现或已发布。"}


def table_text(value: Any) -> str:
    return str(value if value is not None else "—").replace("|", "\\|").replace("\n", " ")


@resource_scope
def generate_indexes(root: Path, *, resources: Path | None = None) -> dict[str, Any]:
    root = root.resolve()
    require_project_write_target(root)
    reg = registry(root)
    page_size = reg["page_size"]
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    records = collect_records(root, include_archive=True)
    for record in records:
        typ = record.get("type", "")
        if not TYPE_RE.fullmatch(typ):
            raise DocError(f"索引类型不合法：{typ}")
        grouped[typ].append(record)
    generated = safe_path(root, "docs/_generated")
    generated.mkdir(parents=True, exist_ok=True)
    for name in ("indexes", "catalog"):
        if (generated / name).is_symlink():
            raise DocError(f"拒绝替换符号链接输出目录：{name}")
    page_count = 0
    temp = Path(tempfile.mkdtemp(prefix=".docctl-", dir=generated))
    try:
        for name in ("indexes", "catalog"):
            (temp / name).mkdir()
        top_rows = []
        for typ in sorted(grouped):
            group = sorted(grouped[typ], key=lambda r: (r.get("id", ""), r["path"]))
            chunks = [group[i:i + page_size] for i in range(0, len(group), page_size)]
            top_rows.append(f"| `{typ}` | {len(group)} | [第一页]({typ}/page-001.md) |")
            for n, chunk in enumerate(chunks, start=1):
                page_count += 1
                file = f"page-{n:03d}"
                (temp / "indexes" / typ).mkdir(exist_ok=True)
                (temp / "catalog" / typ).mkdir(exist_ok=True)
                rel_doc = f"docs/_generated/indexes/{typ}/{file}.md"
                lines = [f"# {typ} · 第 {n}/{len(chunks)} 页", "",
                         "生成视图，只读。事实、状态、批准与验证依据以源文件为准。", "",
                         "| ID / 源文件 | 文档状态 | 工作状态 | 摘要 |", "|---|---|---|---|"]
                for r in chunk:
                    relative = posixpath.relpath(r["path"], posixpath.dirname(rel_doc))
                    if r.get("anchor"):
                        relative += "#" + r["anchor"]
                    lines.append(f"| [{table_text(r.get('id'))}]({relative}) | {table_text(r.get('status'))} | "
                                 f"{table_text(r.get('state', r.get('release_state')))} | {table_text(r.get('summary'))} |")
                nav = ["[类型入口](../README.md)"]
                if n > 1:
                    nav.append(f"[上一页](page-{n-1:03d}.md)")
                if n < len(chunks):
                    nav.append(f"[下一页](page-{n+1:03d}.md)")
                lines += ["", " · ".join(nav)]
                (temp / "indexes" / typ / (file + ".md")).write_text("\n".join(lines) + "\n", encoding="utf-8")
                data = {"type": typ, "page": n, "pages": len(chunks),
                        "page_size": page_size, "records": chunk}
                (temp / "catalog" / typ / (file + ".json")).write_text(
                    json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (temp / "indexes" / "README.md").write_text(
            ("# 生成索引的类型入口\n\n不列全部条目；各类型按页查找。没有实例的类型不生成页面。\n\n"
             "| 类型 | 实例数量 | 入口 |\n|---|---:|---|\n" + "\n".join(top_rows)).rstrip() + "\n", encoding="utf-8")
        (temp / "catalog" / "README.md").write_text(
            "# 分页机器目录\n\n各类型目录的 page-NNN.json 最多包含配置规定数量的记录。"
            "只在需要时读取相应类型和页，不默认加载全库。源内容校验值用于识别漂移，不证明语义正确。\n", encoding="utf-8")
        for name in ("indexes", "catalog"):
            destination = generated / name
            if destination.exists():
                shutil.rmtree(destination)
            shutil.move(str(temp / name), str(destination))
    finally:
        shutil.rmtree(temp, ignore_errors=True)
    return {"records": len(records), "types": len(grouped), "pages_per_format": page_count,
            "page_size": page_size, "note": "只重建 _generated/indexes 与 _generated/catalog；不修改源记录。"}


@resource_scope
def show_routes(root: Path, query: str, *, resources: Path | None = None) -> list[dict[str, Any]]:
    root = root.resolve()
    routes = load_json(root, "docs/_system/routes.json")["routes"]
    exact = [r for r in routes if r["id"].casefold() == query.casefold()]
    matches = exact or [r for r in routes if any(query.casefold() in str(v).casefold()
               for v in [r["id"], r["title"], *r["keywords"]])]
    if not matches:
        raise DocError(f"没有匹配路由：{query}")
    choices = {c["key"]: c for c in registry(root)["collections"]}
    result = []
    for route in matches:
        states = []
        gaps = []
        def resolve(refs, *, writing=False):
            paths = []
            for ref in refs:
                path, state = resolve_reference(root, ref, choices, writing=writing)
                if state is not None:
                    if "collection" in state and state not in states:
                        states.append(state)
                    if path is None and state not in gaps:
                        gaps.append(state)
                if path is not None and path not in paths:
                    paths.append(path)
            return paths
        output = {**route, "must_read": resolve(route["must_read"]),
                  "write_back": resolve(route["write_back"], writing=True)}
        output["read_when"] = [{**rule, "paths": resolve(rule["paths"])} for rule in route.get("read_when", [])]
        output["collection_states"] = states
        output["gaps"] = gaps
        if runtime(root).lightweight and any(isinstance(ref, str) and ref.startswith("docs/_system/")
                                            for ref in route["write_back"]):
            output["write_note"] = ("项目配置写入 docs/.ai-docs.json，集合和路由定制使用 overrides；"
                                    "项目规则写入 docs/AGENTS.md 的托管区块之外。共享 Skill 资源只读。")
        result.append(output)
    return result


def cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2],
                        help="仓库根目录；默认由本脚本位置推导")
    parser.add_argument("--resources", type=Path,
                        help="外部 Skill 模板资源根目录；默认使用本脚本所在的资源包")
    subs = parser.add_subparsers(dest="action", required=True)
    check = subs.add_parser("check", help="检查结构；不执行项目命令")
    check.add_argument("--strict", action="store_true")
    new = subs.add_parser("new", help="从集合模板创建草稿，拒绝覆盖")
    new.add_argument("type")
    new.add_argument("id")
    new.add_argument("slug")
    new.add_argument("--title", required=True)
    new.add_argument("--kind", choices=sorted(TASK_KINDS))
    find = subs.add_parser("find", help="本地扫描元数据，只输出匹配摘要而非全部正文")
    find.add_argument("--type")
    find.add_argument("--status", choices=sorted(STATUSES))
    find.add_argument("--state", choices=sorted(TASK_STATES))
    find.add_argument("--kind", choices=sorted(TASK_KINDS))
    find.add_argument("--query")
    find.add_argument("--limit", type=int, default=20)
    find.add_argument("--include-archive", action="store_true")
    subs.add_parser("index", help="重建分页索引；不改变业务或任务状态")
    route = subs.add_parser("route", help="显示按任务读取和回写的路由")
    route.add_argument("query")
    args = parser.parse_args(argv)
    try:
        root = args.root.resolve()
        if args.action == "check":
            result = validate(root, args.strict, resources=args.resources)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0 if result["ok"] else 1
        if args.action == "new":
            path = make_new(root, args.type, args.id, args.slug, args.title, args.kind, resources=args.resources)
            print(json.dumps({"created": path.relative_to(root).as_posix(), "anchor": args.id.lower(), "status": "draft",
                              "note": "仍需填写、核验和相应批准；不代表已实现或获准执行。"}, ensure_ascii=False, indent=2))
        elif args.action == "find":
            print(json.dumps(find_records(root, args.type, args.status, args.state,
                                          args.kind, args.query, args.limit, args.include_archive, resources=args.resources),
                             ensure_ascii=False, indent=2))
        elif args.action == "index":
            print(json.dumps(generate_indexes(root, resources=args.resources), ensure_ascii=False, indent=2))
        elif args.action == "route":
            print(json.dumps(show_routes(root, args.query, resources=args.resources), ensure_ascii=False, indent=2))
        return 0
    except (DocError, OSError, UnicodeError, KeyError, TypeError, ValueError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(cli())
