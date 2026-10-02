#!/usr/bin/env python3
"""Synchronize minimum draft documentation from local code evidence, never run it.

Python >=3.10, standard library only. Initialization, migration and semantic
analysis are separate operations. Preview by default; apply a reviewed plan.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
from urllib.parse import quote

CONFIG = "docs/.ai-docs.json"
EXCLUDED = {".git", ".hg", ".svn", "node_modules", "vendor", ".venv", "venv",
            "__pycache__", ".cache", "dist", "build", "coverage", "_generated"}
LOCKFILES = {"package-lock.json", "pnpm-lock.yaml", "yarn.lock", "bun.lock", "bun.lockb",
             "uv.lock", "poetry.lock", "Cargo.lock", "go.sum"}
SLOTS = {
    "architecture-overview": ("docs/engineering/architecture/overview.md", "ARCH-OVERVIEW", "descriptive"),
    "development-guide": ("docs/engineering/development/quickstart.md", "DEV-QUICKSTART", "procedure"),
    "project-overview": ("docs/project/overview.md", "PROJECT-OVERVIEW", "normative"),
}
MARKER = re.compile(r'^<!-- ai-docs-sync: (\{[^\n]+\}) -->\n?', re.MULTILINE)


class SyncError(ValueError):
    pass


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SyncError(f"无法载入工具：{path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    previous = sys.dont_write_bytecode
    try:
        sys.dont_write_bytecode = True
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
    return module


def modules(source: Path):
    source = source.resolve()
    if not (source / "docs/_tools/docctl.py").is_file():
        raise SyncError("缺少公共资源；请提供同版本 ai-docs-check，或用 --source 指定资源根")
    return (load_module(source / "docs/_tools/init_docs.py", "_sync_installer"),
            load_module(source / "docs/_tools/docctl.py", "_sync_docctl"))


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def evidence_scan(target: Path, installer, *, max_files: int = 10000) -> dict:
    """Read only code paths and explicit manifest fields; skip symlinks and secrets."""
    target = installer._target_root(target)
    code, manifests, locks, markdown, snapshots, skipped = [], [], [], [], {}, []
    if not target.is_dir():
        raise SyncError("代码同步需要已有项目；请先执行 ai-docs-init")
    counted = 0
    for current, directories, names in os.walk(target, followlinks=False):
        parent = Path(current)
        directories[:] = sorted(name for name in directories if name not in EXCLUDED
                                and not name.startswith(".") and not (parent / name).is_symlink())
        for name in sorted(names):
            path = parent / name
            relative = path.relative_to(target).as_posix()
            counted += 1
            if counted > max_files:
                raise SyncError(f"盘点超过 {max_files} 个文件；请缩小项目范围，不能按不完整盘点生成文档")
            if path.is_symlink():
                skipped.append(relative)
                continue
            is_code = path.suffix in installer.CODE_EXTENSIONS and "docs" not in path.relative_to(target).parts
            is_manifest = name in installer.CODE_MANIFESTS and "docs" not in path.relative_to(target).parts
            is_lock = name in LOCKFILES and "docs" not in path.relative_to(target).parts
            if not (is_code or is_manifest or is_lock or path.suffix == ".md"):
                continue
            snapshots[relative] = sha(path.read_bytes())
            if is_code:
                code.append(relative)
            if is_manifest:
                manifests.append(relative)
            if is_lock:
                locks.append(relative)
            if path.suffix == ".md":
                markdown.append(relative)
    details = []
    for relative in manifests:
        path = target / relative
        info = {"path": relative, "name": None, "description": None, "runtime": {}, "scripts": {}}
        if path.stat().st_size > 1024 * 1024:
            raise SyncError(f"清单过大，请人工审阅：{relative}")
        text = path.read_text(encoding="utf-8")
        if path.name == "package.json":
            try:
                data = json.loads(text)
            except json.JSONDecodeError as exc:
                raise SyncError(f"清单 JSON 无效：{relative}: {exc}") from exc
            if not isinstance(data, dict):
                raise SyncError(f"清单必须是对象：{relative}")
            for key in ("name", "description"):
                if isinstance(data.get(key), str):
                    info[key] = data[key]
            if isinstance(data.get("engines"), dict):
                info["runtime"] = {k: v for k, v in data["engines"].items() if isinstance(v, str)}
            manager = data.get("packageManager")
            info["package_manager"] = manager if isinstance(manager, str) else None
            scripts = data.get("scripts", {})
            if not isinstance(scripts, dict) or any(not isinstance(v, str) for v in scripts.values()):
                raise SyncError(f"scripts 必须为字符串映射：{relative}")
            info["scripts"] = scripts
        elif path.name in {"pyproject.toml", "Cargo.toml"}:
            try:
                import tomllib
            except ImportError:
                info["unparsed_reason"] = "Python 3.10 无内置 TOML 解析器；只登记清单定位，升级到 3.11+ 可提取字段"
            else:
                try:
                    data = tomllib.loads(text)
                except tomllib.TOMLDecodeError as exc:
                    raise SyncError(f"清单 TOML 无效：{relative}: {exc}") from exc
                section = data.get("project" if path.name == "pyproject.toml" else "package", {})
                if not isinstance(section, dict):
                    raise SyncError(f"清单项目段必须为对象：{relative}")
                for key in ("name", "description"):
                    if isinstance(section.get(key), str):
                        info[key] = section[key]
                runtime_key = "requires-python" if path.name == "pyproject.toml" else "rust-version"
                if isinstance(section.get(runtime_key), str):
                    info["runtime"][runtime_key] = section[runtime_key]
                if isinstance(section.get("scripts"), dict):
                    info["scripts"] = {k: v for k, v in section["scripts"].items() if isinstance(v, str)}
        elif path.name == "go.mod":
            module = re.search(r"^module\s+(\S+)", text, re.MULTILINE)
            version = re.search(r"^go\s+(\S+)", text, re.MULTILINE)
            info["name"] = module.group(1) if module else None
            if version:
                info["runtime"]["go"] = version.group(1)
        else:
            info["unparsed_reason"] = "清单已登记定位；此格式的语义字段需人工确认"
        details.append(info)
    return {"target": str(target), "code_files": code, "manifests": details,
            "lockfiles": locks, "markdown_files": markdown, "skipped_symlinks": skipped,
            "has_code": bool(code or manifests), "_snapshots": snapshots}


def link(relative: str, destination: str) -> str:
    path = os.path.relpath(relative, Path(destination).parent).replace(os.sep, "/")
    label = relative.replace("[", "\\[").replace("]", "\\]")
    return f"[{label}]({quote(path, safe='/')})"


def marked(text: str) -> str:
    marker = "<!-- ai-docs-sync: " + json.dumps({"schema_version": 1, "sha256": sha(text.encode())},
                                                sort_keys=True) + " -->\n\n"
    # Marker is outside front matter; checks see the same ordinary business doc.
    closing = text.index("\n---\n", 4) + len("\n---\n")
    return text[:closing] + "\n" + marker + text[closing:].lstrip("\n")


def original_text(text: str) -> str:
    return MARKER.sub("", text, count=1).replace("\n\n\n", "\n\n", 1)


def owned(text: str) -> bool:
    matches = list(MARKER.finditer(text))
    if len(matches) != 1:
        return False
    try:
        record = json.loads(matches[0].group(1))
        return record.get("schema_version") == 1 and record.get("sha256") == sha(original_text(text).encode())
    except (ValueError, AttributeError):
        return False


def render(docctl, typ: str, facts: dict, title: str | None = None, summary: str | None = None) -> str:
    destination, doc_id, authority = SLOTS[typ]
    sources = {path: facts["_snapshots"][path] for path in facts["code_files"]
               + [item["path"] for item in facts["manifests"]] + facts["lockfiles"]}
    snapshot = sha(json.dumps(sources, sort_keys=True).encode())
    meta = {"id": doc_id, "type": typ, "status": "draft",
            "summary": summary or ("从仓库清单同步的代码定位与待确认架构。" if typ == "architecture-overview"
                                   else "从仓库清单同步的运行时与开发入口；命令尚未执行。"),
            "owner": None, "applies_to": "repository-source-sha256:" + snapshot,
            "verified_at": None, "verification_ref": None, "authority": authority}
    if authority in {"normative", "procedure"}:
        meta.update(approved_by=None, approval_ref=None)
    errors = docctl.validate_meta(meta, destination)
    if errors:
        raise SyncError("；".join(errors))
    lines = ["---", docctl.metadata_text(meta), "---", "", "# " + (title or (
        "代码结构与架构待确认项" if typ == "architecture-overview" else "开发入口与核验待办")), ""]
    if typ == "project-overview":
        lines += ["## 已确认概况", summary, "", "## 适用边界与待确认项",
                  "概况来自本次显式提供的内容。目标用户、验收指标、业务边界与批准尚待确认。", ""]
    elif typ == "architecture-overview":
        counts = {}
        for path in facts["code_files"]:
            parent = Path(path).parent.as_posix()
            counts[parent] = counts.get(parent, 0) + 1
        lines += ["## 直接观察到的代码结构", "目录只表示文件定位；职责、依赖方向与数据流需要阅读代码确认。", ""]
        for parent, count in sorted(counts.items()):
            lines.append(f"- {link(parent, destination)}：{count} 个可识别代码文件。")
        if not counts:
            lines.append("未发现可识别的代码后缀；已有构建清单见下方来源。")
        lines += ["", "## 架构待确认项",
                  "需要 AI 结合相关代码确认模块职责、入口、数据流、外部依赖和部署差异。产品目标与批准依据由项目负责人确认。", ""]
    else:
        lines += ["## 运行时与开发入口", "以下值直接取自清单；登记不代表命令安全、可用或已经核验。", ""]
        for manifest in facts["manifests"]:
            lines += ["### " + manifest["path"], ""]
            for key, value in manifest["runtime"].items():
                lines.append("- 运行时声明：" + json.dumps({key: value}, ensure_ascii=False))
            if manifest.get("package_manager"):
                lines.append("- 包管理器声明：" + json.dumps(manifest["package_manager"], ensure_ascii=False))
            for key, value in manifest["scripts"].items():
                lines.append("- 清单入口：" + json.dumps({key: value}, ensure_ascii=False))
            if manifest.get("unparsed_reason"):
                lines.append("- " + manifest["unparsed_reason"])
            if not manifest["runtime"] and not manifest["scripts"]:
                lines.append("运行时或启动命令未从支持的清单字段得到，需按实际代码确认。")
            lines.append("")
        if not facts["manifests"]:
            lines += ["没有受支持的构建清单；需从代码入口确认准备、启动和验证方式。", ""]
        lines += ["## 配置与核验", "命令与位置的正式登记在项目 docs/.ai-docs.json；本次不执行项目命令。",
                  "环境、超时、副作用、样例数据、成功信号和失败处理尚待核验；核验前 verified_at 与 verification_ref 保持 null。", ""]
    lines += ["## 来源快照", "本草案记录本地文件盘点，核验时间保持未知。来源变更后重新预览同步。", ""]
    for relative in [item["path"] for item in facts["manifests"]] + facts["lockfiles"]:
        lines.append(f"- {link(relative, destination)}：SHA-256 `{sources[relative]}`")
    if not facts["manifests"] and not facts["lockfiles"]:
        for relative in facts["code_files"][:20]:
            lines.append(f"- {link(relative, destination)}：SHA-256 `{sources[relative]}`")
    lines += ["", "来源集合 SHA-256：`" + snapshot + "`。", ""]
    return marked("\n".join(lines))


def plan_sync(source: Path, target: Path, *, overview_title: str | None = None,
              overview_summary: str | None = None) -> dict:
    installer, docctl = modules(source)
    target = installer._target_root(target)
    docctl.require_project_write_target(target)
    if not (target / CONFIG).is_file():
        raise SyncError("请先运行 ai-docs-init；代码同步不隐式初始化文档系统")
    context = docctl.runtime(target)
    if not context.lightweight:
        raise SyncError("代码同步要求最小文档系统配置")
    if bool(overview_title) != bool(overview_summary):
        raise SyncError("项目总纲需同时提供 --overview-title 与 --overview-summary")
    for value in (overview_title, overview_summary):
        if value is not None and (not value.strip() or "\n" in value or "\r" in value):
            raise SyncError("总纲标题与摘要须为非空单行内容")
    facts = evidence_scan(target, installer)
    baseline = docctl.validate(target, resources=source)
    existing = docctl.collect_records(target, include_archive=True)
    expected = dict(facts["_snapshots"])
    expected[CONFIG] = installer._snapshot(installer._destination(target, CONFIG))
    plan = {"schema_version": 1, "operation": "sync", "source": str(source.resolve()),
            "resource_version": context.config["system"]["version"], "target": str(target),
            "status": "planned", "actions": [], "preserved": [], "conflicts": [],
            "facts": {k: v for k, v in facts.items() if not k.startswith("_")},
            "baseline_errors": baseline["errors"], "_expected": expected, "_payloads": {}}
    types = ["architecture-overview", "development-guide"] if facts["has_code"] else []
    if overview_title:
        types.append("project-overview")
    for typ in types:
        relative, doc_id, _ = SLOTS[typ]
        path = installer._destination(target, relative)
        before = installer._snapshot(path)
        expected[relative] = before
        matches = [item for item in existing if item.get("type") == typ or item.get("id") == doc_id]
        if matches and (len(matches) > 1 or matches[0]["path"] != relative):
            plan["preserved"].append({"type": typ, "paths": sorted({item["path"] for item in matches}),
                                      "reason": "已有同类对象；请由 AI 确认并更新原对象"})
            continue
        if before is not None and (before == "directory" or not owned(path.read_text(encoding="utf-8"))):
            plan["preserved"].append({"path": relative, "reason": "已有人工内容或同步后本地修改；保留原文"})
            continue
        text = render(docctl, typ, facts, overview_title if typ == "project-overview" else None,
                      overview_summary if typ == "project-overview" else None)
        after = sha(text.encode())
        if before == after:
            continue
        plan["actions"].append({"path": relative, "operation": "create" if before is None else "update",
                                "before_sha256": before, "after_sha256": after})
        plan["_payloads"][relative] = base64.b64encode(text.encode()).decode("ascii")
    if not plan["actions"]:
        plan["status"] = "noop"
    return plan


def apply_sync(source: Path, target: Path, plan: dict) -> dict:
    installer, docctl = modules(source)
    target = installer._target_root(target)
    docctl.require_project_write_target(target)
    if (plan.get("schema_version") != 1 or plan.get("operation") != "sync"
            or plan.get("target") != str(target) or plan.get("source") != str(source.resolve())):
        raise SyncError("计划类型、资源或目标不匹配")
    context = docctl.runtime(target)
    if context.config["system"]["version"] != plan.get("resource_version"):
        raise SyncError("计划生成后协议版本变化，请重新预览")
    permitted = {record[0]: typ for typ, record in SLOTS.items()}
    actions = plan["actions"]
    paths = [item["path"] for item in actions]
    if len(set(paths)) != len(paths) or set(paths) != set(plan["_payloads"]) or not set(paths) <= permitted.keys():
        raise SyncError("计划包含非同步文档或重复动作")
    decoded = {}
    for action in actions:
        relative = action["path"]
        if action["operation"] not in {"create", "update"} or action["before_sha256"] != plan["_expected"].get(relative):
            raise SyncError("计划动作或基线无效")
        content = base64.b64decode(plan["_payloads"][relative], validate=True)
        if sha(content) != action["after_sha256"]:
            raise SyncError("计划内容哈希不匹配")
        text = content.decode("utf-8")
        entries = docctl.document_entries(text, relative)
        typ = permitted[relative]
        if (len(entries) != 1 or entries[0]["meta"].get("type") != typ
                or entries[0]["meta"].get("id") != SLOTS[typ][1]
                or entries[0]["meta"].get("status") != "draft" or not owned(text)):
            raise SyncError("同步只允许指定类型、身份且有完整来源的草案")
        errors = docctl.validate_meta(entries[0]["meta"], relative, resources=source)
        if errors:
            raise SyncError("；".join(errors))
        decoded[relative] = content
    lock = installer._destination(target, "docs/.docctl.lock")
    descriptor = None
    changes, created_dirs = [], []

    def recheck():
        if evidence_scan(target, installer)["_snapshots"] != {
            key: value for key, value in plan["_expected"].items() if key in plan["facts"]["code_files"]
            or key in plan["facts"]["markdown_files"] or key in plan["facts"]["lockfiles"]
            or key in {item["path"] for item in plan["facts"]["manifests"]}}:
            raise SyncError("计划生成后代码或文档集合已有变化，请重新预览")
        for relative, before in plan["_expected"].items():
            if installer._snapshot(installer._destination(target, relative)) != before:
                raise SyncError(f"计划生成后目标已有变化：{relative}")

    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0), 0o600)
        recheck()
        baseline_errors = set(docctl.validate(target, resources=source)["errors"])
        for action in actions:
            relative = action["path"]
            path = installer._destination(target, relative)
            if installer._snapshot(path) != action["before_sha256"]:
                raise SyncError(f"应用期间目标已有变化：{relative}")
            original = path.read_bytes() if path.is_file() else None
            if (action["operation"] == "create") != (original is None):
                raise SyncError("计划动作与目标存在状态不一致")
            if original is not None and not owned(original.decode("utf-8")):
                raise SyncError(f"目标包含人工内容或本地修改，拒绝覆盖：{relative}")
            missing, parent = [], path.parent
            while not parent.exists():
                missing.append(parent)
                parent = parent.parent
            for directory in reversed(missing):
                directory.mkdir()
                created_dirs.append(directory)
            changes.append((path, original, action["after_sha256"]))
            installer._atomic_write(path, decoded[relative], create=original is None)
        expected_after = {path: baseline for path, baseline in plan["_expected"].items()
                          if path != CONFIG and baseline not in {None, "directory"}}
        expected_after.update({item["path"]: item["after_sha256"] for item in actions})
        if (evidence_scan(target, installer)["_snapshots"] != expected_after
                or installer._snapshot(installer._destination(target, CONFIG)) != plan["_expected"][CONFIG]):
            raise SyncError("同步期间代码、文档或配置并发改变；请重新预览")
        validation = docctl.validate(target, resources=source)
        introduced = set(validation["errors"]) - baseline_errors
        if introduced:
            raise SyncError("同步引入结构问题，已回滚：" + "；".join(sorted(introduced)))
        return {**public(plan), "applied": True, "status": "synced" if actions else "noop",
                "validation": validation}
    except (OSError, ValueError) as exc:
        failures = []
        for path, original, after in reversed(changes):
            current = installer._snapshot(path)
            if current == (sha(original) if original is not None else None):
                continue
            if current != after:
                failures.append(str(path.relative_to(target)))
                continue
            try:
                if original is None:
                    path.unlink(missing_ok=True)
                else:
                    installer._atomic_write(path, original, create=False)
            except (ValueError, OSError):
                failures.append(str(path.relative_to(target)))
        if failures:
            raise SyncError(f"{exc}；回滚未完成，保留并发修改或写入失败：" + "；".join(failures)) from exc
        raise
    finally:
        if descriptor is not None:
            os.close(descriptor)
            lock.unlink(missing_ok=True)
        for directory in reversed(created_dirs):
            try:
                directory.rmdir()
            except OSError:
                pass


def public(plan: dict) -> dict:
    return {key: value for key, value in plan.items() if not key.startswith("_")}


def cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", required=True, type=Path)
    parser.add_argument("--source", type=Path, default=Path(__file__).resolve().parents[2] / "ai-docs-check/assets/templates")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--scan", action="store_true")
    mode.add_argument("--apply", action="store_true")
    parser.add_argument("--plan-file", type=Path)
    parser.add_argument("--overview-title")
    parser.add_argument("--overview-summary")
    args = parser.parse_args(argv)
    try:
        source, target = args.source.resolve(), args.target.absolute()
        if args.scan:
            if args.plan_file or args.overview_title or args.overview_summary:
                raise SyncError("--scan 只盘点，不生成计划或总纲")
            installer, _ = modules(source)
            result = public(evidence_scan(target, installer))
        elif args.apply:
            if not args.plan_file or args.overview_title or args.overview_summary:
                raise SyncError("--apply 需要 --plan-file 应用同一计划；总纲参数只用于预览")
            plan = json.loads(args.plan_file.read_text(encoding="utf-8"))
            result = apply_sync(source, target, plan)
        else:
            plan = plan_sync(source, target, overview_title=args.overview_title, overview_summary=args.overview_summary)
            if args.plan_file:
                if args.plan_file.resolve().is_relative_to(target.resolve()):
                    raise SyncError("同步计划需保存在目标项目之外")
                with args.plan_file.open("x", encoding="utf-8") as stream:
                    json.dump(plan, stream, ensure_ascii=False, indent=2)
                    stream.write("\n")
            result = {**public(plan), "applied": False}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False, indent=2), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(cli())
