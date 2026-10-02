"""Independent, deterministic graders for local Codex scenario evaluations.

Expected facts live in case assertions supplied by the runner. Nothing in this
module consumes a target agent's self-reported grade. Python 3.10+, stdlib only.
"""
from __future__ import annotations

import fnmatch
import hashlib
import importlib.util
import json
import os
import re
import shutil
import signal
import subprocess
import sys
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any


IGNORED_DIRS = {".git", "__pycache__", "node_modules", "dist", "build", ".next",
                ".venv", "venv", ".cache", ".pytest_cache", "coverage"}
IGNORED_FILES = {".DS_Store"}
KINDS = {"exists", "absent", "unchanged", "changed", "only_changes", "contains", "not_contains",
         "regex", "json_value", "doc_meta", "doc_check", "record_count", "redirect", "command",
         "external_verifier"}


def _relative(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label}: expected a nonempty relative path")
    path = PurePosixPath(value)
    windows = PureWindowsPath(value)
    if path.is_absolute() or windows.drive or "\\" in value or ".." in path.parts:
        raise ValueError(f"{label}: absolute paths, backslashes, and '..' are forbidden")
    if value in {".", "./"}:
        raise ValueError(f"{label}: specify a project path, not '.'")
    return value


def safe_path(project: Path, relative: str) -> Path:
    """Return a logical project path after rejecting traversal and symlink escape."""
    _relative(relative, "path")
    path = project / relative
    try:
        resolved = path.resolve()
    except (OSError, RuntimeError) as exc:
        raise ValueError(f"path cannot be resolved: {relative}") from exc
    if not resolved.is_relative_to(project.resolve()):
        raise ValueError(f"path escapes project through a symlink: {relative}")
    return path


def _ignored(relative: str) -> bool:
    path = PurePosixPath(relative)
    return (bool(set(path.parts) & IGNORED_DIRS) or path.name in IGNORED_FILES
            or path.suffix in {".pyc", ".pyo"})


def snapshot_files(project: Path) -> dict[str, str]:
    """Hash project files; record internal symlinks without following directories."""
    project = project.resolve()
    if not project.is_dir():
        raise ValueError(f"project does not exist: {project}")
    result: dict[str, str] = {}
    for directory, names, files in os.walk(project, followlinks=False):
        names[:] = sorted(name for name in names if name not in IGNORED_DIRS)
        parent = Path(directory)
        entries = list(files)
        for name in names[:]:
            if (parent / name).is_symlink():
                entries.append(name)
                names.remove(name)
        for name in sorted(entries):
            path = parent / name
            relative = path.relative_to(project).as_posix()
            if _ignored(relative):
                continue
            safe_path(project, relative)
            if path.is_symlink():
                data = b"symlink:" + os.fsencode(os.readlink(path))
            elif path.is_file():
                data = path.read_bytes()
            else:
                raise ValueError(f"unsupported project file: {relative}")
            result[relative] = hashlib.sha256(data).hexdigest()
    return result


def _strings(value: Any, label: str, *, empty: bool = False) -> list[str]:
    if not isinstance(value, list) or (not empty and not value):
        raise ValueError(f"{label}: expected {'a' if not empty else 'an optionally empty'} list")
    if any(not isinstance(item, str) or not item for item in value):
        raise ValueError(f"{label}: expected nonempty strings")
    return value


def _texts(assertion: dict, label: str) -> list[str]:
    if ("text" in assertion) == ("texts" in assertion):
        raise ValueError(f"{label}: specify exactly one of text or texts")
    if "texts" in assertion:
        return _strings(assertion["texts"], f"{label}.texts")
    if not isinstance(assertion["text"], str) or not assertion["text"]:
        raise ValueError(f"{label}.text: expected nonempty text")
    return [assertion["text"]]


def _expected_exit(assertion: dict, label: str) -> int:
    value = assertion.get("expected_exit", 0)
    if type(value) is not int:
        raise ValueError(f"{label}.expected_exit: expected an integer")
    return value


def _argv(assertion: dict, label: str) -> list[str]:
    if ("argv" in assertion) == ("command" in assertion):
        raise ValueError(f"{label}: specify exactly one of argv or command")
    return _strings(assertion.get("argv", assertion.get("command")), label + ".argv")


def _timeout(assertion: dict, label: str) -> float:
    value = assertion.get("timeout", 60)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 < value <= 60:
        raise ValueError(f"{label}.timeout: expected a number between 0 and 60 seconds")
    return value


def _pointer_parts(pointer: Any) -> list[str]:
    if not isinstance(pointer, str) or (pointer and not pointer.startswith("/")):
        raise ValueError("json_value.pointer: expected an RFC 6901 JSON pointer")
    if re.search(r"~(?![01])", pointer):
        raise ValueError("json_value.pointer: '~' must be escaped as '~0' or '~1'")
    return [part.replace("~1", "/").replace("~0", "~") for part in pointer[1:].split("/")] if pointer else []


def validate_assertions(assertions: list) -> None:
    """Reject malformed criteria before preparing or executing a target task."""
    if not isinstance(assertions, list) or not assertions:
        raise ValueError("assertions must be a nonempty list")
    identifiers: set[str] = set()
    for index, assertion in enumerate(assertions, start=1):
        label = f"assertions[{index}]"
        if (not isinstance(assertion, dict) or not isinstance(assertion.get("kind"), str)
                or assertion.get("kind") not in KINDS):
            raise ValueError(f"{label}: unknown or missing assertion kind")
        kind = assertion["kind"]
        identifier = assertion.get("id", f"{kind}-{index}")
        if not isinstance(identifier, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", identifier):
            raise ValueError(f"{label}.id: expected a safe, nonempty identifier")
        if identifier in identifiers:
            raise ValueError(f"{label}.id: duplicate identifier {identifier}")
        identifiers.add(identifier)
        if kind in {"exists", "absent"}:
            for path in _strings(assertion.get("paths"), label + ".paths"):
                _relative(path, label + ".paths")
        if kind in {"unchanged", "changed"}:
            for key in ("paths", "patterns"):
                for path in _strings(assertion.get(key, []), label + "." + key, empty=True):
                    _relative(path, label + "." + key)
        if kind == "changed":
            count = assertion.get("min_count", 1)
            if type(count) is not int or count < 1:
                raise ValueError(f"{label}.min_count: expected a positive integer")
        if kind == "only_changes":
            for pattern in _strings(assertion.get("allowed"), label + ".allowed", empty=True):
                _relative(pattern, label + ".allowed")
        if kind in {"contains", "not_contains", "regex", "json_value", "doc_meta", "redirect"}:
            _relative(assertion.get("path"), label + ".path")
        if kind in {"contains", "not_contains"}:
            _texts(assertion, label)
        if kind == "regex":
            if not isinstance(assertion.get("pattern"), str):
                raise ValueError(f"{label}.pattern: expected a regex string")
            try:
                re.compile(assertion["pattern"])
            except re.error as exc:
                raise ValueError(f"{label}.pattern: invalid regex: {exc}") from exc
        if kind == "json_value":
            _pointer_parts(assertion.get("pointer"))
            if "value" not in assertion:
                raise ValueError(f"{label}: missing expected value")
            try:
                json.dumps(assertion["value"], allow_nan=False)
            except (ValueError, TypeError) as exc:
                raise ValueError(f"{label}.value: expected a JSON value") from exc
        if kind == "doc_meta":
            fields = assertion.get("fields")
            if not isinstance(fields, dict) or not fields or any(not isinstance(key, str) or not key for key in fields):
                raise ValueError(f"{label}.fields: expected a nonempty field map")
            if any(isinstance(value, (dict, list)) for value in fields.values()):
                raise ValueError(f"{label}.fields: doc metadata values must be scalars")
            try:
                json.dumps(fields, allow_nan=False)
            except (ValueError, TypeError) as exc:
                raise ValueError(f"{label}.fields: expected JSON scalar values") from exc
            if "record_id" in assertion and (not isinstance(assertion["record_id"], str) or not assertion["record_id"]):
                raise ValueError(f"{label}.record_id: expected a nonempty ID")
            if "optional_null_fields" in assertion:
                optional = _strings(assertion["optional_null_fields"], label + ".optional_null_fields")
                if len(optional) != len(set(optional)):
                    raise ValueError(f"{label}.optional_null_fields: duplicate field names")
                if any(field in fields and fields[field] is not None for field in optional):
                    raise ValueError(f"{label}.optional_null_fields: cannot also expect a non-null field value")
        if kind == "record_count":
            if not isinstance(assertion.get("type"), str) or not assertion["type"]:
                raise ValueError(f"{label}.type: expected a document type")
            if type(assertion.get("count")) is not int or assertion["count"] < 0:
                raise ValueError(f"{label}.count: expected a nonnegative integer")
        if kind == "redirect" and "target" in assertion:
            if not isinstance(assertion["target"], str) or not assertion["target"]:
                raise ValueError(f"{label}.target: expected a nonempty substring")
        if kind in {"command", "doc_check", "external_verifier"}:
            _expected_exit(assertion, label)
            _timeout(assertion, label)
        if kind == "external_verifier":
            _relative(assertion.get("script"), label + ".script")
            if _expected_exit(assertion, label) not in {0, 1}:
                raise ValueError(f"{label}.expected_exit: external verifiers use only exit 0 or 1")
        if kind == "doc_check" and type(assertion.get("strict", False)) is not bool:
            raise ValueError(f"{label}.strict: expected a boolean")
        if kind == "command":
            _argv(assertion, label)
            if "stdout_contains" in assertion:
                value = assertion["stdout_contains"]
                if isinstance(value, str):
                    if not value:
                        raise ValueError(f"{label}.stdout_contains: expected nonempty text")
                else:
                    _strings(value, label + ".stdout_contains")


def _load_docctl(skills: Path):
    path = skills / "ai-docs-check/assets/templates/docs/_tools/docctl.py"
    if not path.is_file():
        raise RuntimeError(f"bundled docctl is missing: {path}")
    spec = importlib.util.spec_from_file_location("_eval_bundled_docctl", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load bundled docctl: {path}")
    module = importlib.util.module_from_spec(spec)
    previous = sys.dont_write_bytecode
    try:
        sys.dont_write_bytecode = True
        spec.loader.exec_module(module)
    except Exception as exc:
        raise RuntimeError(f"cannot load bundled docctl: {exc}") from exc
    finally:
        sys.dont_write_bytecode = previous
    return module


def _json_equal(actual: Any, expected: Any) -> bool:
    # Python otherwise considers True == 1, hiding incorrect JSON field types.
    return json.dumps(actual, sort_keys=True, ensure_ascii=False) == json.dumps(expected, sort_keys=True, ensure_ascii=False)


def _stop_process_group(process: subprocess.Popen) -> tuple[str, str]:
    """Stop a timed-out grader and its descendants, even after its leader exits."""
    if os.name == "posix":
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    elif process.poll() is None:
        process.terminate()
    try:
        process.communicate(timeout=0.5)
    except subprocess.TimeoutExpired:
        pass
    finally:
        # Do not condition this on process.poll(): a child may ignore SIGTERM
        # and retain the original process group after its leader has exited.
        if os.name == "posix":
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        elif process.poll() is None:
            process.kill()
    try:
        return process.communicate(timeout=2)
    except subprocess.TimeoutExpired as exc:
        # A descendant that created another session may still hold a pipe open.
        # Keep timeout handling bounded and release our pipe descriptors.
        if process.stdout is not None:
            process.stdout.close()
        if process.stderr is not None:
            process.stderr.close()
        process.wait(timeout=2)
        def decode(value):
            return value.decode("utf-8", errors="replace") if isinstance(value, bytes) else value or ""
        return decode(exc.stdout), decode(exc.stderr)


def _write_command_logs(artifacts: Path, identifier: str, stdout: str, stderr: str) -> None:
    artifacts.mkdir(parents=True, exist_ok=True)
    (artifacts / f"{identifier}.stdout.txt").write_text(stdout, encoding="utf-8")
    (artifacts / f"{identifier}.stderr.txt").write_text(stderr, encoding="utf-8")


def _run_command(argv: list[str], project: Path, assertion: dict, artifacts: Path, identifier: str,
                 *, extra_env: dict[str, str] | None = None):
    try:
        process = subprocess.Popen(argv, cwd=project, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   text=True, encoding="utf-8", errors="replace",
                                   env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1", **(extra_env or {})},
                                   start_new_session=os.name == "posix")
    except OSError as exc:
        raise RuntimeError(f"{identifier}: grader command could not complete: {exc}") from exc
    try:
        stdout, stderr = process.communicate(timeout=_timeout(assertion, identifier))
    except subprocess.TimeoutExpired as exc:
        stdout, stderr = _stop_process_group(process)
        _write_command_logs(artifacts, identifier, stdout, stderr)
        raise RuntimeError(f"{identifier}: grader command timed out after {_timeout(assertion, identifier)} seconds; see grader logs") from exc
    except BaseException:
        _stop_process_group(process)
        raise
    _write_command_logs(artifacts, identifier, stdout, stderr)
    return subprocess.CompletedProcess(argv, process.returncode, stdout, stderr)


def _run_external_verifier(assertion: dict, project: Path, artifacts: Path,
                           verifiers: Path, identifier: str, case: dict) -> dict:
    """Execute a trusted, external verifier; target files cannot replace it."""
    verifiers = verifiers.resolve()
    if verifiers.is_relative_to(project):
        raise RuntimeError(f"{identifier}: verifier root must be outside the target project")
    try:
        script = safe_path(verifiers, assertion["script"]).resolve()
    except (OSError, ValueError, RuntimeError) as exc:
        raise RuntimeError(f"{identifier}: invalid external verifier path: {exc}") from exc
    if not script.is_file() or script.is_relative_to(project):
        raise RuntimeError(f"{identifier}: external verifier is missing or inside target project: {script}")
    node = os.environ.get("AI_DOCS_EVAL_NODE") or shutil.which("node")
    if not node:
        raise RuntimeError(f"{identifier}: Node runtime unavailable; set AI_DOCS_EVAL_NODE")
    artifacts.mkdir(parents=True, exist_ok=True)
    extra_env = {}
    if "project" in case:
        try:
            dependency_root = safe_path(verifiers.parent / "dependencies", case["project"])
            dependencies = safe_path(dependency_root, "node_modules")
        except (ValueError, OSError, RuntimeError) as exc:
            raise RuntimeError(f"{identifier}: invalid verifier dependency path: {exc}") from exc
        if dependencies.is_dir():
            extra_env["EVAL_TODO_NODE_MODULES"] = str(dependencies.resolve())
    argv = [node, str(script), str(project)]
    completed = _run_command(argv, artifacts, assertion, artifacts, identifier, extra_env=extra_env)
    evidence_path = artifacts / f"{identifier}.verifier.json"
    evidence = {"script": str(script), "script_sha256": hashlib.sha256(script.read_bytes()).hexdigest(),
                "argv": argv, "exit_code": completed.returncode, "result": None}
    try:
        payload = json.loads(completed.stdout)
    except (ValueError, TypeError) as exc:
        evidence["error"] = "verifier did not return valid JSON"
        evidence_path.write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        raise RuntimeError(f"{identifier}: verifier did not return valid JSON (exit {completed.returncode}); see grader logs") from exc
    evidence["result"] = payload
    evidence_path.write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if completed.returncode not in {0, 1}:
        raise RuntimeError(f"{identifier}: verifier infrastructure failure (exit {completed.returncode}); see {evidence_path.name}")
    if not isinstance(payload, dict) or payload.get("status") not in ("passed", "failed"):
        raise RuntimeError(f"{identifier}: verifier returned an invalid result status")
    checks = payload.get("checks")
    if not isinstance(checks, list) or not checks:
        raise RuntimeError(f"{identifier}: verifier checks must be a nonempty list")
    names = set()
    for check in checks:
        if not isinstance(check, dict):
            raise RuntimeError(f"{identifier}: verifier checks must be objects")
        name = check.get("name", check.get("id"))
        if not isinstance(name, str) or not name.strip() or name in names or type(check.get("passed")) is not bool:
            raise RuntimeError(f"{identifier}: verifier check requires a unique name/id and boolean passed")
        if "detail" in check and not isinstance(check["detail"], str):
            raise RuntimeError(f"{identifier}: verifier check detail must be text")
        names.add(name)
    successful = all(check["passed"] for check in checks)
    if ((completed.returncode == 0) != successful
            or (payload["status"] == "passed") != successful):
        raise RuntimeError(f"{identifier}: verifier exit, status, and check outcomes disagree")
    passed = successful and completed.returncode == _expected_exit(assertion, identifier)
    count = sum(check["passed"] for check in checks)
    detail = f"{count}/{len(checks)} external checks passed; expected exit {_expected_exit(assertion, identifier)}, got {completed.returncode}"
    failed_checks = [check.get("name", check.get("id")) + (": " + check["detail"] if check.get("detail") else "")
                     for check in checks if not check["passed"]]
    if failed_checks:
        detail += "; " + "; ".join(failed_checks)
    return {"id": identifier, "kind": "external_verifier", "passed": passed,
            "detail": detail, "checks": checks, "evidence": evidence_path.name}


def grade_case(case: dict, project: Path, baseline: dict[str, str], artifacts: Path, skills: Path,
               *, verifiers: Path | None = None) -> list[dict]:
    """Grade final project state against external assertions; raise on bad config."""
    assertions = case.get("assertions")
    validate_assertions(assertions)
    project, artifacts, skills = Path(project).resolve(), Path(artifacts), Path(skills)
    if not isinstance(baseline, dict):
        raise ValueError("baseline must be a path-to-SHA256 dictionary")
    for path, digest in baseline.items():
        _relative(path, "baseline path")
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ValueError(f"baseline hash is not a SHA256: {path}")
    baseline = {path: digest for path, digest in baseline.items() if not _ignored(path)}
    # Lexical config is already validated. Escaping links in target outputs fail
    # the affected assertion without reading the file outside the project.
    unsafe_paths: dict[str, str] = {}
    for assertion in assertions:
        relatives = assertion.get("paths", []) + ([assertion["path"]] if "path" in assertion else [])
        for relative in relatives:
            try:
                safe_path(project, relative)
            except ValueError as exc:
                unsafe_paths[relative] = str(exc)
    current: dict[str, str] | None = None
    docctl = None
    results = []
    for index, assertion in enumerate(assertions, start=1):
        kind = assertion["kind"]
        identifier = assertion.get("id", f"{kind}-{index}")
        passed = False
        detail = ""
        relatives = assertion.get("paths", []) + ([assertion["path"]] if "path" in assertion else [])
        unsafe = [unsafe_paths[path] for path in relatives if path in unsafe_paths]
        if unsafe:
            detail = "; ".join(unsafe)
        elif kind in {"exists", "absent"}:
            mismatches = []
            for relative in assertion["paths"]:
                path = safe_path(project, relative)
                exists = path.exists() or path.is_symlink()
                if exists != (kind == "exists"):
                    mismatches.append(relative)
            passed = not mismatches
            detail = ("all specified paths " + ("exist" if kind == "exists" else "are absent")) if passed else "unexpected paths: " + ", ".join(mismatches)
        elif kind in {"unchanged", "changed", "only_changes"}:
            if current is None:
                try:
                    current = snapshot_files(project)
                except (ValueError, OSError) as exc:
                    results.append({"id": identifier, "kind": kind, "passed": False,
                                    "detail": f"cannot safely snapshot target: {exc}"})
                    continue
            if kind == "changed":
                paths, patterns = assertion.get("paths", []), assertion.get("patterns", [])
                changes = sorted(path for path in baseline.keys() | current.keys()
                                 if baseline.get(path) != current.get(path)
                                 and ((not paths and not patterns)
                                      or any(path == item or path.startswith(item.rstrip("/") + "/") for item in paths)
                                      or any(fnmatch.fnmatchcase(path, pattern) for pattern in patterns)))
                minimum = assertion.get("min_count", 1)
                passed = len(changes) >= minimum
                detail = f"{len(changes)} changed files; minimum {minimum}"
                if changes:
                    detail += ": " + ", ".join(changes)
            elif kind == "only_changes":
                changes = sorted(path for path in baseline.keys() | current.keys() if baseline.get(path) != current.get(path))
                unexpected = [path for path in changes if not any(fnmatch.fnmatchcase(path, pattern) for pattern in assertion["allowed"])]
                passed = not unexpected
                detail = f"{len(changes)} changed files within allowed scope" if passed else "changes outside allowed scope: " + ", ".join(unexpected)
            else:
                paths = assertion.get("paths", [])
                patterns = assertion.get("patterns", [])
                selected = set()
                missing = []
                for path in paths:
                    matches = {item for item in baseline if item == path or item.startswith(path.rstrip("/") + "/")}
                    if not matches:
                        missing.append(path)
                    selected.update(matches)
                for pattern in patterns:
                    matches = {item for item in baseline if fnmatch.fnmatchcase(item, pattern)}
                    if not matches:
                        missing.append(pattern)
                    selected.update(matches)
                if not paths and not patterns:
                    selected = set(baseline)
                mismatches = sorted(path for path in selected if current.get(path) != baseline[path])
                passed = not missing and not mismatches
                parts = (["no baseline match: " + ", ".join(missing)] if missing else []) + (["modified or deleted: " + ", ".join(mismatches)] if mismatches else [])
                detail = f"{len(selected)} baseline files unchanged" if passed else "; ".join(parts)
        elif kind in {"contains", "not_contains", "regex", "json_value", "doc_meta", "redirect"}:
            path = safe_path(project, assertion["path"])
            try:
                raw = path.read_text(encoding="utf-8")
            except (OSError, UnicodeError) as exc:
                detail = f"cannot read {assertion['path']}: {exc}"
            else:
                if kind in {"contains", "not_contains"}:
                    expected = _texts(assertion, identifier)
                    mismatches = [value for value in expected if (value in raw) != (kind == "contains")]
                    passed = not mismatches
                    detail = "all text criteria matched" if passed else "text criteria failed: " + repr(mismatches)
                elif kind == "regex":
                    passed = re.search(assertion["pattern"], raw) is not None
                    detail = "regex matched" if passed else f"regex did not match: {assertion['pattern']}"
                elif kind == "json_value":
                    try:
                        actual = json.loads(raw)
                        for part in _pointer_parts(assertion["pointer"]):
                            if isinstance(actual, list):
                                if not re.fullmatch(r"0|[1-9][0-9]*", part):
                                    raise KeyError(part)
                                actual = actual[int(part)]
                            elif isinstance(actual, dict):
                                actual = actual[part]
                            else:
                                raise KeyError(part)
                    except (ValueError, KeyError, IndexError, TypeError) as exc:
                        detail = f"JSON value unavailable at {assertion['pointer']!r}: {exc}"
                    else:
                        passed = _json_equal(actual, assertion["value"])
                        detail = "JSON value matched" if passed else f"expected {assertion['value']!r}, got {actual!r}"
                else:
                    if docctl is None:
                        docctl = _load_docctl(skills)
                    try:
                        if kind == "redirect":
                            passed = docctl.thin_redirect(raw) and ("target" not in assertion or assertion["target"] in raw)
                            detail = "thin redirect matched" if passed else "missing or invalid redirect / target"
                        else:
                            entries = docctl.document_entries(raw, assertion["path"])
                            record_id = assertion.get("record_id", assertion["fields"].get("id"))
                            if record_id is not None:
                                entries = [entry for entry in entries if entry["meta"].get("id") == record_id]
                            if len(entries) != 1:
                                detail = f"expected one selected metadata record, found {len(entries)}; use record_id for compact collections"
                            else:
                                meta = entries[0]["meta"]
                                optional = assertion.get("optional_null_fields", [])
                                mismatches = [key for key, value in assertion["fields"].items()
                                              if (key not in meta and key not in optional)
                                              or (key in meta and not _json_equal(meta[key], value))]
                                mismatches.extend(key for key in optional if key in meta and meta[key] is not None
                                                  and key not in mismatches)
                                passed = not mismatches
                                detail = "metadata fields matched" if passed else "incorrect or missing metadata fields: " + ", ".join(mismatches)
                    except (ValueError, OSError, UnicodeError) as exc:
                        detail = f"invalid document: {exc}"
        elif kind == "record_count":
            if docctl is None:
                docctl = _load_docctl(skills)
            try:
                records = docctl.collect_records(project)
                actual = sum(record.get("type") == assertion["type"] for record in records)
                passed = actual == assertion["count"]
                detail = f"expected {assertion['count']} {assertion['type']} records, found {actual}"
            except (ValueError, OSError, UnicodeError) as exc:
                detail = f"cannot collect document records: {exc}"
        elif kind == "external_verifier":
            verifier_root = Path(verifiers) if verifiers is not None else artifacts.resolve().parents[2] / "inputs/verifiers"
            results.append(_run_external_verifier(assertion, project, artifacts.resolve(), verifier_root, identifier, case))
            continue
        elif kind in {"command", "doc_check"}:
            if kind == "doc_check":
                script = skills / "ai-docs-check/scripts/check.py"
                if not script.is_file():
                    raise RuntimeError(f"bundled document checker is missing: {script}")
                argv = [sys.executable, str(script.resolve()), "--root", str(project), "check"]
                if assertion.get("strict", False):
                    argv.append("--strict")
            else:
                argv = [part.replace("{python}", sys.executable) for part in _argv(assertion, identifier)]
            completed = _run_command(argv, project, assertion, artifacts, identifier)
            if kind == "doc_check":
                try:
                    payload = json.loads(completed.stdout)
                except (ValueError, TypeError) as exc:
                    raise RuntimeError(f"{identifier}: document checker did not return valid JSON (exit {completed.returncode}); see grader logs") from exc
                if not isinstance(payload, dict) or type(payload.get("ok")) is not bool:
                    raise RuntimeError(f"{identifier}: document checker returned an invalid result schema")
            expected_exit = _expected_exit(assertion, identifier)
            expected_texts = assertion.get("stdout_contains", [])
            if isinstance(expected_texts, str):
                expected_texts = [expected_texts]
            missing = [value for value in expected_texts if value not in completed.stdout]
            passed = completed.returncode == expected_exit and not missing
            detail = f"expected exit {expected_exit}, got {completed.returncode}"
            if missing:
                detail += "; missing stdout text: " + repr(missing)
        results.append({"id": identifier, "kind": kind, "passed": passed, "detail": detail})
    return results
