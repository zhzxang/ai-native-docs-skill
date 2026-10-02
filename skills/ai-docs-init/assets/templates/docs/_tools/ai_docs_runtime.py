#!/usr/bin/env python3
"""Resolve project configuration and external AI documentation resources.

Project facts live in docs/.ai-docs.json. Shared definitions remain beside this
module in the Skill bundle. This module only reads; it never creates directories.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
import re
from typing import Any

CONFIG_PATH = "docs/.ai-docs.json"
SYSTEM_NAME = "ai-docs-system"
ENTRY_FILES = {"README.md", "AGENTS.md", "docs/README.md", "docs/AGENTS.md"}


class RuntimeError(ValueError):
    """Missing, incompatible, or unsafe documentation configuration."""


def safe_path(root: Path, relative: str) -> Path:
    if (not isinstance(relative, str) or not relative.strip()
            or Path(relative).is_absolute() or ".." in Path(relative).parts):
        raise RuntimeError(f"需要安全的仓库相对路径：{relative}")
    base = root.resolve()
    path = (base / relative).resolve()
    if not path.is_relative_to(base):
        raise RuntimeError(f"路径越过资源或项目边界：{relative}")
    return path


def read_json(root: Path, relative: str) -> Any:
    try:
        return json.loads(safe_path(root, relative).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"无法读取 JSON {relative}: {exc}") from exc


def resource_root(resources: Path | None = None) -> Path:
    return (Path(resources) if resources is not None else Path(__file__).resolve().parents[2]).resolve()


def package_version(resources: Path | None = None) -> str:
    package = read_json(resource_root(resources), "docs/_system/package.json")
    version = package.get("system_version") if isinstance(package, dict) else None
    if (not isinstance(package, dict) or package.get("name") != SYSTEM_NAME
            or not isinstance(version, str) or not re.fullmatch(r"\d+\.\d+\.\d+", version)):
        raise RuntimeError("Skill 资源 package.json 缺少有效系统名称或版本")
    return version


def default_config(resources: Path | None = None) -> dict[str, Any]:
    version = package_version(resources)
    return {
        "schema_version": 1,
        "system": {"name": SYSTEM_NAME, "version": version},
        "project": {"name": None, "owner": None, "operating_mode": "bootstrap"},
        "work_tracking": {"mode": "repository", "source": "docs/work/items", "external_ref": None},
        "locations": [],
        "commands": [],
        "installation": {"schema_version": 1, "system_version": version,
                         "owned_blocks": {}, "status": "installed"},
    }


def _object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RuntimeError(f"{label} 必须为对象")
    return value


def _array(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise RuntimeError(f"{label} 必须为数组")
    return value


def _relative(value: Any, label: str) -> str:
    if (not isinstance(value, str) or not value.strip() or Path(value).is_absolute()
            or any(part in {"..", ".git"} for part in Path(value).parts)):
        raise RuntimeError(f"{label} 必须为安全的仓库相对路径")
    return value


def _named_records(value: Any, label: str) -> list[dict[str, Any]]:
    records = _array(value, label)
    seen: set[str] = set()
    for record in records:
        item = _object(record, label + " 条目")
        key = item.get("id")
        if not isinstance(key, str) or not key.strip() or key in seen:
            raise RuntimeError(f"{label} 包含非法或重复 ID：{key}")
        seen.add(key)
    return records


def validate_collections(value: Any) -> None:
    data = _object(value, "overrides.collections")
    if type(data.get("schema_version")) is not int or data["schema_version"] != 2:
        raise RuntimeError("轻量模式 collections schema_version 必须为 2")
    defaults = _object(data.get("defaults"), "collections.defaults")
    if defaults.get("compact_max_items") != 2:
        raise RuntimeError("compact_max_items 必须为 2")
    for key in ("create_empty_business_documents", "create_empty_collection_directories", "auto_collapse"):
        if defaults.get(key) is not False:
            raise RuntimeError(f"collections.defaults.{key} 必须为 false")
    page_size = data.get("page_size")
    if type(page_size) is not int or not 1 <= page_size <= 100:
        raise RuntimeError("collections.page_size 必须为 1 到 100 的整数")
    keys: set[str] = set()
    bases: set[str] = set()
    for record in _array(data.get("collections"), "collections.collections"):
        item = _object(record, "collection 条目")
        key = item.get("key")
        if not isinstance(key, str) or not re.fullmatch(r"[a-z][a-z0-9-]*", key) or key in keys:
            raise RuntimeError(f"非法或重复 collection key：{key}")
        keys.add(key)
        base = _relative(item.get("base_path"), f"collection {key}.base_path")
        if (base in bases or Path(base).suffix or not base.startswith("docs/")
                or any(part.startswith("_") for part in Path(base).parts)):
            raise RuntimeError(f"非法或重复 collection base_path：{base}")
        bases.add(base)
        if item.get("template") != f"docs/_templates/{key}.md":
            raise RuntimeError(f"collection {key}.template 必须引用集中模板")
        if not isinstance(item.get("prefix"), str) or not re.fullmatch(r"[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*", item["prefix"]):
            raise RuntimeError(f"collection {key}.prefix 无效")
        for field in ("title", "summary", "authority"):
            if not isinstance(item.get(field), str) or not item[field].strip():
                raise RuntimeError(f"collection {key}.{field} 必须为非空字符串")


def _validate_ref(value: Any, keys: set[str], label: str) -> None:
    if isinstance(value, str):
        _relative(value, label)
    elif isinstance(value, dict) and set(value) == {"collection"}:
        if not isinstance(value["collection"], str) or value["collection"] not in keys:
            raise RuntimeError(f"{label} 引用未知 collection：{value['collection']}")
    elif isinstance(value, dict) and set(value) == {"optional_path"}:
        _relative(value["optional_path"], label)
    else:
        raise RuntimeError(f"{label} 包含非法路由引用")


def validate_routes(value: Any, collections: dict[str, Any]) -> None:
    data = _object(value, "overrides.routes")
    if type(data.get("schema_version")) is not int or data["schema_version"] != 2:
        raise RuntimeError("轻量模式 routes schema_version 必须为 2")
    keys = {item["key"] for item in collections["collections"]}
    for item in _named_records(data.get("routes"), "routes"):
        if not isinstance(item.get("title"), str) or not item["title"].strip():
            raise RuntimeError(f"route {item['id']}.title 必须为非空字符串")
        if any(not isinstance(word, str) for word in _array(item.get("keywords"), "route keywords")):
            raise RuntimeError("route keywords 必须为字符串数组")
        refs = _array(item.get("must_read"), "route must_read") + _array(item.get("write_back"), "route write_back")
        for rule in _array(item.get("read_when", []), "route read_when"):
            rule = _object(rule, "route read_when 条目")
            if not isinstance(rule.get("condition"), str):
                raise RuntimeError("route read_when.condition 必须为字符串")
            refs += _array(rule.get("paths"), "route read_when.paths")
        for ref in refs:
            _validate_ref(ref, keys, f"route {item['id']}")


def validate_config(value: Any, *, resources: Path | None = None, check_version: bool = True) -> None:
    config = _object(value, CONFIG_PATH)
    if type(config.get("schema_version")) is not int or config["schema_version"] != 1:
        raise RuntimeError(f"{CONFIG_PATH} schema_version 必须为 1")
    # Unknown project fields may carry established facts and are preserved.
    system = _object(config.get("system"), "system")
    if (system.get("name") != SYSTEM_NAME or not isinstance(system.get("version"), str)
            or not re.fullmatch(r"\d+\.\d+\.\d+", system["version"])):
        raise RuntimeError("system 必须声明 ai-docs-system 与固定协议版本")
    if check_version:
        available = package_version(resources)
        if system["version"] != available:
            raise RuntimeError(f"协议版本不匹配：项目固定 {system['version']}，Skill 资源为 {available}；先取得对应版本或显式升级")
    project = _object(config.get("project"), "project")
    if project.get("operating_mode") not in {"bootstrap", "maintenance"}:
        raise RuntimeError("project.operating_mode 必须为 bootstrap 或 maintenance")
    for field in ("name", "owner"):
        if project.get(field) is not None and not isinstance(project[field], str):
            raise RuntimeError(f"project.{field} 必须为字符串或 null")
    tracking = _object(config.get("work_tracking"), "work_tracking")
    if tracking.get("mode") not in {"repository", "external"}:
        raise RuntimeError("work_tracking.mode 必须为 repository 或 external")
    if tracking.get("source") is not None:
        _relative(tracking["source"], "work_tracking.source")
    for item in _named_records(config.get("locations"), "locations"):
        if item.get("enabled") is not None and type(item["enabled"]) is not bool:
            raise RuntimeError(f"location {item['id']}.enabled 必须为 true / false / null")
        for path in _array(item.get("paths", []), "location paths"):
            _relative(path, f"location {item['id']}.paths")
        if item.get("repository") is not None and not isinstance(item["repository"], str):
            raise RuntimeError("location.repository 必须为字符串或 null")
    for item in _named_records(config.get("commands"), "commands"):
        argv = item.get("argv")
        if argv is not None and (not isinstance(argv, list) or not argv
                or any(not isinstance(arg, str) or not arg for arg in argv)):
            raise RuntimeError(f"command {item['id']}.argv 必须为非空字符串数组或 null")
        if item.get("cwd") is not None:
            _relative(item["cwd"], f"command {item['id']}.cwd")
        if item.get("timeout_seconds") is not None and (
                type(item["timeout_seconds"]) is not int or item["timeout_seconds"] <= 0):
            raise RuntimeError(f"command {item['id']}.timeout_seconds 必须为正整数或 null")
    if "readiness" in config:
        readiness = _object(config["readiness"], "readiness")
        for name in ("required_documents", "required_locations", "required_commands"):
            values = _array(readiness.get(name), f"readiness.{name}")
            if name != "required_documents" and any(not isinstance(item, str) or not item for item in values):
                raise RuntimeError(f"readiness.{name} 必须为非空字符串数组")
    overrides = _object(config.get("overrides", {}), "overrides")
    if set(overrides) - {"collections", "routes"}:
        raise RuntimeError("overrides 只支持 collections 与 routes")
    if "collections" in overrides:
        validate_collections(overrides["collections"])
    if "routes" in overrides or "readiness" in config:
        collections = overrides.get("collections") or read_json(resource_root(resources), "docs/_system/collections.json")
        validate_collections(collections)
        if "routes" in overrides:
            validate_routes(overrides["routes"], collections)
        for ref in config.get("readiness", {}).get("required_documents", []):
            _validate_ref(ref, {item["key"] for item in collections["collections"]}, "readiness.required_documents")
    installation = _object(config.get("installation"), "installation")
    if (type(installation.get("schema_version")) is not int or installation["schema_version"] != 1
            or installation.get("system_version") != system["version"]):
        raise RuntimeError("installation 的 schema_version 或 system_version 与配置不一致")
    if "owned_files" in installation:
        raise RuntimeError("轻量配置不托管系统文件，不应包含 installation.owned_files")
    if not isinstance(installation.get("status"), str) or not installation["status"]:
        raise RuntimeError("installation.status 必须为非空字符串")
    for relative, record in _object(installation.get("owned_blocks"), "installation.owned_blocks").items():
        if relative not in ENTRY_FILES or not isinstance(record, dict) or record.get("id") != "ai-docs-init":
            raise RuntimeError(f"未知托管入口区块：{relative}")
        if not re.fullmatch(r"[0-9a-f]{64}", str(record.get("sha256", ""))):
            raise RuntimeError(f"托管入口区块基线无效：{relative}")
    if "migration" in config:
        _object(config["migration"], "migration")


class Runtime:
    def __init__(self, root: Path, resources: Path | None = None):
        self.root = root.resolve()
        self.resources = resource_root(resources)
        path = safe_path(self.root, CONFIG_PATH)
        self.lightweight = path.exists()
        self.config = read_json(self.root, CONFIG_PATH) if self.lightweight else None
        if self.lightweight:
            validate_config(self.config, resources=self.resources)

    def load(self, relative: str) -> Any:
        if not self.lightweight:
            return read_json(self.root, relative)
        config = self.config
        if relative == CONFIG_PATH:
            return copy.deepcopy(config)
        if relative == "docs/_system/project-map.json":
            readiness = config.get("readiness")
            if readiness is None:
                readiness = read_json(self.resources, relative)["readiness"]
            return {"schema_version": 1, "project": copy.deepcopy(config["project"]),
                    "work_tracking": copy.deepcopy(config["work_tracking"]),
                    "locations": copy.deepcopy(config["locations"]), "readiness": copy.deepcopy(readiness)}
        if relative == "docs/_system/commands.json":
            return {"schema_version": 1, "commands": copy.deepcopy(config["commands"])}
        if relative in {"docs/_system/collections.json", "docs/_system/routes.json"}:
            key = Path(relative).stem
            override = config.get("overrides", {}).get(key)
            value = copy.deepcopy(override) if override is not None else read_json(self.resources, relative)
            if key == "collections":
                validate_collections(value)
            else:
                validate_routes(value, self.load("docs/_system/collections.json"))
            return value
        return read_json(self.resources, relative)

    def template(self, relative: str) -> Path:
        if not isinstance(relative, str) or not relative.startswith("docs/_templates/"):
            raise RuntimeError("模板须从集中模板资源目录读取")
        path = safe_path(self.resources if self.lightweight else self.root, relative)
        if not path.is_file():
            raise RuntimeError(f"Skill 模板资源不存在：{relative}")
        return path

    def reference(self, relative: str) -> Path:
        if self.lightweight and relative in {"docs/_system/project-map.json", "docs/_system/commands.json"}:
            return safe_path(self.root, CONFIG_PATH)
        if (self.lightweight and relative in {"docs/_system/collections.json", "docs/_system/routes.json"}
                and Path(relative).stem in self.config.get("overrides", {})):
            return safe_path(self.root, CONFIG_PATH)
        external = self.lightweight and relative.startswith(("docs/_system/", "docs/_templates/", "docs/_tools/"))
        return safe_path(self.resources if external else self.root, relative)

    def write_reference(self, relative: str) -> Path:
        if self.lightweight and relative in {
                "docs/_system/project-map.json", "docs/_system/commands.json",
                "docs/_system/collections.json", "docs/_system/routes.json"}:
            return safe_path(self.root, CONFIG_PATH)
        if self.lightweight and relative.startswith("docs/_system/") and relative.endswith(".md"):
            return safe_path(self.root, "docs/AGENTS.md")
        if self.lightweight and relative.startswith(("docs/_system/", "docs/_templates/", "docs/_tools/")):
            raise RuntimeError(f"项目路由不能回写共享 Skill 资源：{relative}")
        return safe_path(self.root, relative)
