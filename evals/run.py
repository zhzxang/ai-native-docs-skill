#!/usr/bin/env python3
"""Local, standard-library scenario runner for the four AI Native Docs skills."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import fnmatch
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import time
import uuid

from graders import grade_case, snapshot_files, validate_assertions

EVAL_ROOT = Path(__file__).resolve().parent
REPO_ROOT = EVAL_ROOT.parent
SKILL_NAMES = ("ai-docs-init", "ai-docs-sync", "ai-docs-migrate", "ai-docs-check")
IGNORED = {".git", "node_modules", "dist", "build", "coverage", ".venv", "venv",
           "__pycache__", ".cache", ".next", ".DS_Store", ".pytest_cache"}
ID_PATTERN = re.compile(r"[a-z0-9][a-z0-9_-]*\Z")


class InfrastructureError(RuntimeError):
    pass


class TargetExecutionError(RuntimeError):
    pass


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def valid_id(value) -> bool:
    return isinstance(value, str) and bool(ID_PATTERN.fullmatch(value))


def relative_path(root: Path, value: str) -> Path:
    if not isinstance(value, str) or not value or Path(value).is_absolute() or ".." in Path(value).parts:
        raise ValueError(f"Expected a relative path without '..': {value!r}")
    target = root / value
    if not target.resolve().is_relative_to(root.resolve()):
        raise ValueError(f"Path escapes the project: {value!r}")
    return target


def ignored_name(name: str) -> bool:
    return name in IGNORED or name.endswith((".pyc", ".pyo")) or name == ".env" or name.startswith(".env.")


def copy_tree(source: Path, destination: Path) -> None:
    """Copy a frozen input, omitting credentials, dependencies and generated files."""
    if not source.is_dir():
        raise ValueError(f"Project directory does not exist: {source}")
    source = source.resolve()
    if destination.resolve().is_relative_to(source):
        raise ValueError("Copy destination must be outside the source project")
    for directory, dirs, files in os.walk(source, followlinks=False):
        dirs[:] = [name for name in dirs if not ignored_name(name)]
        for name in dirs + [name for name in files if not ignored_name(name)]:
            path = Path(directory) / name
            if path.is_symlink():
                raise ValueError(f"Snapshot does not support symbolic links: {path}")
    shutil.copytree(source, destination,
                    ignore=lambda directory, names: [name for name in names if ignored_name(name)])


def load_manifests(folder: Path) -> dict[str, dict]:
    manifests = {}
    if not folder.is_dir():
        raise ValueError(f"Missing manifest directory: {folder}")
    for path in sorted(folder.rglob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            raise ValueError(f"Invalid manifest {path}: {error}") from error
        if not isinstance(data, dict) or type(data.get("version")) is not int or data["version"] != 1 or not valid_id(data.get("id")):
            raise ValueError(f"Manifest requires version=1 and a safe lowercase id: {path}")
        if data["id"] in manifests:
            raise ValueError(f"Duplicate id {data['id']!r}: {path}")
        data["_manifest"] = str(path)
        manifests[data["id"]] = data
    return manifests


def validate_actions(actions: list, label: str) -> None:
    if not isinstance(actions, list):
        raise ValueError(f"{label} must be an array")
    for action in actions:
        if not isinstance(action, dict) or action.get("action") not in {"init", "sync", "migrate", "write", "append", "replace", "node_dependencies"}:
            raise ValueError(f"Unknown action in {label}: {action!r}")
        kind = action["action"]
        if kind == "node_dependencies":
            continue
        if kind == "replace":
            relative_path(Path("/tmp/eval-validation"), action.get("path"))
            if not isinstance(action.get("old"), str) or not action["old"] or not isinstance(action.get("new"), str):
                raise ValueError("replace requires a nonempty old string and a new string")
            if action["old"] == action["new"]:
                raise ValueError("replace old and new must differ")
            continue
        if kind in {"write", "append"}:
            relative_path(Path("/tmp/eval-validation"), action.get("path"))
            if not isinstance(action.get("content"), str):
                raise ValueError(f"{kind} requires string content")
        else:
            relative_path(Path("/tmp/eval-validation"), action.get("plan", kind + ".json"))
            if "preview" in action and not isinstance(action["preview"], bool):
                raise ValueError("preview must be a boolean")
            if kind == "migrate" and not isinstance(action.get("mapping"), dict):
                raise ValueError("migrate requires an explicit mapping object")


def selected_cases(args) -> tuple[list[dict], dict[str, dict]]:
    cases = load_manifests(args.cases_dir)
    projects = load_manifests(args.projects_dir)
    patterns = args.case or ["*"]
    for pattern in patterns:
        if not any(fnmatch.fnmatchcase(case_id, pattern) for case_id in cases):
            raise ValueError(f"No case matches {pattern!r}")
    selected = []
    for case_id, case in cases.items():
        if not any(fnmatch.fnmatchcase(case_id, pattern) for pattern in patterns):
            continue
        tags = case.get("tags", [])
        if not isinstance(tags, list) or any(not isinstance(tag, str) or not tag for tag in tags):
            raise ValueError(f"Case {case_id} tags must be an array of nonempty strings")
        if args.tag and not all(tag in tags for tag in args.tag):
            continue
        if not valid_id(case.get("project")) or case["project"] not in projects:
            raise ValueError(f"Unknown project for {case_id}: {case.get('project')!r}")
        engines = case.get("engines", ["codex", "tools"])
        if not isinstance(engines, list) or not engines or any(engine not in ("codex", "tools") for engine in engines):
            raise ValueError(f"Case {case_id} engines must be a nonempty array of codex/tools")
        if not isinstance(case.get("prompt"), str) or not case["prompt"].strip():
            raise ValueError(f"Case {case_id} requires a nonempty prompt")
        if not isinstance(case.get("assertions"), list) or not case["assertions"]:
            raise ValueError(f"Case {case_id} requires independent assertions")
        validate_assertions(case["assertions"])
        validate_actions(case.get("setup", []), case_id + ".setup")
        validate_actions(case.get("steps", []), case_id + ".steps")
        project = projects[case["project"]]
        source = project.get("source")
        if not isinstance(source, str) or not source:
            raise ValueError(f"Project {project['id']} requires a source directory")
        project["_source"] = str((EVAL_ROOT / source).resolve())
        if not Path(project["_source"]).is_dir():
            raise ValueError(f"Missing project source: {project['_source']}")
        selected.append(case)
    if not selected:
        raise ValueError("No cases selected")
    return selected, projects


def run_process(argv: list[str], cwd: Path, stdout: Path, stderr: Path,
                timeout: float) -> dict:
    started = time.monotonic()
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    try:
        with stdout.open("w", encoding="utf-8") as out, stderr.open("w", encoding="utf-8") as err:
            process = subprocess.Popen(argv, cwd=cwd, env=env, stdin=subprocess.DEVNULL, stdout=out, stderr=err,
                                       start_new_session=True)
            try:
                returncode = process.wait(timeout=timeout)
            except (subprocess.TimeoutExpired, KeyboardInterrupt) as error:
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    pass
                # The leader may already have exited while a child ignores SIGTERM.
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait()
                if isinstance(error, KeyboardInterrupt):
                    raise
                raise InfrastructureError(f"Command timed out after {timeout:g}s; see {stderr}")
    except OSError as error:
        raise InfrastructureError(f"Could not start command: {error}") from error
    return {"argv": argv, "exit_code": returncode,
            "duration_seconds": round(time.monotonic() - started, 3),
            "stdout": str(stdout), "stderr": str(stderr)}


def apply_actions(actions: list, project: Path, plans: Path, skills: Path,
                  artifacts: Path, prefix: str, timeout: float, *, dependencies: Path | None = None) -> list[dict]:
    records = []
    for index, action in enumerate(actions, 1):
        kind = action["action"]
        if kind == "node_dependencies":
            if dependencies is None or not dependencies.is_dir():
                raise InfrastructureError("Node dependencies were not prepared for this scenario")
            destination = project / "node_modules"
            if destination.exists():
                raise InfrastructureError("Node dependencies already exist in this attempt")
            copy_node_modules(dependencies, destination)
            records.append({"action": kind, "source": str(dependencies)})
            continue
        if kind == "replace":
            path = relative_path(project, action["path"])
            text = path.read_text(encoding="utf-8")
            if text.count(action["old"]) != 1:
                raise InfrastructureError(f"replace requires exactly one match in {action['path']}")
            path.write_text(text.replace(action["old"], action["new"], 1), encoding="utf-8")
            records.append({"action": kind, "path": action["path"]})
            continue
        if kind in {"write", "append"}:
            path = relative_path(project, action["path"])
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a" if kind == "append" else "w", encoding="utf-8") as handle:
                handle.write(action["content"])
            records.append({"action": kind, "path": action["path"]})
            continue
        script = {"init": "bootstrap.py", "sync": "sync.py", "migrate": "migrate.py"}[kind]
        plan = relative_path(plans, action.get("plan", kind + ".json"))
        plan.parent.mkdir(parents=True, exist_ok=True)
        base = [sys.executable, str(skills / f"ai-docs-{kind}" / "scripts" / script),
                "--target", str(project)]
        preview = base + ["--plan-file", str(plan)]
        if kind == "migrate":
            mapping = plan.with_name(plan.name + ".mapping.json")
            write_json(mapping, action["mapping"])
            preview += ["--mapping", str(mapping)]
        for stage, command in [("preview", preview)] + ([] if action.get("preview") else [
                ("apply", base + ["--apply", "--plan-file", str(plan)])]):
            label = f"{prefix}-{index:02d}-{kind}-{stage}"
            record = run_process(command, project, artifacts / (label + ".stdout"),
                                 artifacts / (label + ".stderr"), timeout)
            records.append(record)
            if record["exit_code"] != 0:
                write_json(artifacts / (prefix + "-commands.json"), records)
                failure = InfrastructureError if prefix == "setup" else TargetExecutionError
                raise failure(f"{prefix} {kind} {stage} exited {record['exit_code']}; see {record['stderr']}")
    write_json(artifacts / (prefix + "-commands.json"), records)
    return records


def copy_node_modules(source: Path, destination: Path) -> None:
    """Copy dependencies with relative links that remain inside each fresh tree."""
    root = source.resolve()
    for directory, dirs, files in os.walk(root, followlinks=False):
        for name in dirs + files:
            path = Path(directory) / name
            if path.is_symlink():
                if os.path.isabs(os.readlink(path)):
                    raise InfrastructureError(f"Absolute dependency symlink cannot be isolated: {path}")
                if not path.resolve().is_relative_to(root):
                    raise InfrastructureError(f"Dependency symlink leaves node_modules: {path}")
    shutil.copytree(root, destination, symlinks=True)


def dependency_hashes(modules: Path) -> dict[str, str]:
    """Hash every dependency file and link, including nested node_modules."""
    if not modules.is_dir():
        raise InfrastructureError("Frozen Node dependency directory is missing")
    root = modules.resolve()
    hashes = {}
    for directory, dirs, files in os.walk(root, followlinks=False):
        parent = Path(directory)
        entries = list(files)
        for name in dirs[:]:
            if (parent / name).is_symlink():
                entries.append(name)
                dirs.remove(name)
        for name in sorted(entries):
            path = parent / name
            digest = hashlib.sha256()
            if path.is_symlink():
                if os.path.isabs(os.readlink(path)) or not path.resolve().is_relative_to(root):
                    raise InfrastructureError(f"Dependency link cannot be isolated: {path}")
                digest.update(b"symlink:" + os.fsencode(os.readlink(path)))
            elif path.is_file():
                with path.open("rb") as handle:
                    for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                        digest.update(chunk)
            else:
                raise InfrastructureError(f"Unsupported dependency file: {path}")
            hashes[path.relative_to(root).as_posix()] = digest.hexdigest()
    return hashes


def verify_dependency_snapshot(modules: Path) -> None:
    manifest = modules.parent / "hashes.json"
    if not manifest.is_file() or dependency_hashes(modules) != json.loads(manifest.read_text(encoding="utf-8")):
        raise InfrastructureError("Frozen Node dependencies changed; cannot evaluate reliably")


def installed_dependencies_match_lock(source: Path, frozen_project: Path) -> bool:
    """Check npm's installed-package descriptors before copying an existing tree."""
    try:
        locked = json.loads((frozen_project / "package-lock.json").read_text(encoding="utf-8"))["packages"]
        installed = json.loads((source / "node_modules/.package-lock.json").read_text(encoding="utf-8"))["packages"]
        if not isinstance(locked, dict) or not isinstance(installed, dict) or not installed:
            return False
        package_root = locked.get("", {})
        if not isinstance(package_root, dict):
            return False
        required = {**package_root.get("dependencies", {}),
                    **package_root.get("devDependencies", {})}
        if any("node_modules/" + name not in installed for name in required):
            return False
        for relative, package in installed.items():
            if not isinstance(package, dict) or not isinstance(locked.get(relative), dict):
                return False
            if any(package.get(field) != locked[relative].get(field) for field in ("version", "resolved", "integrity")):
                return False
            path = relative_path(source, relative)
            if not relative.startswith("node_modules/") or not path.is_dir():
                return False
        return True
    except (ValueError, KeyError, TypeError, OSError):
        return False


def prepare_node_dependencies(source: Path, frozen_project: Path, destination: Path,
                              artifacts: Path, timeout: float) -> Path:
    if destination.is_dir():
        verify_dependency_snapshot(destination)
        return destination
    if not (frozen_project / "package-lock.json").is_file():
        raise InfrastructureError("node_dependencies requires package-lock.json")
    modules = source / "node_modules"
    copied = modules.is_dir() and installed_dependencies_match_lock(source, frozen_project)
    if not copied:
        npm = shutil.which("npm")
        if npm is None:
            raise InfrastructureError("npm is required to prepare locked Node dependencies")
        modules = frozen_project / "node_modules"
        command = [npm, "ci", "--ignore-scripts", "--no-audit", "--no-fund"]
        record = run_process(command, frozen_project, artifacts / "dependencies.stdout",
                             artifacts / "dependencies.stderr", timeout)
        write_json(artifacts / "dependencies-command.json", record)
        if record["exit_code"] != 0:
            raise InfrastructureError("npm ci failed during dependency preparation; see dependencies.stderr")
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        copy_node_modules(modules, destination)
    except (OSError, RuntimeError):
        if destination.exists():
            shutil.rmtree(destination)
        raise
    write_json(destination.parent / "provenance.json", {
        "package_lock_sha256": hashlib.sha256((frozen_project / "package-lock.json").read_bytes()).hexdigest(),
        "installed_lock_sha256": hashlib.sha256((modules / ".package-lock.json").read_bytes()).hexdigest()
        if (modules / ".package-lock.json").is_file() else None,
        "source": str(modules), "method": "copy-checked-npm-lock" if copied else "npm-ci",
    })
    write_json(destination.parent / "hashes.json", dependency_hashes(destination))
    return destination


def render_prompt(case: dict, project: Path, plans: Path, skills: Path) -> str:
    text = case["prompt"]
    for name, value in {"project": project, "plans": plans, "skills": skills}.items():
        text = text.replace("{" + name + "}", str(value))
    return (
        "你正在一个独立的本地项目副本中执行用户任务。\n"
        f"项目根目录：{project}\n"
        f"本次待测的四个 Skill 位于：{skills}\n"
        "按任务需要读取该目录中对应的 SKILL.md；公共资源来自同目录的 ai-docs-check。\n"
        f"计划、映射和执行证据写入项目之外的可写目录：{plans}\n"
        "按下面请求中授权的范围完成操作；仅预览请求不得应用。不要修改 Skill 资源。\n"
        "最终说明完成的操作、产出与未核验项，真实执行结果才构成核验证据。\n\n"
        "用户请求：\n" + text + "\n"
    )


def codex_command(args, project: Path, plans: Path, artifacts: Path, prompt: str) -> list[str]:
    argv = [args.codex_bin, "exec", "-C", str(project), "--add-dir", str(plans),
            "--sandbox", "workspace-write", "--skip-git-repo-check", "--json", "--ephemeral",
            "-o", str(artifacts / "final.md")]
    if args.model:
        argv += ["--model", args.model]
    if args.ignore_user_config:
        argv.append("--ignore-user-config")
    argv.append(prompt)
    return argv


def parse_codex_result(execution: dict, artifacts: Path) -> dict:
    events = []
    for number, line in enumerate((artifacts / "events.jsonl").read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except ValueError as error:
            raise InfrastructureError(f"Invalid CLI JSONL at line {number}") from error
        if not isinstance(event, dict):
            raise InfrastructureError(f"Invalid CLI event at line {number}")
        events.append(event)
    completed = [event for event in events if event.get("type") == "turn.completed"]
    terminal_errors = [event for event in events if event.get("type") in {"turn.failed", "error"}]
    stderr = (artifacts / "stderr.log").read_text(encoding="utf-8", errors="replace")
    diagnostics = (json.dumps(terminal_errors, ensure_ascii=False) + "\n" + stderr).lower()
    infra_markers = ("unauthorized", "authentication", "not logged", "rate limit", "quota", "usage limit",
                     "insufficient", "connection", "network", "timed out", "stream disconnected",
                     "failed to connect", "api key", "sandbox", "operation not permitted")
    failed = execution["exit_code"] != 0 or not completed or any(
        event.get("type") == "turn.failed" for event in events)
    if failed and (not events or any(marker in diagnostics for marker in infra_markers)):
        raise InfrastructureError(f"CLI could not complete a run (exit {execution['exit_code']}); see {artifacts / 'stderr.log'}")
    if not completed and not terminal_errors:
        raise InfrastructureError("CLI emitted no terminal event")
    usage = completed[-1].get("usage", {}) if completed else {}
    return {"passed": not failed, "usage": usage, "event_count": len(events)}


def make_diff(before: dict, after: dict) -> dict:
    return {"added": sorted(after.keys() - before.keys()), "deleted": sorted(before.keys() - after.keys()),
            "modified": sorted(key for key in before.keys() & after.keys() if before[key] != after[key])}


def grade_attempt(case: dict, attempt: Path, skills: Path, grader=grade_case, *, verifiers: Path | None = None) -> dict:
    project, artifacts = attempt / "project", attempt / "artifacts"
    baseline = json.loads((artifacts / "baseline.json").read_text(encoding="utf-8"))
    if verifiers is None:
        checks = grader(case, project, baseline, artifacts, skills)
    else:
        checks = grader(case, project, baseline, artifacts, skills, verifiers=verifiers)
    try:
        diff = make_diff(baseline, snapshot_files(project))
    except ValueError as error:
        checks.append({"id": "safe-project-files", "kind": "files", "passed": False, "detail": str(error)})
        diff = {"error": str(error)}
    write_json(artifacts / "diff.json", diff)
    return {"checks": checks, "diff": diff}


def report_markdown(report: dict) -> str:
    lines = ["# Local scenario evaluation", "", f"Engine: `{report['engine']}`",
             f"Model: `{report.get('model') or 'CLI default'}`", "",
             "Tools mode validates scripts and graders; it does not evaluate Codex behavior." if report["engine"] == "tools" else "Each attempt uses a fresh project copy and Codex session.",
             "", "| Case | Attempt | Status | Checks passed | Seconds |",
             "| --- | --- | --- | --- | --- |"]
    for row in report["attempts"]:
        checks = row.get("checks", [])
        lines.append(f"| {row['case']} | {row['attempt']} | {row['status']} | "
                     f"{sum(check['passed'] for check in checks)}/{len(checks)} | {row['duration_seconds']} |")
    lines += ["", "## Stability", "", "| Case | Passes / attempts | Infrastructure errors |",
              "| --- | --- | --- |"]
    for case_id, counts in report["summary"]["cases"].items():
        lines.append(f"| {case_id} | {counts['passed']}/{counts['total']} | {counts['infrastructure_error']} |")
    for row in report["attempts"]:
        failures = [check for check in row.get("checks", []) if not check["passed"]]
        if failures or row.get("error"):
            lines += ["", f"## {row['case']} / attempt {row['attempt']}", ""]
            if row.get("error"):
                lines.append(row["error"])
            lines += [f"- {check['id']}: {check['detail']}" for check in failures]
    return "\n".join(lines) + "\n"


def finalize_report(report: dict, run_dir: Path, *, announce=True) -> int:
    summary = {"passed": 0, "failed": 0, "infrastructure_error": 0, "cases": {}}
    for row in report["attempts"]:
        summary[row["status"]] += 1
        counts = summary["cases"].setdefault(row["case"], {
            "total": 0, "passed": 0, "failed": 0, "infrastructure_error": 0})
        counts["total"] += 1
        counts[row["status"]] += 1
    report["summary"] = summary
    write_json(run_dir / "report.json", report)
    (run_dir / "report.md").write_text(report_markdown(report), encoding="utf-8")
    if announce:
        print(f"Report: {run_dir / 'report.md'}", flush=True)
        print(f"Passed {summary['passed']}; failed {summary['failed']}; infrastructure errors {summary['infrastructure_error']}", flush=True)
    return 2 if summary["infrastructure_error"] else (1 if summary["failed"] else 0)


def run_suite(args) -> int:
    cases, projects = selected_cases(args)
    unsupported = [case for case in cases if args.engine not in case.get("engines", ["codex", "tools"])]
    if unsupported:
        print(f"Skipping cases unavailable for {args.engine}: " + ", ".join(case['id'] for case in unsupported))
        cases = [case for case in cases if case not in unsupported]
    if not cases:
        raise ValueError(f"No selected case supports the {args.engine} engine")
    if args.engine == "tools" and any(not case.get("steps") for case in cases):
        raise ValueError("Tools mode requires steps on every selected case")
    if args.dry_run:
        print(json.dumps({"engine": args.engine, "model": args.model or "CLI default",
                          "repeat": args.repeat, "timeout": args.timeout,
                          "cases": [{"id": case["id"], "project": case["project"],
                                     "source": projects[case["project"]]["_source"],
                                     "assertions": len(case["assertions"])} for case in cases]},
                         ensure_ascii=False, indent=2))
        return 0
    cli_version = None
    if args.engine == "codex":
        try:
            probe = subprocess.run([args.codex_bin, "--version"], text=True, capture_output=True, timeout=15)
        except (OSError, subprocess.TimeoutExpired) as error:
            raise InfrastructureError(f"Codex CLI is unavailable: {error}") from error
        if probe.returncode:
            raise InfrastructureError("Could not read Codex CLI version")
        cli_version = probe.stdout.strip()
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    run_dir = args.results_dir.resolve() / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    skills = run_dir / "inputs" / "skills"
    for name in SKILL_NAMES:
        copy_tree(REPO_ROOT / "skills" / name, skills / name)
    frozen_cases = [{key: value for key, value in case.items() if not key.startswith("_")} for case in cases]
    write_json(run_dir / "inputs" / "cases.json", frozen_cases)
    skill_hashes = snapshot_files(skills)
    write_json(run_dir / "inputs" / "skill-hashes.json", skill_hashes)
    harness_hashes = {}
    for name in ("run.py", "graders.py"):
        content = (EVAL_ROOT / name).read_bytes()
        (run_dir / "inputs" / name).write_bytes(content)
        harness_hashes[name] = hashlib.sha256(content).hexdigest()
    write_json(run_dir / "inputs" / "harness-hashes.json", harness_hashes)
    verifiers = run_dir / "inputs" / "verifiers"
    if (EVAL_ROOT / "verifiers").is_dir():
        copy_tree(EVAL_ROOT / "verifiers", verifiers)
    else:
        verifiers.mkdir()
    verifier_hashes = snapshot_files(verifiers)
    write_json(run_dir / "inputs" / "verifier-hashes.json", verifier_hashes)
    frozen_projects = {}
    project_hashes = {}
    for project_id in sorted({case["project"] for case in cases}):
        destination = run_dir / "inputs" / "projects" / project_id
        copy_tree(Path(projects[project_id]["_source"]), destination)
        frozen_projects[project_id] = destination
        project_hashes[project_id] = snapshot_files(destination)
    write_json(run_dir / "inputs" / "project-hashes.json", project_hashes)
    report = {"version": 1, "run_id": run_id, "engine": args.engine, "model": args.model,
              "cli_version": cli_version, "python_version": sys.version.split()[0],
              "ignore_user_config": args.ignore_user_config, "timeout_seconds": args.timeout,
              "created_at": datetime.now(timezone.utc).isoformat(), "attempts": []}
    write_json(run_dir / "metadata.json", {key: value for key, value in report.items() if key != "attempts"})
    print(f"Run: {run_dir}", flush=True)
    for case in cases:
        for number in range(1, args.repeat + 1):
            started = time.monotonic()
            attempt = run_dir / case["id"] / f"attempt-{number}"
            project, artifacts, plans = attempt / "project", attempt / "artifacts", attempt / "plans"
            trial_skills = attempt / "skills"
            artifacts.mkdir(parents=True)
            plans.mkdir()
            row = {"case": case["id"], "attempt": number, "status": "infrastructure_error",
                   "path": str(attempt), "checks": []}
            print(f"[{case['id']} {number}/{args.repeat}] {args.engine}", flush=True)
            try:
                copy_tree(frozen_projects[case["project"]], project)
                copy_tree(skills, trial_skills)
                dependency_root = None
                actions = case.get("setup", []) + case.get("steps", [])
                if any(action["action"] == "node_dependencies" for action in actions):
                    dependency_root = prepare_node_dependencies(
                        Path(projects[case["project"]]["_source"]), frozen_projects[case["project"]],
                        run_dir / "inputs/dependencies" / case["project"] / "node_modules", artifacts, args.timeout)
                apply_actions(case.get("setup", []), project, plans, trial_skills, artifacts, "setup", args.timeout,
                              dependencies=dependency_root)
                write_json(artifacts / "baseline.json", snapshot_files(project))
                # Keep an input copy for inspection; hashes remain the grading authority.
                copy_tree(project, attempt / "before")
                prompt = render_prompt(case, project, plans, trial_skills)
                (artifacts / "prompt.txt").write_text(prompt, encoding="utf-8")
                if args.engine == "tools":
                    apply_actions(case["steps"], project, plans, trial_skills, artifacts, "tools", args.timeout,
                                  dependencies=dependency_root)
                    target = {"passed": True}
                else:
                    execution = run_process(codex_command(args, project, plans, artifacts, prompt), project,
                                            artifacts / "events.jsonl", artifacts / "stderr.log", args.timeout)
                    write_json(artifacts / "execution.json", execution)
                    target = parse_codex_result(execution, artifacts)
                    row["usage"] = target["usage"]
                    row["event_count"] = target["event_count"]
                row["target_result"] = target
                if dependency_root is not None:
                    verify_dependency_snapshot(dependency_root)
                if snapshot_files(skills) != skill_hashes:
                    raise InfrastructureError("Frozen controller skill resources changed; grading is unavailable")
                if snapshot_files(verifiers) != verifier_hashes:
                    raise InfrastructureError("Frozen external verifiers changed; grading is unavailable")
                try:
                    resources_unchanged = snapshot_files(trial_skills) == skill_hashes
                except ValueError:
                    resources_unchanged = False
                graded = grade_attempt(case, attempt, skills, verifiers=verifiers)
                row.update(graded)
                row["checks"].insert(0, {"id": "target-completed", "kind": "runtime",
                                         "passed": target["passed"], "detail": "Target runtime completed" if target["passed"] else "Target runtime failed"})
                row["checks"].append({"id": "skills-unchanged", "kind": "runtime",
                                      "passed": resources_unchanged, "detail": "Frozen skill resources must remain unchanged"})
                row["status"] = "passed" if all(check["passed"] for check in row["checks"]) else "failed"
            except TargetExecutionError as error:
                row["error"] = str(error)
                row["status"] = "failed"
            except (InfrastructureError, RuntimeError, ValueError, OSError) as error:
                row["error"] = str(error)
                row["status"] = "infrastructure_error"
            # Also preserve state changes from timed-out or otherwise failed targets.
            if (artifacts / "baseline.json").is_file() and "diff" not in row:
                try:
                    baseline = json.loads((artifacts / "baseline.json").read_text(encoding="utf-8"))
                    row["diff"] = make_diff(baseline, snapshot_files(project))
                    write_json(artifacts / "diff.json", row["diff"])
                except (ValueError, OSError):
                    pass
            row["duration_seconds"] = round(time.monotonic() - started, 3)
            report["attempts"].append(row)
            write_json(artifacts / "result.json", row)
            print(f"  {row['status']} ({row['duration_seconds']}s)", flush=True)
            # Preserve a useful report even if a subsequent attempt is interrupted.
            finalize_report(report, run_dir, announce=False)
            if snapshot_files(skills) != skill_hashes or snapshot_files(verifiers) != verifier_hashes:
                print("Stopping: immutable controller inputs changed", file=sys.stderr)
                return finalize_report(report, run_dir)
    return finalize_report(report, run_dir)


def grade_saved(args) -> int:
    run_dir = args.run_dir.resolve()
    report = json.loads((run_dir / "report.json").read_text(encoding="utf-8"))
    cases = {case["id"]: case for case in json.loads((run_dir / "inputs/cases.json").read_text(encoding="utf-8"))}
    skills = run_dir / "inputs/skills"
    hashes = json.loads((run_dir / "inputs/skill-hashes.json").read_text(encoding="utf-8"))
    if snapshot_files(skills) != hashes:
        raise InfrastructureError("Frozen skills changed; cannot regrade reliably")
    verifiers = run_dir / "inputs/verifiers"
    verifier_hashes_file = run_dir / "inputs/verifier-hashes.json"
    if verifier_hashes_file.is_file():
        if snapshot_files(verifiers) != json.loads(verifier_hashes_file.read_text(encoding="utf-8")):
            raise InfrastructureError("Frozen external verifiers changed; cannot regrade reliably")
    for manifest in (run_dir / "inputs/dependencies").glob("*/hashes.json"):
        verify_dependency_snapshot(manifest.parent / "node_modules")
    harness_hashes = json.loads((run_dir / "inputs/harness-hashes.json").read_text(encoding="utf-8"))
    saved_grader = run_dir / "inputs/graders.py"
    if hashlib.sha256(saved_grader.read_bytes()).hexdigest() != harness_hashes["graders.py"]:
        raise InfrastructureError("Frozen grader changed; cannot regrade reliably")
    spec = importlib.util.spec_from_file_location("_saved_eval_graders", saved_grader)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for row in report["attempts"]:
        if row["status"] == "infrastructure_error" and "target_result" not in row:
            continue
        attempt = run_dir / row["case"] / f"attempt-{row['attempt']}"
        try:
            target = row.get("target_result", {})
            try:
                skills_unchanged = module.snapshot_files(attempt / "skills") == hashes
            except ValueError:
                skills_unchanged = False
            runtime = [{"id": "target-completed", "kind": "runtime", "passed": target.get("passed", False),
                        "detail": "Saved target runtime completion"},
                       {"id": "skills-unchanged", "kind": "runtime", "passed": skills_unchanged,
                        "detail": "Trial skill resources must remain unchanged"}]
            if verifier_hashes_file.is_file():
                row.update(grade_attempt(cases[row["case"]], attempt, skills, module.grade_case, verifiers=verifiers))
            else:
                row.update(grade_attempt(cases[row["case"]], attempt, skills, module.grade_case))
            row["checks"] = runtime + row["checks"]
            row["status"] = "passed" if all(check["passed"] for check in row["checks"]) else "failed"
            row.pop("error", None)
        except (RuntimeError, ValueError, OSError) as error:
            row["status"] = "infrastructure_error"
            row["error"] = str(error)
        write_json(attempt / "artifacts/result.json", row)
    return finalize_report(report, run_dir)


def import_project(args) -> int:
    if not valid_id(args.id):
        raise ValueError("Project id must contain lowercase letters, digits, '-' or '_'")
    existing = load_manifests(EVAL_ROOT / "projects")
    destination = EVAL_ROOT / "local-projects" / args.id
    manifest = EVAL_ROOT / "projects/local" / (args.id + ".json")
    if args.id in existing or destination.exists() or manifest.exists():
        raise ValueError(f"Project {args.id!r} already exists; choose a new id")
    copy_tree(args.source.resolve(), destination)
    write_json(manifest, {"version": 1, "id": args.id, "description": args.description,
                          "source": destination.relative_to(EVAL_ROOT).as_posix()})
    print(f"Snapshot: {destination}")
    print(f"Manifest: {manifest}")
    print("Add a case referencing this project id; review its facts and assertions before running.")
    return 0


def positive_int(value: str) -> int:
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return number


def positive_float(value: str) -> float:
    number = float(value)
    if number <= 0 or not number < float("inf"):
        raise argparse.ArgumentTypeError("must be a finite positive number")
    return number


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    commands = result.add_subparsers(dest="command", required=True)
    for name in ("list", "run"):
        command = commands.add_parser(name)
        command.add_argument("--cases-dir", type=Path, default=EVAL_ROOT / "cases")
        command.add_argument("--projects-dir", type=Path, default=EVAL_ROOT / "projects")
        command.add_argument("--case", action="append", help="Case id or quoted glob; repeatable")
        command.add_argument("--tag", action="append", help="Require this tag; repeatable")
        if name == "list":
            command.add_argument("--json", action="store_true")
        else:
            command.add_argument("--engine", choices=("codex", "tools"), default="codex")
            command.add_argument("--model", help="Omit to use the current CLI default")
            command.add_argument("--codex-bin", default="codex")
            command.add_argument("--ignore-user-config", action="store_true")
            command.add_argument("--repeat", type=positive_int, default=1)
            command.add_argument("--timeout", type=positive_float, default=600)
            command.add_argument("--results-dir", type=Path, default=EVAL_ROOT / "results")
            command.add_argument("--dry-run", action="store_true", help="Validate and list inputs without invoking a target or writing files")
    grade = commands.add_parser("grade", help="Regrade saved files without invoking Codex")
    grade.add_argument("run_dir", type=Path)
    imported = commands.add_parser("import-project", help="Freeze a local project snapshot; original stays untouched")
    imported.add_argument("--id", required=True)
    imported.add_argument("--source", type=Path, required=True)
    imported.add_argument("--description", default="Local project snapshot")
    return result


def main(argv=None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "list":
            cases, _ = selected_cases(args)
            if args.json:
                print(json.dumps([{key: value for key, value in case.items() if not key.startswith("_")} for case in cases], ensure_ascii=False, indent=2))
            else:
                for case in cases:
                    print(f"{case['id']:32} {case['project']:20} {case.get('title', '')}")
            return 0
        if args.command == "run":
            return run_suite(args)
        if args.command == "grade":
            return grade_saved(args)
        return import_project(args)
    except (ValueError, OSError, RuntimeError) as error:
        print(f"Evaluation error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
