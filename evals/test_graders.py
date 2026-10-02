"""Regression tests for external scenario assertions, including false outputs."""
import json
import os
from pathlib import Path
import signal
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

try:
    from .graders import grade_case, snapshot_files, validate_assertions
except ImportError:
    from graders import grade_case, snapshot_files, validate_assertions


SKILLS = Path(__file__).resolve().parents[1] / "skills"


class GraderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="ai-docs-eval-graders-")
        self.root = Path(self.temp.name).resolve()
        self.project = self.root / "project"
        self.project.mkdir()
        self.artifacts = self.root / "artifacts"
        self.write("src/main.py", "print('hello')\n")
        self.write("README.md", "# Demo\n")
        self.baseline = snapshot_files(self.project)

    def tearDown(self):
        self.temp.cleanup()

    def write(self, path, text):
        target = self.project / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        return target

    def grade(self, *assertions, skills=SKILLS, verifiers=None):
        return grade_case({"assertions": list(assertions)}, self.project, self.baseline,
                          self.artifacts, skills, verifiers=verifiers)

    def verifier(self, text, name="check.mjs"):
        root = self.root / "immutable-verifiers"
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        return root

    def test_exists_and_absent_cannot_pass_missing_or_unwanted_files(self):
        results = self.grade(
            {"kind": "exists", "paths": ["src", "src/main.py"]},
            {"kind": "absent", "paths": ["missing.md"]},
            {"kind": "exists", "paths": ["missing.md"]},
            {"kind": "absent", "paths": ["README.md"]},
        )
        self.assertEqual([item["passed"] for item in results], [True, True, False, False])

    def test_unchanged_detects_modified_deleted_and_no_baseline_match(self):
        self.write("src/main.py", "print('changed')\n")
        (self.project / "README.md").unlink()
        results = self.grade(
            {"kind": "unchanged"},
            {"kind": "unchanged", "paths": ["src"]},
            {"kind": "unchanged", "patterns": ["src/*.py"]},
            {"kind": "unchanged", "paths": ["new.md"]},
        )
        self.assertTrue(all(not item["passed"] for item in results))
        self.assertIn("README.md", results[0]["detail"])
        self.assertIn("src/main.py", results[0]["detail"])
        self.assertIn("no baseline match", results[3]["detail"])

    def test_unchanged_does_not_reject_new_files(self):
        self.write("docs/new.md", "new output\n")
        self.assertTrue(self.grade({"kind": "unchanged"})[0]["passed"])

    def test_changed_detects_added_modified_deleted_and_selected_scope(self):
        self.write("src/main.py", "print('changed')\n")
        self.write("tests/new.test.js", "new test\n")
        (self.project / "README.md").unlink()
        results = self.grade(
            {"kind": "changed", "min_count": 3},
            {"kind": "changed", "paths": ["src"]},
            {"kind": "changed", "paths": ["README.md"]},
            {"kind": "changed", "patterns": ["tests/**"]},
            {"kind": "changed", "paths": ["src"], "patterns": ["tests/**"], "min_count": 2},
            {"kind": "changed", "paths": ["missing.md"]},
            {"kind": "changed", "patterns": ["tests/**"], "min_count": 2},
        )
        self.assertEqual([item["passed"] for item in results], [True, True, True, True, True, False, False])
        self.assertIn("tests/new.test.js", results[3]["detail"])

    def test_changed_cannot_pass_without_any_change(self):
        results = self.grade({"kind": "changed"}, {"kind": "changed", "patterns": ["tests/**"]})
        self.assertTrue(all(not item["passed"] for item in results))

    def test_only_changes_covers_added_modified_and_deleted(self):
        self.write("src/main.py", "print('changed')\n")
        self.write("docs/new.md", "new output\n")
        (self.project / "README.md").unlink()
        results = self.grade(
            {"kind": "only_changes", "allowed": ["src/**", "docs/**", "README.md"]},
            {"kind": "only_changes", "allowed": ["docs/**"]},
            {"kind": "only_changes", "allowed": []},
        )
        self.assertEqual([item["passed"] for item in results], [True, False, False])
        self.assertIn("README.md", results[1]["detail"])
        self.assertIn("src/main.py", results[1]["detail"])

    def test_snapshot_ignores_dependency_build_and_git_infrastructure(self):
        for directory in (".git", "__pycache__", "node_modules", "dist", "build", ".next", ".pytest_cache", ".venv", "venv", ".cache", "coverage"):
            self.write(directory + "/noise.txt", "ignore\n")
        self.write(".DS_Store", "ignore")
        self.write("compiled.pyc", "ignore")
        self.assertEqual(snapshot_files(self.project), self.baseline)
        self.assertTrue(self.grade({"kind": "only_changes", "allowed": []})[0]["passed"])

    def test_text_and_regex_distinguish_correct_and_incorrect_facts(self):
        self.write("docs/overview.md", "# Layout\n\nCLI entry: app.main\nPort: 8080\n")
        results = self.grade(
            {"kind": "contains", "path": "docs/overview.md", "texts": ["app.main", "8080"]},
            {"kind": "not_contains", "path": "docs/overview.md", "text": "9000"},
            {"kind": "regex", "path": "docs/overview.md", "pattern": r"(?m)^Port: 8080$"},
            {"kind": "contains", "path": "docs/overview.md", "text": "9000"},
            {"kind": "not_contains", "path": "docs/overview.md", "text": "app.main"},
            {"kind": "regex", "path": "docs/overview.md", "pattern": r"Port: 9000"},
            {"kind": "not_contains", "path": "missing.md", "text": "forbidden"},
        )
        self.assertEqual([item["passed"] for item in results], [True, True, True, False, False, False, False])

    def test_json_pointer_supports_escaping_lists_null_and_root(self):
        payload = {"a/b": {"~key": [None, {"flag": True}]}}
        self.write("settings.json", json.dumps(payload))
        results = self.grade(
            {"kind": "json_value", "path": "settings.json", "pointer": "/a~1b/~0key/0", "value": None},
            {"kind": "json_value", "path": "settings.json", "pointer": "/a~1b/~0key/1/flag", "value": True},
            {"kind": "json_value", "path": "settings.json", "pointer": "", "value": payload},
            {"kind": "json_value", "path": "settings.json", "pointer": "/a~1b/~0key/1/flag", "value": 1},
            {"kind": "json_value", "path": "settings.json", "pointer": "/a~1b/~0key/02", "value": None},
            {"kind": "json_value", "path": "settings.json", "pointer": "/missing", "value": None},
        )
        self.assertEqual([item["passed"] for item in results], [True, True, True, False, False, False])

    def test_invalid_target_json_fails_assertion(self):
        self.write("settings.json", "{ invalid json")
        self.assertFalse(self.grade({"kind": "json_value", "path": "settings.json", "pointer": "", "value": {}})[0]["passed"])

    def test_frontmatter_metadata_uses_bundled_parser(self):
        self.write("docs/overview.md", '---\nid: "ARCH-001"\ntype: "architecture"\nstatus: "draft"\nowner: null\n---\n\n# Overview\n')
        results = self.grade(
            {"kind": "doc_meta", "path": "docs/overview.md", "fields": {"id": "ARCH-001", "status": "draft", "owner": None}},
            {"kind": "doc_meta", "path": "docs/overview.md", "fields": {"status": "active"}},
            {"kind": "doc_meta", "path": "docs/overview.md", "fields": {"verified_at": None}},
        )
        self.assertEqual([item["passed"] for item in results], [True, False, False])
        # A target-controlled local docctl must never supply the expected answer.
        self.write("docs/_tools/docctl.py", "raise RuntimeError('do not load target code')\n")
        self.assertTrue(self.grade({"kind": "doc_meta", "path": "docs/overview.md", "fields": {"status": "draft"}})[0]["passed"])

    def test_compact_metadata_selects_record_and_counts_without_templates(self):
        self.write("docs/architecture.md", '# Architectures\n\n<a id="arch-001"></a>\n## ARCH-001 · First\n\n```yaml doc-meta\nid: "ARCH-001"\ntype: "architecture"\nstatus: "draft"\n```\n\n### Purpose\n\nFirst.\n\n<a id="arch-002"></a>\n## ARCH-002 · Second\n\n```yaml doc-meta\nid: "ARCH-002"\ntype: "architecture"\nstatus: "draft"\n```\n\n### Purpose\n\nSecond.\n')
        self.write("docs/_templates/sample.md", '---\nid: "ARCH-TEMPLATE"\ntype: "architecture"\nstatus: "template"\n---\n')
        self.write("docs/archive/old.md", '---\nid: "ARCH-OLD"\ntype: "architecture"\nstatus: "archived"\n---\n')
        results = self.grade(
            {"kind": "doc_meta", "path": "docs/architecture.md", "record_id": "ARCH-002", "fields": {"type": "architecture"}},
            {"kind": "doc_meta", "path": "docs/architecture.md", "fields": {"id": "ARCH-001"}},
            {"kind": "doc_meta", "path": "docs/architecture.md", "fields": {"status": "draft"}},
            {"kind": "record_count", "type": "architecture", "count": 2},
            {"kind": "record_count", "type": "architecture", "count": 3},
        )
        self.assertEqual([item["passed"] for item in results], [True, True, False, True, False])

    def test_optional_null_metadata_fields_allow_missing_and_null_but_reject_approval(self):
        assertion = {"kind": "doc_meta", "path": "docs/overview.md", "fields": {"id": "ARCH-001"},
                     "optional_null_fields": ["approved_by", "approval_ref"]}
        base = '---\nid: "ARCH-001"\ntype: "architecture-overview"\nstatus: "draft"\n'
        for metadata, expected in (
            ("", True),
            ("approved_by: null\napproval_ref: null\n", True),
            ('approved_by: "Codex"\napproval_ref: null\n', False),
            ('approved_by: null\napproval_ref: "made up"\n', False),
            ('approved_by: "Codex"\napproval_ref: "made up"\n', False),
        ):
            self.write("docs/overview.md", base + metadata + "---\n\n# Architecture\n")
            with self.subTest(metadata=metadata):
                self.assertEqual(self.grade(assertion)[0]["passed"], expected)
        # Explicitly expected null can also be optional when declared as such.
        self.write("docs/overview.md", base + "---\n\n# Architecture\n")
        both = {**assertion, "fields": {"id": "ARCH-001", "approved_by": None}}
        self.assertTrue(self.grade(both)[0]["passed"])

    def test_malformed_metadata_does_not_pass(self):
        self.write("docs/bad.md", '---\nid: "ARCH-001"\nstatus: draft\n---\n')
        self.assertFalse(self.grade({"kind": "doc_meta", "path": "docs/bad.md", "fields": {"status": "draft"}})[0]["passed"])

    def test_redirect_requires_thin_marker_and_target(self):
        self.write("legacy.md", "<!-- doc-redirect -->\n# Old entry\n\n迁移到新位置。\n\n[Overview](docs/overview.md)\n")
        self.write("fake.md", "# Redirect claim\n\n[Overview](docs/overview.md)\n")
        results = self.grade(
            {"kind": "redirect", "path": "legacy.md", "target": "docs/overview.md"},
            {"kind": "redirect", "path": "legacy.md", "target": "docs/wrong.md"},
            {"kind": "redirect", "path": "fake.md"},
        )
        self.assertEqual([item["passed"] for item in results], [True, False, False])

    def test_command_runs_in_project_saves_output_and_checks_exit(self):
        results = self.grade(
            {"id": "project-command", "kind": "command", "argv": ["{python}", "-c", "from pathlib import Path; print(Path('src/main.py').read_text())"], "stdout_contains": ["hello", "print"]},
            {"kind": "command", "command": ["{python}", "-c", "raise SystemExit(3)"], "expected_exit": 3},
            {"kind": "command", "command": ["{python}", "-c", "print('wrong')"], "stdout_contains": "expected"},
            {"kind": "command", "command": ["{python}", "-c", "raise SystemExit(4)"], "expected_exit": 0},
        )
        self.assertEqual([item["passed"] for item in results], [True, True, False, False])
        self.assertIn("hello", (self.artifacts / "project-command.stdout.txt").read_text())
        self.assertTrue((self.artifacts / "project-command.stderr.txt").is_file())

    def test_command_launch_and_timeout_are_infrastructure_errors(self):
        with self.assertRaises(RuntimeError):
            self.grade({"kind": "command", "command": ["/nonexistent/ai-docs-eval-tool"]})
        with self.assertRaisesRegex(RuntimeError, "timed out"):
            self.grade({"kind": "command", "command": ["{python}", "-c", "import time; time.sleep(10)"], "timeout": 0.05})

    @unittest.skipUnless(shutil.which("node") or os.environ.get("AI_DOCS_EVAL_NODE"), "Node required for real external verifier")
    def test_external_verifier_is_independent_and_saves_per_check_evidence(self):
        root = self.verifier(
            "import {readFileSync} from 'node:fs';\n"
            "import {join} from 'node:path';\n"
            "const project = process.argv[2];\n"
            "const checks = [\n"
            " {name:'read actual README', passed:readFileSync(join(project,'README.md'),'utf8') === '# Demo\\n', detail:'checks actual project'},\n"
            " {id:'external cwd', passed:process.cwd() !== project}\n"
            "];\n"
            "const passed=checks.every(check=>check.passed);\n"
            "console.log(JSON.stringify({status:passed?'passed':'failed',checks}));\n"
            "process.exit(passed?0:1);\n"
        )
        self.write("check.mjs", "throw Error('target must not supply verifier');\n")
        result = self.grade({"id": "external", "kind": "external_verifier", "script": "check.mjs"}, verifiers=root)[0]
        self.assertTrue(result["passed"], result)
        self.assertEqual(len(result["checks"]), 2)
        evidence = json.loads((self.artifacts / result["evidence"]).read_text())
        self.assertEqual(evidence["script"], str(root / "check.mjs"))
        self.assertEqual(evidence["exit_code"], 0)
        self.assertEqual(evidence["argv"][-1], str(self.project))
        self.write("README.md", "wrong\n")
        result = self.grade({"id": "external", "kind": "external_verifier", "script": "check.mjs"}, verifiers=root)[0]
        self.assertFalse(result["passed"])
        self.assertIn("read actual README", result["detail"])
        self.assertIn("checks actual project", result["detail"])
        result = self.grade({"kind": "external_verifier", "script": "check.mjs", "expected_exit": 1}, verifiers=root)[0]
        self.assertFalse(result["passed"], "expected exit 1 must not bless failed behavior checks")

    @unittest.skipUnless(shutil.which("node") or os.environ.get("AI_DOCS_EVAL_NODE"), "Node required for real external verifier")
    def test_external_verifier_default_snapshot_root_and_dependency_environment(self):
        self.artifacts = self.root / "run/cases/demo/artifacts"
        root = self.root / "run/inputs/verifiers"
        root.mkdir(parents=True)
        dependencies = root.parent / "dependencies/demo/node_modules"
        dependencies.mkdir(parents=True)
        (root / "check.mjs").write_text(
            f"const passed=process.env.EVAL_TODO_NODE_MODULES === {json.dumps(str(dependencies))};\n"
            "const actual=process.env.EVAL_TODO_NODE_MODULES;\n"
            "console.log(JSON.stringify({status:passed?'passed':'failed', checks:[{name:'trusted deps',passed}], actual}));\n"
            "process.exit(passed?0:1);\n"
        )
        result = grade_case({"project": "demo", "assertions": [{"id": "deps", "kind": "external_verifier", "script": "check.mjs"}]},
                            self.project, self.baseline, self.artifacts, SKILLS)[0]
        self.assertTrue(result["passed"])
        evidence = json.loads((self.artifacts / result["evidence"]).read_text())
        self.assertEqual(evidence["result"]["actual"], str(dependencies))

    @unittest.skipUnless(shutil.which("node") or os.environ.get("AI_DOCS_EVAL_NODE"), "Node required for real external verifier")
    def test_external_verifier_invalid_outputs_and_exit_two_are_infrastructure_errors(self):
        invalid = [
            ("not JSON", 0),
            ("", 0),
            (json.dumps({"status": "passed", "checks": []}), 0),
            (json.dumps({"status": [], "checks": []}), 0),
            (json.dumps({"status": "passed", "checks": [{"name": "wrong type", "passed": 1}]}), 0),
            (json.dumps({"status": "passed", "checks": [{"name": "false positive", "passed": False}]}), 0),
            (json.dumps({"status": "failed", "checks": [{"name": "wrong exit", "passed": False}]}), 0),
            (json.dumps({"status": "passed", "checks": [{"name": "wrong exit", "passed": True}]}), 1),
            (json.dumps({"status": "infrastructure_error", "error": "missing browser"}), 2),
        ]
        for output, code in invalid:
            root = self.verifier(f"process.stdout.write({json.dumps(output)}); process.exit({code});\n")
            with self.subTest(output=output, code=code), self.assertRaises(RuntimeError):
                self.grade({"kind": "external_verifier", "script": "check.mjs"}, verifiers=root)

    def test_external_verifier_missing_runtime_script_and_target_control_are_infrastructure_errors(self):
        root = self.verifier("console.log('{}');\n")
        with patch.dict(os.environ, {}, clear=True), patch("shutil.which", return_value=None):
            with self.assertRaisesRegex(RuntimeError, "Node runtime unavailable"):
                self.grade({"kind": "external_verifier", "script": "check.mjs"}, verifiers=root)
        with self.assertRaisesRegex(RuntimeError, "missing"):
            self.grade({"kind": "external_verifier", "script": "missing.mjs"}, verifiers=root)
        with self.assertRaisesRegex(RuntimeError, "outside"):
            self.grade({"kind": "external_verifier", "script": "check.mjs"}, verifiers=self.project)
        (root / "escape.mjs").symlink_to(self.write("check.mjs", "throw Error('target');\n"))
        with self.assertRaisesRegex(RuntimeError, "invalid external verifier path"):
            self.grade({"kind": "external_verifier", "script": "escape.mjs"}, verifiers=root)
        with patch.dict(os.environ, {"AI_DOCS_EVAL_NODE": "/nonexistent/ai-docs-node"}):
            with self.assertRaisesRegex(RuntimeError, "could not complete"):
                self.grade({"kind": "external_verifier", "script": "check.mjs"}, verifiers=root)

    @unittest.skipUnless(shutil.which("node") or os.environ.get("AI_DOCS_EVAL_NODE"), "Node required for real external verifier")
    def test_external_verifier_timeout_is_infrastructure_error(self):
        root = self.verifier("setTimeout(()=>{},10000);\n")
        with self.assertRaisesRegex(RuntimeError, "timed out"):
            self.grade({"id": "slow-verifier", "kind": "external_verifier", "script": "check.mjs", "timeout": 0.05}, verifiers=root)
        self.assertTrue((self.artifacts / "slow-verifier.stdout.txt").is_file())

    @unittest.skipUnless(os.name == "posix", "POSIX process-group and signal regression")
    def test_timeout_kills_child_that_ignores_term_after_parent_exits(self):
        child_code = (
            "import os, signal, sys, time\n"
            "test_pid = int(sys.argv[1])\n"
            "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
            "signal.signal(signal.SIGUSR2, lambda *_: os.kill(test_pid, signal.SIGUSR1))\n"
            "os.kill(test_pid, signal.SIGUSR1)\n"
            "while True: time.sleep(0.1)\n"
        )
        parent_code = (
            "import signal, subprocess, sys, time\n"
            "signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))\n"
            f"child = subprocess.Popen([sys.executable, '-c', {child_code!r}, sys.argv[1]], "
            "stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)\n"
            "print(child.pid, flush=True)\n"
            "while True: time.sleep(0.1)\n"
        )
        # A signal response proves a live child; kill(pid, 0) alone
        # reports zombies as alive on both macOS and Linux.
        child_pid = None
        received = threading.Event()
        previous = signal.signal(signal.SIGUSR1, lambda *_: received.set())
        try:
            with self.assertRaisesRegex(RuntimeError, "timed out"):
                self.grade({"id": "timeout-tree", "kind": "command",
                            "argv": ["{python}", "-c", parent_code, str(os.getpid())], "timeout": 1})
            child_pid = int((self.artifacts / "timeout-tree.stdout.txt").read_text().strip())
            self.assertTrue(received.is_set(), "child initialized before timeout")
            received.clear()
            try:
                os.kill(child_pid, signal.SIGUSR2)
            except ProcessLookupError:
                pass
            self.assertFalse(received.wait(0.25), "SIGTERM-ignoring descendant is still alive")
        finally:
            if child_pid is not None:
                try:
                    os.kill(child_pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            signal.signal(signal.SIGUSR1, previous)

    def test_doc_check_runs_external_skill_and_detects_wrong_output(self):
        completed = subprocess.run([sys.executable, str(SKILLS / "ai-docs-init/scripts/bootstrap.py"),
                                    "--target", str(self.project), "--apply"], capture_output=True, text=True)
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertTrue(self.grade({"kind": "doc_check"})[0]["passed"])
        self.write("docs/bad.md", '---\nid: "FEATURE-1"\ntype: "feature"\nstatus: "draft"\n---\n\n# Invalid metadata\n')
        results = self.grade({"kind": "doc_check"}, {"kind": "doc_check", "expected_exit": 1})
        self.assertEqual([item["passed"] for item in results], [False, True])

    def test_doc_check_invalid_json_is_infrastructure_error(self):
        with patch("subprocess.Popen") as mocked:
            mocked.return_value.communicate.return_value = ("looks successful", "")
            mocked.return_value.returncode = 0
            with self.assertRaises(RuntimeError):
                self.grade({"kind": "doc_check"})

    def test_paths_reject_traversal_absolute_and_external_symlinks(self):
        for path in ("../secret", "src/../README.md", "/tmp/secret", "C:\\secret", "C:secret", "\\\\host\\share"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                self.grade({"kind": "exists", "paths": [path]})
        outside = self.root / "secret.txt"
        outside.write_text("secret")
        (self.project / "link.txt").symlink_to(outside)
        results = self.grade({"kind": "contains", "path": "link.txt", "text": "secret"},
                             {"kind": "only_changes", "allowed": ["**"]})
        self.assertTrue(all(not item["passed"] for item in results))
        with self.assertRaises(ValueError):
            snapshot_files(self.project)

    def test_internal_symlink_change_and_dangling_link_are_visible(self):
        link = self.project / "link.txt"
        link.symlink_to("README.md")
        self.baseline = snapshot_files(self.project)
        link.unlink()
        link.symlink_to("src/main.py")
        self.assertFalse(self.grade({"kind": "unchanged", "paths": ["link.txt"]})[0]["passed"])
        (self.project / "dangling.txt").symlink_to("missing.txt")
        self.assertFalse(self.grade({"kind": "absent", "paths": ["dangling.txt"]})[0]["passed"])

    def test_bad_configuration_raises_before_commands_run(self):
        with patch("subprocess.Popen") as mocked:
            with self.assertRaises(ValueError):
                self.grade({"kind": "command", "command": ["{python}", "-c", "print('run')"]},
                           {"kind": "regex", "path": "README.md", "pattern": "["})
            mocked.assert_not_called()

    def test_invalid_configurations_are_not_vacuous_successes(self):
        invalid = [
            [], [{"kind": "unknown"}], [{"kind": []}], [{"kind": "exists", "paths": []}],
            [{"kind": "absent", "paths": "README.md"}], [{"kind": "only_changes"}],
            [{"kind": "only_changes", "allowed": ["../**"]}],
            [{"kind": "unchanged", "patterns": "**"}],
            [{"kind": "changed", "paths": "src"}],
            [{"kind": "changed", "patterns": ["../**"]}],
            [{"kind": "changed", "min_count": 0}],
            [{"kind": "changed", "min_count": True}],
            [{"kind": "changed", "min_count": 1.5}],
            [{"kind": "contains", "path": "README.md", "texts": []}],
            [{"kind": "contains", "path": "README.md", "text": "", "texts": ["x"]}],
            [{"kind": "regex", "path": "README.md", "pattern": "["}],
            [{"kind": "json_value", "path": "x", "pointer": "a", "value": 1}],
            [{"kind": "json_value", "path": "x", "pointer": "/a~2", "value": 1}],
            [{"kind": "json_value", "path": "x", "pointer": ""}],
            [{"kind": "doc_meta", "path": "x", "fields": {}}],
            [{"kind": "doc_meta", "path": "x", "fields": {"owner": []}}],
            [{"kind": "doc_meta", "path": "x", "fields": {"id": "A"}, "optional_null_fields": "approved_by"}],
            [{"kind": "doc_meta", "path": "x", "fields": {"id": "A"}, "optional_null_fields": []}],
            [{"kind": "doc_meta", "path": "x", "fields": {"id": "A"}, "optional_null_fields": [None]}],
            [{"kind": "doc_meta", "path": "x", "fields": {"id": "A"}, "optional_null_fields": ["approved_by", "approved_by"]}],
            [{"kind": "doc_meta", "path": "x", "fields": {"approved_by": "human"}, "optional_null_fields": ["approved_by"]}],
            [{"kind": "record_count", "type": "task", "count": -1}],
            [{"kind": "record_count", "type": "task", "count": True}],
            [{"kind": "command", "command": []}],
            [{"kind": "command", "argv": ["python"], "command": ["python"]}],
            [{"kind": "command", "command": ["python"], "timeout": 61}],
            [{"kind": "command", "command": ["python"], "expected_exit": False}],
            [{"kind": "doc_check", "strict": "yes"}],
            [{"kind": "external_verifier"}],
            [{"kind": "external_verifier", "script": "/tmp/check.mjs"}],
            [{"kind": "external_verifier", "script": "../check.mjs"}],
            [{"kind": "external_verifier", "script": "check.mjs", "timeout": True}],
            [{"kind": "external_verifier", "script": "check.mjs", "timeout": 61}],
            [{"kind": "external_verifier", "script": "check.mjs", "expected_exit": False}],
            [{"kind": "external_verifier", "script": "check.mjs", "expected_exit": 2}],
            [{"id": "../bad", "kind": "doc_check"}],
            [{"id": "same", "kind": "doc_check"}, {"id": "same", "kind": "doc_check"}],
        ]
        for assertions in invalid:
            with self.subTest(assertions=assertions), self.assertRaises(ValueError):
                validate_assertions(assertions)


if __name__ == "__main__":
    unittest.main()
