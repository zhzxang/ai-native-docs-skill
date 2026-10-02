"""Detached four-Skill workflows using one shared resource package."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "skills"


class SkillSetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="ai-docs-skill-set-")
        self.work = Path(self.temp.name).resolve()
        self.skills = self.work / "detached"
        for name in ("ai-docs-init", "ai-docs-sync", "ai-docs-migrate", "ai-docs-check"):
            shutil.copytree(SKILLS / name, self.skills / name,
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        self.target = self.work / "project"
        self.resource_files = self.resource_snapshot()

    def tearDown(self):
        self.temp.cleanup()

    def command(self, skill, script, *args, expected=0):
        environment = os.environ.copy()
        environment.pop("PYTHONDONTWRITEBYTECODE", None)
        result = subprocess.run([sys.executable, str(self.skills / skill / "scripts" / script), *args],
                                cwd=self.work, env=environment, text=True, capture_output=True)
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        self.assertEqual(self.resource_snapshot(), self.resource_files)
        return json.loads(result.stdout)

    def resource_snapshot(self):
        resources = self.skills / "ai-docs-check/assets/templates"
        return {path.relative_to(resources).as_posix(): (path.read_bytes(), path.stat().st_mtime_ns)
                for path in resources.rglob("*") if path.is_file()}

    def test_code_only_init_then_separate_sync_and_check(self):
        self.target.mkdir()
        (self.target / "main.py").write_text("print('hello')\n")
        result = self.command("ai-docs-init", "bootstrap.py", "--target", str(self.target), "--apply")
        self.assertEqual(result["follow_up"], "sync_minimum_docs")
        self.assertFalse((self.target / "docs/engineering").exists())
        plan = self.work / "sync.json"
        self.command("ai-docs-sync", "sync.py", "--target", str(self.target), "--plan-file", str(plan))
        synced = self.command("ai-docs-sync", "sync.py", "--target", str(self.target), "--apply", "--plan-file", str(plan))
        self.assertTrue(synced["validation"]["ok"])
        self.assertTrue(self.command("ai-docs-check", "check.py", "--root", str(self.target), "check")["ok"])
        checked = self.command("ai-docs-check", "check.py", "check-meta",
                               str(self.target / "docs/engineering/architecture/overview.md"),
                               str(self.target / "docs/engineering/development/quickstart.md"))
        self.assertEqual(checked["records"], 2)
        self.assertTrue(checked["ok"])

    def test_historical_docs_init_routes_and_does_not_migrate(self):
        self.target.mkdir()
        (self.target / "legacy.md").write_text("# Existing system behavior\n\nKeep these facts.\n")
        result = self.command("ai-docs-init", "bootstrap.py", "--target", str(self.target), "--apply")
        self.assertEqual(result["follow_up"], "ask_user_migration")
        self.assertEqual((self.target / "legacy.md").read_text(), "# Existing system behavior\n\nKeep these facts.\n")
        self.assertFalse((self.target / "docs/product").exists())

    def test_meta_check_is_independent_from_init(self):
        candidate = self.work / "candidate.md"
        candidate.write_text('---\nid: "FEATURE-1"\ntype: "feature"\nstatus: "draft"\n---\n\n# Invalid meta\n')
        checked = self.command("ai-docs-check", "check.py", "check-meta", str(candidate), expected=1)
        self.assertFalse(checked["ok"])
        self.assertTrue(checked["errors"])
        self.assertFalse(self.target.exists())


if __name__ == "__main__":
    unittest.main()
