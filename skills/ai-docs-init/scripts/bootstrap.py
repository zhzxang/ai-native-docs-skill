#!/usr/bin/env python3
"""Preview or apply an incremental AI documentation installation from this skill."""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import sys


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ValueError(f"无法载入工具：{path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def public_plan(result: dict) -> dict:
    return {key: value for key, value in result.items() if not key.startswith("_")}


def summarize(output: dict, plan_file: Path | None) -> dict:
    result = {key: value for key, value in output.items() if key not in {"actions", "preserved"}}
    actions = output.get("actions", [])
    result["action_counts"] = {operation: sum(item["operation"] == operation for item in actions)
                               for operation in ("create", "update")}
    groups = {}
    for item in actions:
        if item["operation"] == "create":
            parts = Path(item["path"]).parts
            group = "/".join(parts[:2]) if len(parts) > 2 else item["path"]
            groups[group] = groups.get(group, 0) + 1
    result["created_groups"] = groups
    result["updated_paths"] = [item["path"] for item in actions if item["operation"] == "update"]
    result["preserved_count"] = len(output.get("preserved", []))
    if plan_file:
        result["plan_file"] = str(plan_file.absolute())
    return result


def cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--source", type=Path,
                        default=Path(__file__).resolve().parents[1] / "assets/templates")
    parser.add_argument("--mode", choices=("auto", "init", "adopt", "upgrade"), default="auto")
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--apply", action="store_true")
    action.add_argument("--dry-run", action="store_true")
    action.add_argument("--scan", action="store_true")
    parser.add_argument("--plan-file", type=Path,
                        help="预览时保存计划；--apply 时读取并验证同一计划")
    parser.add_argument("--overview-title")
    parser.add_argument("--overview-summary")
    parser.add_argument("--summary", action="store_true",
                        help="输出计数、更新路径和完整冲突；完整变更仍保存在 --plan-file 中")
    args = parser.parse_args(argv)
    try:
        source = args.source.resolve()
        # Preserve the supplied path so the installer can reject symlink ancestors.
        target = args.target.absolute()
        installer_path = source / "docs/_tools/init_docs.py"
        if not installer_path.is_file():
            raise ValueError("Skill 缺少打包模板；维护者先运行 scripts/build_assets.py")
        installer = load_module(installer_path, "ai_docs_skill_installer")
        if args.scan:
            if args.plan_file or args.overview_title or args.overview_summary:
                raise ValueError("--scan 仅盘点，不能同时生成安装计划或总纲")
            print(json.dumps(installer.scan(target), ensure_ascii=False, indent=2))
            return 0
        if args.apply and args.plan_file:
            plan = json.loads(args.plan_file.read_text(encoding="utf-8"))
            if Path(plan["target"]).resolve() != target.resolve():
                raise ValueError("计划目标与 --target 不一致")
            if args.overview_title or args.overview_summary:
                raise ValueError("应用已保存计划时不能另改总纲参数；请重新生成计划")
        else:
            plan = installer.plan_install(source, target, mode=args.mode,
                                          overview_title=args.overview_title,
                                          overview_summary=args.overview_summary)
            if args.plan_file:
                if args.plan_file.resolve().is_relative_to(target):
                    raise ValueError("安装计划属于临时工具数据，请保存在目标仓库之外")
                # Never replace an existing review artifact silently.
                with args.plan_file.open("x", encoding="utf-8") as stream:
                    json.dump(plan, stream, ensure_ascii=False, indent=2)
                    stream.write("\n")
        result = installer.bootstrap(source, target, mode=args.mode,
                                     dry_run=not args.apply, plan=plan)
        output = public_plan(result)
        if args.apply and result.get("applied") and (target / "docs/_system/collections.json").is_file():
            checker = load_module(source / "docs/_tools/docctl.py", "ai_docs_skill_checker")
            try:
                structure = checker.validate(target)
                strict = checker.validate(target, strict=True)
                output["validation"] = {"structure": structure, "strict": strict}
                stages = output.setdefault("stages", {})
                stages["structure_valid"] = structure["ok"]
                stages["strict_ready"] = strict["ok"]
                if not structure["ok"]:
                    output["status"] = "needs_review"
            except (ValueError, OSError, KeyError, TypeError) as exc:
                output["validation"] = {"error": str(exc)}
                output["status"] = "needs_review"
        print(json.dumps(summarize(output, args.plan_file) if args.summary else output,
                         ensure_ascii=False, indent=2))
        return 1 if output.get("status") in {"blocked", "partial", "needs_review"} or output.get("conflicts") else 0
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False, indent=2), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(cli())
