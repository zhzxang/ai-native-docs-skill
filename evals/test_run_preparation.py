"""Preparation and frozen-input tests; no real Codex or npm network calls."""
from __future__ import annotations

from contextlib import redirect_stdout
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import run as runner


class PreparationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="ai-docs-eval-preparation-")
        self.root = Path(self.temporary.name).resolve()
        self.source = self.root / "original"
        self.source.mkdir()
        self.artifacts = self.root / "artifacts"
        self.artifacts.mkdir()
        self.plans = self.root / "plans"
        self.plans.mkdir()
        self.skills = self.root / "skills"
        self.skills.mkdir()

    def tearDown(self):
        self.temporary.cleanup()

    def apply(self, project, actions, *, dependencies=None):
        return runner.apply_actions(actions, project, self.plans, self.skills,
                                    self.artifacts, "setup", 5,
                                    dependencies=dependencies)

    def installed_dependencies(self):
        runner.write_json(self.source / "package.json", {"name": "tiny", "version": "1.0.0"})
        package = {
            "version": "1.0.0", "resolved": "https://example.invalid/tiny-1.0.0.tgz",
            "integrity": "sha512-fixture",
        }
        runner.write_json(self.source / "package-lock.json", {
            "name": "tiny", "version": "1.0.0", "lockfileVersion": 3,
            "packages": {"": {"name": "tiny", "version": "1.0.0"}, "node_modules/tiny": package},
        })
        modules = self.source / "node_modules"
        entry = modules / "tiny/bin.mjs"
        entry.parent.mkdir(parents=True)
        entry.write_text("export const value = 'original dependency'\n")
        (modules / ".bin").mkdir()
        (modules / ".bin/tiny").symlink_to("../tiny/bin.mjs")
        runner.write_json(modules / ".package-lock.json", {
            "name": "tiny", "version": "1.0.0", "lockfileVersion": 3,
            "packages": {"node_modules/tiny": package},
        })
        return modules

    def freeze_source(self):
        frozen = self.root / "frozen-project"
        runner.copy_tree(self.source, frozen)
        return frozen

    def test_replace_injects_bug_only_in_the_disposable_project(self):
        original = "export function toggle() { return 'only target' }\n"
        (self.source / "todos.ts").write_text(original)
        (self.source / "keep.txt").write_text("keep\n")
        before = runner.snapshot_files(self.source)
        project = self.root / "attempt"
        runner.copy_tree(self.source, project)
        records = self.apply(project, [{
            "action": "replace", "path": "todos.ts",
            "old": "return 'only target'", "new": "return 'all targets'",
        }])
        self.assertEqual((project / "todos.ts").read_text(), original.replace("only target", "all targets"))
        self.assertEqual(runner.snapshot_files(self.source), before)
        self.assertEqual(runner.make_diff(before, runner.snapshot_files(project)), {
            "added": [], "deleted": [], "modified": ["todos.ts"],
        })
        self.assertEqual(records, [{"action": "replace", "path": "todos.ts"}])
        self.assertEqual(json.loads((self.artifacts / "setup-commands.json").read_text()), records)

    def test_replace_missing_or_duplicate_match_fails_without_writing(self):
        for content in ("other text\n", "original\noriginal\n"):
            with self.subTest(content=content):
                path = self.source / "value.txt"
                path.write_text(content)
                before = path.read_bytes()
                with self.assertRaisesRegex(runner.InfrastructureError, "exactly one match"):
                    self.apply(self.source, [{
                        "action": "replace", "path": "value.txt",
                        "old": "original", "new": "replacement",
                    }])
                self.assertEqual(path.read_bytes(), before)

    def test_invalid_replace_configuration_rejected_before_execution(self):
        valid = {"action": "replace", "path": "source.txt", "old": "before", "new": "after"}
        invalid = [
            {"old": ""}, {"old": None}, {"old": 1}, {"new": None}, {"new": []},
            {"new": "before"}, {"path": "../outside.txt"}, {"path": "/outside.txt"},
            {"path": None}, {"path": ""},
        ]
        for override in invalid:
            with self.subTest(override=override), self.assertRaises(ValueError):
                runner.validate_actions([{**valid, **override}], "case.setup")
        # Empty replacement is useful for deliberately removing a faulty line.
        runner.validate_actions([{**valid, "new": ""}], "case.setup")

    def test_replace_cannot_escape_through_a_project_symlink(self):
        outside = self.root / "outside.txt"
        outside.write_text("original\n")
        (self.source / "link.txt").symlink_to(outside)
        with self.assertRaises(ValueError):
            self.apply(self.source, [{
                "action": "replace", "path": "link.txt", "old": "original", "new": "changed",
            }])
        self.assertEqual(outside.read_text(), "original\n")

    def test_installed_dependencies_freeze_once_and_copy_fresh_with_bin_links(self):
        modules = self.installed_dependencies()
        frozen = self.freeze_source()
        dependency_copy = self.root / "inputs/dependencies/tiny/node_modules"
        with patch.object(runner, "run_process") as command:
            prepared = runner.prepare_node_dependencies(
                self.source, frozen, dependency_copy, self.artifacts, 5)
            command.assert_not_called()
        self.assertEqual(prepared, dependency_copy)
        self.assertFalse((frozen / "node_modules").exists())
        lock_bytes = (self.source / "package-lock.json").read_bytes()
        self.assertEqual(json.loads((prepared.parent / "provenance.json").read_text())["package_lock_sha256"],
                         hashlib.sha256(lock_bytes).hexdigest())

        first = self.root / "attempt-1"
        second = self.root / "attempt-2"
        first.mkdir()
        second.mkdir()
        self.apply(first, [{"action": "node_dependencies"}], dependencies=prepared)
        link = first / "node_modules/.bin/tiny"
        self.assertTrue(link.is_symlink())
        self.assertEqual(os.readlink(link), "../tiny/bin.mjs")
        self.assertTrue(link.resolve().is_relative_to((first / "node_modules").resolve()))
        link.write_text("attempt one changed dependency\n")
        self.assertEqual((modules / "tiny/bin.mjs").read_text(), "export const value = 'original dependency'\n")
        self.assertEqual((prepared / "tiny/bin.mjs").read_text(), "export const value = 'original dependency'\n")

        # Later fixture changes must not replace the already-frozen dependencies.
        (modules / "tiny/bin.mjs").write_text("fixture changed after freeze\n")
        reused = runner.prepare_node_dependencies(self.source, frozen, prepared, self.artifacts, 5)
        self.assertEqual(reused, prepared)
        self.apply(second, [{"action": "node_dependencies"}], dependencies=reused)
        self.assertEqual((second / "node_modules/.bin/tiny").read_text(), "export const value = 'original dependency'\n")
        self.assertNotEqual((first / "node_modules/.bin/tiny").resolve(),
                            (second / "node_modules/.bin/tiny").resolve())
        self.assertEqual((self.source / "package-lock.json").read_bytes(), lock_bytes)

    def test_node_dependency_action_requires_prepared_tree_and_fresh_destination(self):
        project = self.root / "attempt"
        project.mkdir()
        with self.assertRaisesRegex(runner.InfrastructureError, "not prepared"):
            self.apply(project, [{"action": "node_dependencies"}])
        modules = self.installed_dependencies()
        self.apply(project, [{"action": "node_dependencies"}], dependencies=modules)
        with self.assertRaisesRegex(runner.InfrastructureError, "already exist"):
            self.apply(project, [{"action": "node_dependencies"}], dependencies=modules)

    def test_external_dependency_symlinks_are_rejected_without_copying(self):
        for link_kind in ("file", "directory"):
            with self.subTest(link_kind=link_kind):
                modules = self.root / ("modules-" + link_kind)
                modules.mkdir()
                external = self.root / ("outside-" + link_kind)
                if link_kind == "file":
                    external.write_text("private dependency\n")
                else:
                    external.mkdir()
                    (external / "value.txt").write_text("private dependency\n")
                (modules / "escape").symlink_to(external, target_is_directory=link_kind == "directory")
                destination = self.root / ("copied-" + link_kind)
                with self.assertRaisesRegex(runner.InfrastructureError, "symlink"):
                    runner.copy_node_modules(modules, destination)
                self.assertFalse(destination.exists())

    def test_absolute_internal_dependency_link_cannot_keep_pointing_at_source(self):
        modules = self.installed_dependencies()
        (modules / ".bin/absolute").symlink_to(modules / "tiny/bin.mjs")
        destination = self.root / "copied-modules"
        try:
            runner.copy_node_modules(modules, destination)
        except runner.InfrastructureError:
            self.assertFalse(destination.exists())
            return
        copied_link = destination / ".bin/absolute"
        self.assertTrue(copied_link.resolve().is_relative_to(destination.resolve()),
                        "accepted absolute internal symlink still targets original dependency tree")
        copied_link.write_text("attempt edit\n")
        self.assertEqual((modules / "tiny/bin.mjs").read_text(), "export const value = 'original dependency'\n")

    def test_missing_lock_or_npm_is_an_infrastructure_error_without_installing(self):
        frozen = self.freeze_source()
        destination = self.root / "prepared/node_modules"
        with patch.object(runner, "run_process") as command:
            with self.assertRaisesRegex(runner.InfrastructureError, "package-lock"):
                runner.prepare_node_dependencies(self.source, frozen, destination, self.artifacts, 5)
            runner.write_json(frozen / "package-lock.json", {"lockfileVersion": 3})
            with patch.object(runner.shutil, "which", return_value=None):
                with self.assertRaisesRegex(runner.InfrastructureError, "npm is required"):
                    runner.prepare_node_dependencies(self.source, frozen, destination, self.artifacts, 5)
            command.assert_not_called()
        self.assertFalse(destination.exists())
        self.assertFalse((self.source / "node_modules").exists())

    def test_install_fallback_runs_only_in_frozen_copy_and_disables_scripts(self):
        runner.write_json(self.source / "package-lock.json", {"lockfileVersion": 3})
        runner.write_json(self.source / "package.json", {"name": "tiny"})
        before = runner.snapshot_files(self.source)
        frozen = self.freeze_source()
        destination = self.root / "prepared/node_modules"

        def install(argv, cwd, stdout, stderr, timeout):
            self.assertEqual(argv, ["/fake/npm", "ci", "--ignore-scripts", "--no-audit", "--no-fund"])
            self.assertEqual(cwd, frozen)
            self.assertEqual(timeout, 5)
            entry = cwd / "node_modules/tiny/index.mjs"
            entry.parent.mkdir(parents=True)
            entry.write_text("export default 'locked'\n")
            return {"argv": argv, "exit_code": 0, "stdout": str(stdout), "stderr": str(stderr)}

        with patch.object(runner.shutil, "which", return_value="/fake/npm"), \
                patch.object(runner, "run_process", side_effect=install) as command:
            runner.prepare_node_dependencies(self.source, frozen, destination, self.artifacts, 5)
        command.assert_called_once()
        self.assertEqual((destination / "tiny/index.mjs").read_text(), "export default 'locked'\n")
        self.assertEqual(runner.snapshot_files(self.source), before)
        self.assertFalse((self.source / "node_modules").exists())
        self.assertEqual(json.loads((destination.parent / "provenance.json").read_text())["method"], "npm-ci")

    def test_stale_or_missing_installed_metadata_uses_frozen_install_fallback(self):
        modules = self.installed_dependencies()
        metadata = modules / ".package-lock.json"
        installed = json.loads(metadata.read_text())
        variants = ("missing", "malformed", "version", "resolved", "integrity", "missing-package")
        for variant in variants:
            with self.subTest(variant=variant):
                current = json.loads(json.dumps(installed))
                if variant == "missing":
                    metadata.unlink(missing_ok=True)
                elif variant == "malformed":
                    metadata.write_text("not-json")
                else:
                    if variant in {"version", "resolved", "integrity"}:
                        current["packages"]["node_modules/tiny"][variant] = "stale descriptor"
                    runner.write_json(metadata, current)
                if variant == "missing-package":
                    shutil.rmtree(modules / "tiny")
                before_metadata = metadata.read_bytes() if metadata.exists() else None
                before_entry = (modules / "tiny/bin.mjs").read_bytes() if (modules / "tiny/bin.mjs").exists() else None
                frozen = self.root / ("frozen-" + variant)
                runner.copy_tree(self.source, frozen)
                destination = self.root / "prepared" / variant / "node_modules"

                def install(argv, cwd, stdout, stderr, timeout):
                    self.assertEqual(cwd, frozen)
                    self.assertEqual(argv, ["/fake/npm", "ci", "--ignore-scripts", "--no-audit", "--no-fund"])
                    entry = cwd / "node_modules/tiny/bin.mjs"
                    entry.parent.mkdir(parents=True)
                    entry.write_text("installed in frozen input\n")
                    runner.write_json(cwd / "node_modules/.package-lock.json", installed)
                    return {"argv": argv, "exit_code": 0, "stdout": str(stdout), "stderr": str(stderr)}

                with patch.object(runner.shutil, "which", return_value="/fake/npm"), \
                        patch.object(runner, "run_process", side_effect=install) as command:
                    runner.prepare_node_dependencies(self.source, frozen, destination, self.artifacts, 5)
                command.assert_called_once()
                self.assertEqual((destination / "tiny/bin.mjs").read_text(), "installed in frozen input\n")
                self.assertEqual(json.loads((destination.parent / "provenance.json").read_text())["method"], "npm-ci")
                self.assertEqual(metadata.read_bytes() if metadata.exists() else None, before_metadata)
                self.assertEqual((modules / "tiny/bin.mjs").read_bytes() if (modules / "tiny/bin.mjs").exists() else None,
                                 before_entry)

    def test_frozen_dependency_tampering_is_rejected_when_reused(self):
        self.installed_dependencies()
        frozen = self.freeze_source()
        destination = self.root / "prepared/node_modules"
        runner.prepare_node_dependencies(self.source, frozen, destination, self.artifacts, 5)
        hashes_file = destination.parent / "hashes.json"
        self.assertTrue(hashes_file.is_file())
        original_hashes = hashes_file.read_bytes()
        (destination / "tiny/bin.mjs").write_text("tampered frozen dependency\n")
        with self.assertRaises(runner.InfrastructureError):
            runner.prepare_node_dependencies(self.source, frozen, destination, self.artifacts, 5)
        self.assertEqual(hashes_file.read_bytes(), original_hashes)

    def test_dependency_hashes_include_nested_modules_hidden_files_and_symlinks(self):
        modules = self.installed_dependencies()
        nested = modules / "tiny/node_modules/child/index.mjs"
        nested.parent.mkdir(parents=True)
        nested.write_text("nested dependency\n")
        hidden = modules / "tiny/.cache-marker"
        hidden.write_text("hidden dependency state\n")
        hashes = runner.dependency_hashes(modules)
        self.assertTrue({"tiny/bin.mjs", ".bin/tiny", ".package-lock.json",
                         "tiny/node_modules/child/index.mjs", "tiny/.cache-marker"}.issubset(hashes))
        nested.write_text("nested dependency changed\n")
        self.assertNotEqual(runner.dependency_hashes(modules)["tiny/node_modules/child/index.mjs"],
                            hashes["tiny/node_modules/child/index.mjs"])
        link = modules / ".bin/tiny"
        link.unlink()
        link.symlink_to("../tiny/node_modules/child/index.mjs")
        self.assertNotEqual(runner.dependency_hashes(modules)[".bin/tiny"], hashes[".bin/tiny"])

    def test_failed_install_is_an_infrastructure_error_not_a_prepared_dependency_tree(self):
        runner.write_json(self.source / "package-lock.json", {"lockfileVersion": 3})
        frozen = self.freeze_source()
        destination = self.root / "prepared/node_modules"
        with patch.object(runner.shutil, "which", return_value="/fake/npm"), \
                patch.object(runner, "run_process", return_value={"exit_code": 1}):
            with self.assertRaisesRegex(runner.InfrastructureError, "npm ci failed"):
                runner.prepare_node_dependencies(self.source, frozen, destination, self.artifacts, 5)
        self.assertFalse(destination.exists())
        self.assertFalse((self.source / "node_modules").exists())


class FrozenVerifierTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="ai-docs-eval-frozen-verifiers-")
        self.root = Path(self.temporary.name).resolve()
        self.source = self.root / "source"
        self.source.mkdir()
        (self.source / "source.txt").write_text("original\n")
        self.controller = self.root / "controller"
        self.controller.mkdir()
        for name in ("run.py", "graders.py"):
            shutil.copyfile(HERE / name, self.controller / name)
        verifier = self.controller / "verifiers/tiny.mjs"
        verifier.parent.mkdir()
        verifier.write_text("// Frozen fixture verifier; this test does not execute it.\n")
        self.cases = self.root / "cases"
        self.projects = self.root / "projects"
        self.cases.mkdir()
        self.projects.mkdir()
        runner.write_json(self.cases / "case.json", {
            "version": 1, "id": "prepared", "project": "tiny", "prompt": "Create output.",
            "steps": [{"action": "write", "path": "result.txt", "content": "expected\n"}],
            "assertions": [{"kind": "contains", "path": "result.txt", "text": "expected"}],
        })
        runner.write_json(self.projects / "project.json", {
            "version": 1, "id": "tiny", "source": str(self.source),
        })

    def tearDown(self):
        self.temporary.cleanup()

    def saved_run(self):
        args = runner.parser().parse_args([
            "run", "--engine", "tools", "--cases-dir", str(self.cases),
            "--projects-dir", str(self.projects), "--results-dir", str(self.root / "results"),
        ])
        with patch.object(runner, "EVAL_ROOT", self.controller), redirect_stdout(io.StringIO()):
            self.assertEqual(runner.run_suite(args), 0)
        return next((self.root / "results").iterdir())

    def test_external_verifiers_are_frozen_and_regrade_rejects_tampering(self):
        saved = self.saved_run()
        verifier = saved / "inputs/verifiers/tiny.mjs"
        hashes = json.loads((saved / "inputs/verifier-hashes.json").read_text())
        self.assertEqual(hashes, {"tiny.mjs": hashlib.sha256(verifier.read_bytes()).hexdigest()})
        original = verifier.read_bytes()
        (self.controller / "verifiers/tiny.mjs").write_text("// later controller edit\n")
        self.assertEqual(verifier.read_bytes(), original)
        with redirect_stdout(io.StringIO()):
            self.assertEqual(runner.grade_saved(SimpleNamespace(run_dir=saved)), 0)
        verifier.write_text("// tampered frozen verifier\n")
        with self.assertRaisesRegex(runner.InfrastructureError, "Frozen external verifiers changed"):
            runner.grade_saved(SimpleNamespace(run_dir=saved))

    def test_frozen_dependency_tampering_is_rejected_when_regrading(self):
        package = {"version": "1.0.0"}
        runner.write_json(self.source / "package.json", {"name": "tiny", "version": "1.0.0"})
        runner.write_json(self.source / "package-lock.json", {
            "lockfileVersion": 3, "packages": {"node_modules/tiny": package},
        })
        modules = self.source / "node_modules"
        entry = modules / "tiny/index.mjs"
        entry.parent.mkdir(parents=True)
        entry.write_text("frozen tiny dependency\n")
        runner.write_json(modules / ".package-lock.json", {
            "lockfileVersion": 3, "packages": {"node_modules/tiny": package},
        })
        case_file = self.cases / "case.json"
        case = json.loads(case_file.read_text())
        case["setup"] = [{"action": "node_dependencies"}]
        runner.write_json(case_file, case)
        with patch.object(runner, "run_process") as command:
            saved = self.saved_run()
            command.assert_not_called()
        frozen = saved / "inputs/dependencies/tiny/node_modules"
        hashes_file = frozen.parent / "hashes.json"
        self.assertTrue(hashes_file.is_file())
        hashes = json.loads(hashes_file.read_text())
        self.assertEqual(hashes, runner.dependency_hashes(frozen))
        with redirect_stdout(io.StringIO()):
            self.assertEqual(runner.grade_saved(SimpleNamespace(run_dir=saved)), 0)
        (frozen / "tiny/index.mjs").write_text("tampered dependency\n")
        with self.assertRaises(runner.InfrastructureError):
            runner.grade_saved(SimpleNamespace(run_dir=saved))
        self.assertEqual(entry.read_text(), "frozen tiny dependency\n")

    def test_legacy_saved_grader_without_verifiers_keyword_can_be_regraded(self):
        saved = self.saved_run()
        # A pre-verifier saved run has no verifier hash manifest and a five-argument grader.
        (saved / "inputs/verifier-hashes.json").unlink()
        legacy_grader = (
            "import hashlib\n"
            "def snapshot_files(project):\n"
            "    return {path.relative_to(project).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()\n"
            "            for path in project.rglob('*') if path.is_file()}\n"
            "def grade_case(case, project, baseline, artifacts, skills):\n"
            "    return [{'id': 'legacy', 'kind': 'legacy', 'passed': True, 'detail': 'Legacy grader called'}]\n"
        )
        grader = saved / "inputs/graders.py"
        grader.write_text(legacy_grader)
        hashes_path = saved / "inputs/harness-hashes.json"
        hashes = json.loads(hashes_path.read_text())
        hashes["graders.py"] = hashlib.sha256(grader.read_bytes()).hexdigest()
        runner.write_json(hashes_path, hashes)
        with redirect_stdout(io.StringIO()):
            self.assertEqual(runner.grade_saved(SimpleNamespace(run_dir=saved)), 0)
        report = json.loads((saved / "report.json").read_text())
        self.assertEqual(report["attempts"][0]["status"], "passed")
        self.assertTrue(any(check["id"] == "legacy" for check in report["attempts"][0]["checks"]))


if __name__ == "__main__":
    unittest.main()
