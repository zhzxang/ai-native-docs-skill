"""Local runner integration tests using a disposable fake Codex executable."""
from __future__ import annotations

import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import run as runner


FAKE_CODEX = r'''
import json
import os
from pathlib import Path
import re
import sys

argv = sys.argv[1:]
log = Path(os.environ["EVAL_FAKE_LOG"])
with log.open("a", encoding="utf-8") as handle:
    handle.write(json.dumps(argv, ensure_ascii=False) + "\n")
if argv == ["--version"]:
    print("codex fake-test-1")
    raise SystemExit(0)

project = Path(argv[argv.index("-C") + 1])
final = Path(argv[argv.index("-o") + 1])
match = re.search(r"四个 Skill 位于：([^\n]+)", argv[-1])
if match is None:
    print("missing skill instruction", file=sys.stderr)
    raise SystemExit(3)
skills = Path(match.group(1))
skill = skills / "ai-docs-init" / "SKILL.md"
observed = {
    "source_before": (project / "source.txt").read_text(),
    "output_existed": (project / "result.md").exists(),
    "skill_marker_existed": "FAKE-POLLUTION-001" in skill.read_text(),
    "skill_path": str(skills),
    "argv": argv,
}
(final.parent / "fake-observed.json").write_text(json.dumps(observed))
behavior = os.environ.get("EVAL_FAKE_BEHAVIOR", "pass")
(project / "result.md").write_text("WRONG\n" if behavior == "wrong" else "EXPECTED\n")
final.write_text("Everything is correct.\n")

if behavior == "pollute-on-first":
    executions = sum(json.loads(line)[0] == "exec" for line in log.read_text().splitlines())
    if executions == 1:
        (project / "source.txt").write_text("polluted\n")
        skill.write_text(skill.read_text() + "\nFAKE-POLLUTION-001\n")
        print(json.dumps({"type": "turn.failed", "error": {"message": "authentication failed"}}))
        raise SystemExit(1)

if behavior == "malformed":
    print("not valid JSONL")
elif behavior in {"failed", "auth"}:
    message = "authentication failed" if behavior == "auth" else "task could not complete"
    print(json.dumps({"type": "turn.failed", "error": {"message": message}}))
else:
    print(json.dumps({"type": "turn.completed", "usage": {"input_tokens": 1, "output_tokens": 1}}))
raise SystemExit(7 if behavior == "nonzero" else 0)
'''


class RunnerIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="ai-docs-eval-runner-")
        self.root = Path(self.temporary.name).resolve()
        self.source = self.root / "original-project"
        self.source.mkdir()
        (self.source / "source.txt").write_text("original\n", encoding="utf-8")
        self.cases = self.root / "cases"
        self.projects = self.root / "projects"
        self.results = self.root / "results"
        self.cases.mkdir()
        self.projects.mkdir()
        self.case = {
            "version": 1,
            "id": "local-output",
            "project": "local-project",
            "tags": ["integration"],
            "prompt": "请在 {project} 中创建 result.md，内容为 EXPECTED。",
            "assertions": [
                {"kind": "exists", "paths": ["result.md"]},
                {"kind": "contains", "path": "result.md", "text": "EXPECTED"},
                {"kind": "unchanged", "paths": ["source.txt"]},
                {"kind": "only_changes", "allowed": ["result.md"]},
            ],
        }
        self.write_case()
        self.write_json(self.projects / "project.json", {
            "version": 1, "id": "local-project", "source": str(self.source),
        })
        self.fake = self.root / "fake-codex"
        self.fake.write_text("#!" + sys.executable + "\n" + FAKE_CODEX, encoding="utf-8")
        self.fake.chmod(0o755)
        self.log = self.root / "fake-invocations.jsonl"

    def tearDown(self):
        self.temporary.cleanup()

    def write_json(self, path, data):
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def write_case(self):
        self.write_json(self.cases / "case.json", self.case)

    def cli(self, *arguments, behavior="pass"):
        env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1",
               "EVAL_FAKE_LOG": str(self.log), "EVAL_FAKE_BEHAVIOR": behavior}
        return subprocess.run([sys.executable, str(HERE / "run.py"), *arguments],
                              text=True, capture_output=True, env=env, timeout=30)

    def run_case(self, *extra, behavior="pass"):
        return self.cli("run", "--cases-dir", str(self.cases),
                        "--projects-dir", str(self.projects),
                        "--results-dir", str(self.results),
                        "--codex-bin", str(self.fake), *extra, behavior=behavior)

    def saved_run(self):
        runs = sorted(self.results.iterdir())
        self.assertEqual(len(runs), 1)
        report = json.loads((runs[0] / "report.json").read_text())
        return runs[0], report

    def invocations(self):
        if not self.log.exists():
            return []
        return [json.loads(line) for line in self.log.read_text().splitlines()]

    def test_output_grader_accepts_correct_output_and_rejects_wrong_self_report(self):
        completed = self.run_case()
        self.assertEqual(completed.returncode, 0, completed.stderr + completed.stdout)
        run_dir, report = self.saved_run()
        self.assertEqual(report["attempts"][0]["status"], "passed")
        self.assertEqual(report["cli_version"], "codex fake-test-1")
        self.assertEqual(report["attempts"][0]["usage"]["output_tokens"], 1)
        self.assertEqual((self.source / "source.txt").read_text(), "original\n")
        self.assertTrue((run_dir / "local-output/attempt-1/artifacts/diff.json").is_file())

        self.results = self.root / "wrong-results"
        completed = self.run_case(behavior="wrong")
        self.assertEqual(completed.returncode, 1, completed.stderr + completed.stdout)
        _, report = self.saved_run()
        row = report["attempts"][0]
        self.assertEqual(row["status"], "failed")
        self.assertTrue(row["target_result"]["passed"])
        self.assertTrue(any(check["kind"] == "contains" and not check["passed"]
                            for check in row["checks"]))

    def test_task_errors_and_protocol_or_auth_errors_have_distinct_statuses(self):
        for behavior, expected_exit, expected_status in [
            ("nonzero", 1, "failed"),
            ("failed", 1, "failed"),
            ("auth", 2, "infrastructure_error"),
            ("malformed", 2, "infrastructure_error"),
        ]:
            with self.subTest(behavior=behavior):
                self.results = self.root / (behavior + "-results")
                completed = self.run_case(behavior=behavior)
                self.assertEqual(completed.returncode, expected_exit, completed.stderr + completed.stdout)
                run_dir, report = self.saved_run()
                row = report["attempts"][0]
                self.assertEqual(row["status"], expected_status)
                self.assertTrue((run_dir / "local-output/attempt-1/artifacts/events.jsonl").is_file())
                if expected_status == "failed":
                    self.assertFalse(row["target_result"]["passed"])
                else:
                    self.assertTrue(row["error"])

    def test_default_cli_model_is_preserved_and_explicit_model_is_forwarded(self):
        completed = self.run_case()
        self.assertEqual(completed.returncode, 0, completed.stderr)
        execution = [argv for argv in self.invocations() if argv[0] == "exec"][-1]
        self.assertNotIn("--model", execution)
        self.assertIn("--ephemeral", execution)
        self.assertEqual(execution[execution.index("--sandbox") + 1], "workspace-write")

        self.results = self.root / "model-results"
        completed = self.run_case("--model", "fixture-model")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        execution = [argv for argv in self.invocations() if argv[0] == "exec"][-1]
        self.assertEqual(execution[execution.index("--model") + 1], "fixture-model")
        _, report = self.saved_run()
        self.assertEqual(report["model"], "fixture-model")

    def test_repeat_uses_fresh_project_and_trial_skills_after_infrastructure_error(self):
        completed = self.run_case("--repeat", "2", behavior="pollute-on-first")
        self.assertEqual(completed.returncode, 2, completed.stderr + completed.stdout)
        run_dir, report = self.saved_run()
        self.assertEqual([row["status"] for row in report["attempts"]],
                         ["infrastructure_error", "passed"])
        observed = [json.loads((run_dir / f"local-output/attempt-{number}/artifacts/fake-observed.json").read_text())
                    for number in (1, 2)]
        self.assertEqual([item["source_before"] for item in observed], ["original\n", "original\n"])
        self.assertEqual([item["output_existed"] for item in observed], [False, False])
        self.assertEqual([item["skill_marker_existed"] for item in observed], [False, False])
        self.assertNotEqual(observed[0]["skill_path"], observed[1]["skill_path"])
        self.assertNotIn("FAKE-POLLUTION-001", (run_dir / "inputs/skills/ai-docs-init/SKILL.md").read_text())
        self.assertEqual((self.source / "source.txt").read_text(), "original\n")
        self.assertIn("source.txt", report["attempts"][0]["diff"]["modified"])

    def test_dry_run_validates_without_running_cli_or_creating_files(self):
        before = {path.relative_to(self.root).as_posix(): path.read_bytes()
                  for path in self.root.rglob("*") if path.is_file()}
        completed = self.run_case("--dry-run")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(json.loads(completed.stdout)["model"], "CLI default")
        after = {path.relative_to(self.root).as_posix(): path.read_bytes()
                 for path in self.root.rglob("*") if path.is_file()}
        self.assertEqual(before, after)
        self.assertFalse(self.results.exists())
        self.assertFalse(self.log.exists())

    def test_regrade_rejects_changed_output_without_invoking_codex(self):
        completed = self.run_case()
        self.assertEqual(completed.returncode, 0, completed.stderr)
        run_dir, _ = self.saved_run()
        calls_before = self.invocations()
        (run_dir / "local-output/attempt-1/project/result.md").write_text("WRONG\n")
        completed = self.cli("grade", str(run_dir))
        self.assertEqual(completed.returncode, 1, completed.stderr + completed.stdout)
        _, report = self.saved_run()
        self.assertEqual(report["attempts"][0]["status"], "failed")
        self.assertEqual(self.invocations(), calls_before)

    def test_completed_target_with_grader_infrastructure_error_can_be_regraded(self):
        grader_command = self.root / "later-available-grader"
        self.case["assertions"].append({
            "kind": "command", "argv": [str(grader_command)],
            "stdout_contains": "grader ready", "expected_exit": 0,
        })
        self.write_case()
        completed = self.run_case()
        self.assertEqual(completed.returncode, 2, completed.stderr + completed.stdout)
        run_dir, report = self.saved_run()
        self.assertEqual(report["attempts"][0]["status"], "infrastructure_error")
        self.assertTrue(report["attempts"][0]["target_result"]["passed"])
        calls_before = self.invocations()
        grader_command.write_text("#!" + sys.executable + "\nprint('grader ready')\n")
        grader_command.chmod(0o755)
        completed = self.cli("grade", str(run_dir))
        self.assertEqual(completed.returncode, 0, completed.stderr + completed.stdout)
        _, report = self.saved_run()
        self.assertEqual(report["attempts"][0]["status"], "passed")
        self.assertNotIn("error", report["attempts"][0])
        self.assertEqual(self.invocations(), calls_before)

    def test_invalid_manifest_types_fail_before_creating_runs(self):
        for field, value in [("version", True), ("project", []), ("tags", "integration")]:
            with self.subTest(field=field):
                original = self.case[field]
                self.case[field] = value
                self.write_case()
                completed = self.cli("list", "--cases-dir", str(self.cases),
                                     "--projects-dir", str(self.projects))
                self.assertEqual(completed.returncode, 2, completed.stderr)
                self.assertIn("Evaluation error:", completed.stderr)
                self.assertNotIn("Traceback", completed.stderr)
                self.case[field] = original
        self.assertFalse(self.results.exists())
        self.assertFalse(self.log.exists())

    def test_snapshot_excludes_environment_and_dependencies_without_changing_original(self):
        (self.source / ".env").write_text("EXAMPLE_TOKEN=fixture-only\n")
        (self.source / ".env.local").write_text("LOCAL=fixture-only\n")
        dependency = self.source / "node_modules/demo/index.js"
        dependency.parent.mkdir(parents=True)
        dependency.write_text("module.exports = 'fixture dependency'\n")
        original = {path.relative_to(self.source).as_posix(): path.read_bytes()
                    for path in self.source.rglob("*") if path.is_file()}
        completed = self.run_case()
        self.assertEqual(completed.returncode, 0, completed.stderr + completed.stdout)
        run_dir, _ = self.saved_run()
        for project in [run_dir / "inputs/projects/local-project", run_dir / "local-output/attempt-1/project"]:
            self.assertTrue((project / "source.txt").is_file())
            for relative in [".env", ".env.local", "node_modules"]:
                self.assertFalse((project / relative).exists())
        current = {path.relative_to(self.source).as_posix(): path.read_bytes()
                   for path in self.source.rglob("*") if path.is_file()}
        self.assertEqual(original, current)


@unittest.skipUnless(os.name == "posix" and hasattr(os, "fork"), "requires POSIX process groups")
class RunnerTimeoutTests(unittest.TestCase):
    def test_timeout_stops_child_that_ignores_sigterm_after_leader_exits(self):
        with tempfile.TemporaryDirectory(prefix="ai-docs-eval-timeout-") as directory:
            root = Path(directory).resolve()
            script = root / "forked-target.py"
            script.write_text(
                "import os, signal, time\n"
                "from pathlib import Path\n"
                "child = os.fork()\n"
                "if child == 0:\n"
                "    signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
                "    Path('child.pid').write_text(str(os.getpid()))\n"
                "    count = 0\n"
                "    while True:\n"
                "        Path('heartbeat').write_text(str(count))\n"
                "        count += 1\n"
                "        time.sleep(0.02)\n"
                "else:\n"
                "    while True: time.sleep(1)\n"
            )
            try:
                with self.assertRaises(runner.InfrastructureError):
                    runner.run_process([sys.executable, str(script)], root,
                                       root / "stdout.log", root / "stderr.log", 0.5)
                self.assertTrue((root / "child.pid").is_file(), "forked child did not start")
                time.sleep(0.1)
                heartbeat = (root / "heartbeat").read_text()
                time.sleep(0.15)
                self.assertEqual((root / "heartbeat").read_text(), heartbeat,
                                 "child continued mutating files after runner timeout")
            finally:
                if (root / "child.pid").is_file():
                    try:
                        os.kill(int((root / "child.pid").read_text()), signal.SIGKILL)
                    except ProcessLookupError:
                        pass


if __name__ == "__main__":
    unittest.main()
