#!/usr/bin/env python3
"""Documentation helper. Python >=3.10; standard library only.

Never executes registered commands, calls a network service, approves a document,
or changes source record state. Only `new` and `index` write files.
Front matter supports a documented, flat YAML subset: key: JSON scalar.
"""
from __future__ import annotations

import argparse
import hashlib
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


class DocError(ValueError):
    """An actionable configuration or document error."""


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
    path = safe_path(root, relative)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DocError(f"无法读取 JSON {relative}: {exc}") from exc


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
    records = []
    for path in source_markdown(root):
        rel = path.relative_to(root)
        if is_template(rel):
            continue
        if not include_archive and "archive" in rel.parts:
            continue
        raw = path.read_text(encoding="utf-8")
        meta = parse_frontmatter(raw, rel.as_posix())
        if meta is None or meta.get("status") == "template":
            continue
        if not include_archive and meta.get("status") == "archived":
            continue
        title_match = re.search(r"^#\s+(.+)$", raw, re.MULTILINE)
        records.append({**meta, "path": rel.as_posix(),
                        "title": title_match.group(1).strip() if title_match else "",
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


def relative_link_errors(root: Path, path: Path, text: str) -> list[str]:
    """Check ordinary inline local Markdown file links; not network/anchors."""
    errors = []
    for match in LINK_RE.finditer(without_code_fences(text)):
        target = match.group(1).strip()
        # Our templates use normal inline links; optional titles are ignored.
        if target.startswith("<") and ">" in target:
            target = target[1:target.index(">")]
        else:
            target = target.split(' "', 1)[0].split(" '", 1)[0]
        if not target or PLACEHOLDER_RE.search(target):
            continue
        parsed = urlsplit(target)
        if parsed.scheme or parsed.netloc or not parsed.path:
            continue
        decoded = unquote(parsed.path)
        if decoded.startswith("/"):
            errors.append(f"{path.relative_to(root)}: 请使用仓库内相对链接：{target}")
            continue
        relative = (path.parent / decoded).relative_to(root).as_posix()
        try:
            destination = safe_path(root, relative)
            if not destination.exists():
                errors.append(f"{path.relative_to(root)}: 相对链接目标不存在：{target}")
        except DocError as exc:
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


def registry(root: Path) -> dict[str, Any]:
    data = load_json(root, "docs/_system/collections.json")
    if not isinstance(data, dict) or not isinstance(data.get("collections"), list):
        raise DocError("collections.json 需要 collections 数组")
    if not isinstance(data.get("page_size"), int) or not 1 <= data["page_size"] <= 100:
        raise DocError("page_size 必须为 1 到 100 的整数")
    return data


def validate(root: Path, strict: bool = False) -> dict[str, Any]:
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
        if not path.is_file():
            errors.append(f"缺少入口：{rootfile}")
        else:
            paths.append(path)
    for path in sorted(paths):
        rel = path.relative_to(root).as_posix()
        text = path.read_text(encoding="utf-8")
        errors.extend(relative_link_errors(root, path, text))
        if is_template(Path(rel)):
            # Agent Skills uses its own specification; adapters may use theirs.
            if path.name != "_template.md":
                continue
        try:
            meta = parse_frontmatter(text, rel)
        except DocError as exc:
            errors.append(str(exc))
            continue
        if meta is None:
            continue
        missing = REQUIRED - meta.keys()
        if missing:
            errors.append(f"{rel}: 缺少元数据 {', '.join(sorted(missing))}")
        if meta.get("status") not in STATUSES:
            errors.append(f"{rel}: 非法 status")
        if meta.get("authority") not in AUTHORITIES:
            errors.append(f"{rel}: 非法 authority")
        typ = meta.get("type")
        if not isinstance(typ, str) or not TYPE_RE.fullmatch(typ):
            errors.append(f"{rel}: 非法 type")
        if meta.get("status") == "template" or is_template(Path(rel)):
            if meta.get("status") != "template":
                errors.append(f"{rel}: 模板文件的 status 必须为 template")
            continue
        doc_id = meta.get("id")
        if not isinstance(doc_id, str) or not ID_RE.fullmatch(doc_id):
            errors.append(f"{rel}: 非法或未填写 id")
        elif doc_id in ids:
            errors.append(f"重复 ID {doc_id}: {ids[doc_id]} 与 {rel}")
        else:
            ids[doc_id] = rel
        record_metas[rel] = meta
        verified = meta.get("verified_at")
        reference = meta.get("verification_ref")
        if bool(verified) != bool(reference):
            errors.append(f"{rel}: verified_at 与 verification_ref 必须同时填写或同时为空")
        if verified is not None and not date_is_valid(verified):
            errors.append(f"{rel}: verified_at 须为 ISO 日期或带时区的时间")
        if typ == "task":
            if meta.get("state") not in TASK_STATES:
                errors.append(f"{rel}: 非法任务 state")
            if meta.get("kind") not in TASK_KINDS:
                errors.append(f"{rel}: 非法任务 kind")
            if meta.get("handover_ref"):
                try:
                    if not safe_path(root, meta["handover_ref"]).is_file():
                        errors.append(f"{rel}: handover_ref 目标不存在")
                except DocError as exc:
                    errors.append(f"{rel}: {exc}")
        if typ == "release" and meta.get("release_state") not in RELEASE_STATES:
            errors.append(f"{rel}: 非法 release_state")
        if meta.get("status") == "active":
            if PLACEHOLDER_RE.search(text):
                errors.append(f"{rel}: active 文档仍包含未填写占位符")
            if not meta.get("owner"):
                (errors if strict else warnings).append(f"{rel}: active 文档缺少 owner")
            if not verified:
                (errors if strict else warnings).append(f"{rel}: active 文档缺少核验记录")
            if meta.get("authority") in ("normative", "procedure"):
                if not meta.get("approved_by") or not meta.get("approval_ref"):
                    errors.append(f"{rel}: 生效规范/程序缺少批准依据")
    try:
        reg = registry(root)
        seen_keys: set[str] = set()
        for item in reg["collections"]:
            key = item.get("key")
            if not isinstance(key, str) or not TYPE_RE.fullmatch(key) or key in seen_keys:
                errors.append(f"collections.json: 非法或重复类型键 {key}")
                continue
            seen_keys.add(key)
            for field in ("directory", "template"):
                dest = safe_path(root, item.get(field, ""))
                if not dest.exists():
                    errors.append(f"collections.json: {key}.{field} 不存在")
        routes = load_json(root, "docs/_system/routes.json")["routes"]
        seen_routes: set[str] = set()
        for item in routes:
            if item["id"] in seen_routes:
                errors.append(f"重复路由 ID: {item['id']}")
            seen_routes.add(item["id"])
            refs = list(item["must_read"]) + list(item["write_back"])
            for rule in item.get("read_when", []):
                refs.extend(rule["paths"])
            for ref in refs:
                if not safe_path(root, ref).exists():
                    errors.append(f"路由 {item['id']}: 路径不存在 {ref}")
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
                p = safe_path(root, ref)
                if not p.is_file():
                    errors.append(f"必需文档不存在：{ref}")
                    continue
                content = p.read_text(encoding="utf-8")
                if PLACEHOLDER_RE.search(content):
                    errors.append(f"必需文档未填写：{ref}")
                if ref in record_metas and record_metas[ref].get("status") != "active":
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
    except (DocError, KeyError, TypeError) as exc:
        errors.append(f"配置结构错误：{exc}")
    return {"ok": not errors, "mode": "strict" if strict else "structure",
            "markdown_files_checked": len(paths), "records": len(record_metas),
            "errors": errors, "warnings": warnings,
            "limits": "不执行项目命令，不联网，不校验法律/业务语义、外部权限、完整 YAML 或 Markdown 锚点。"}


def make_new(root: Path, key: str, doc_id: str, slug: str, title: str,
             kind: str | None = None) -> Path:
    choices = {c["key"]: c for c in registry(root)["collections"]}
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
    if any(r.get("id") == doc_id for r in collect_records(root, include_archive=True)):
        raise DocError(f"ID 已存在，拒绝覆盖：{doc_id}")
    source = safe_path(root, item["template"]).read_text(encoding="utf-8")
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
    target = safe_path(root, f"{item['directory']}/{doc_id}-{slug}.md")
    target.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation also prevents accidental overwrite during concurrent use.
    try:
        with target.open("x", encoding="utf-8") as stream:
            stream.write(text)
    except FileExistsError as exc:
        raise DocError(f"文件已存在，拒绝覆盖：{target.relative_to(root)}") from exc
    return target


def find_records(root: Path, typ: str | None = None, status: str | None = None,
                 state: str | None = None, kind: str | None = None,
                 query: str | None = None, limit: int = 20,
                 include_archive: bool = False) -> dict[str, Any]:
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


def generate_indexes(root: Path) -> dict[str, Any]:
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
            "# 生成索引的类型入口\n\n不列全部条目；各类型按页查找。没有实例的类型不生成页面。\n\n"
            "| 类型 | 实例数量 | 入口 |\n|---|---:|---|\n" + "\n".join(top_rows) + "\n", encoding="utf-8")
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


def show_routes(root: Path, query: str) -> list[dict[str, Any]]:
    routes = load_json(root, "docs/_system/routes.json")["routes"]
    exact = [r for r in routes if r["id"].casefold() == query.casefold()]
    if exact:
        return exact
    matches = [r for r in routes if any(query.casefold() in str(v).casefold()
               for v in [r["id"], r["title"], *r["keywords"]])]
    if not matches:
        raise DocError(f"没有匹配路由：{query}")
    return matches


def cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2],
                        help="仓库根目录；默认由本脚本位置推导")
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
            result = validate(root, args.strict)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0 if result["ok"] else 1
        if args.action == "new":
            path = make_new(root, args.type, args.id, args.slug, args.title, args.kind)
            print(json.dumps({"created": path.relative_to(root).as_posix(), "status": "draft",
                              "note": "仍需填写、核验和相应批准；不代表已实现或获准执行。"}, ensure_ascii=False, indent=2))
        elif args.action == "find":
            print(json.dumps(find_records(root, args.type, args.status, args.state,
                                          args.kind, args.query, args.limit, args.include_archive),
                             ensure_ascii=False, indent=2))
        elif args.action == "index":
            print(json.dumps(generate_indexes(root), ensure_ascii=False, indent=2))
        elif args.action == "route":
            print(json.dumps(show_routes(root, args.query), ensure_ascii=False, indent=2))
        return 0
    except (DocError, OSError, UnicodeError, KeyError, TypeError, ValueError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(cli())
