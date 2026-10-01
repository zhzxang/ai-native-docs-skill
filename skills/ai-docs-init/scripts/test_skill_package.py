"""Smoke tests for a portable skill package and its reviewed-plan CLI."""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

SKILL_ROOT = Path(__file__).resolve().parents[1]


class PortablePackageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="ai-docs-skill-test-")
        self.work = Path(self.tmp.name).resolve()
        self.skill = self.work / "detached/ai-docs-init"
        shutil.copytree(SKILL_ROOT, self.skill, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        self.target = self.work / "project"
        self.plan = self.work / "plan.json"

    def tearDown(self):
        self.tmp.cleanup()

    def run_cli(self, *args):
        return subprocess.run([sys.executable, "-B", str(self.skill / "scripts/bootstrap.py"),
                               "--target", str(self.target), *args], cwd=self.work,
                              text=True, capture_output=True)

    def test_detached_package_previews_and_applies_same_plan(self):
        preview = self.run_cli("--plan-file", str(self.plan))
        self.assertEqual(preview.returncode, 0, preview.stderr)
        output = json.loads(preview.stdout)
        self.assertFalse(output["applied"])
        self.assertNotIn("_payloads", output)
        self.assertFalse(self.target.exists())
        applied = self.run_cli("--apply", "--plan-file", str(self.plan))
        self.assertEqual(applied.returncode, 0, applied.stdout + applied.stderr)
        result = json.loads(applied.stdout)
        self.assertTrue(result["applied"])
        self.assertTrue(result["validation"]["structure"]["ok"])
        self.assertFalse(result["validation"]["strict"]["ok"])
        self.assertTrue((self.target / "docs/_system/installation.json").is_file())
        self.assertFalse((self.target / "docs/product").exists())

    def test_same_package_repeated_application_is_noop(self):
        first = self.run_cli("--apply")
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        files = {p.relative_to(self.target): p.read_bytes() for p in self.target.rglob("*") if p.is_file()}
        repeated = self.run_cli("--apply")
        self.assertEqual(repeated.returncode, 0, repeated.stdout + repeated.stderr)
        self.assertEqual(json.loads(repeated.stdout)["status"], "noop")
        self.assertEqual(files, {p.relative_to(self.target): p.read_bytes()
                                for p in self.target.rglob("*") if p.is_file()})

    def test_target_changes_invalidate_saved_plan(self):
        self.target.mkdir()
        (self.target / "README.md").write_text("Original project facts.\n")
        self.assertEqual(self.run_cli("--plan-file", str(self.plan)).returncode, 0)
        (self.target / "README.md").write_text("Concurrent project facts.\n")
        applied = self.run_cli("--apply", "--plan-file", str(self.plan))
        self.assertNotEqual(applied.returncode, 0)
        self.assertEqual((self.target / "README.md").read_text(), "Concurrent project facts.\n")
        self.assertFalse((self.target / "docs/_system/installation.json").exists())

    def test_saved_plan_for_another_target_is_rejected(self):
        self.assertEqual(self.run_cli("--plan-file", str(self.plan)).returncode, 0)
        data = json.loads(self.plan.read_text())
        data["target"] = str(self.work / "different-project")
        self.plan.write_text(json.dumps(data))
        result = self.run_cli("--apply", "--plan-file", str(self.plan))
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.target.exists())

    def test_scan_does_not_initialize_project(self):
        self.target.mkdir()
        (self.target / "README.md").write_text("# Existing project\n")
        result = self.run_cli("--scan")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["mode_hint"], "adopt")
        self.assertEqual(sorted(p.name for p in self.target.iterdir()), ["README.md"])

    def test_plan_cannot_be_stored_in_target_project(self):
        result = self.run_cli("--plan-file", str(self.target / "plan.json"))
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.target.exists())

    def test_cli_rejects_target_symlink_before_writing(self):
        outside = self.work / "outside"
        outside.mkdir()
        self.target.symlink_to(outside, target_is_directory=True)
        result = self.run_cli("--apply")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(list(outside.iterdir()), [])

    def test_summary_keeps_complete_review_plan_and_applies_it(self):
        preview = self.run_cli("--summary", "--plan-file", str(self.plan))
        self.assertEqual(preview.returncode, 0, preview.stderr)
        summary = json.loads(preview.stdout)
        complete = json.loads(self.plan.read_text())
        self.assertNotIn("actions", summary)
        self.assertEqual(summary["action_counts"]["create"], len(complete["actions"]))
        self.assertEqual(sum(summary["created_groups"].values()), len(complete["actions"]))
        self.assertEqual(len(complete["_payloads"]), len(complete["actions"]))
        applied = self.run_cli("--summary", "--apply", "--plan-file", str(self.plan))
        self.assertEqual(applied.returncode, 0, applied.stdout + applied.stderr)
        result = json.loads(applied.stdout)
        self.assertTrue(result["validation"]["structure"]["ok"])
        self.assertEqual(result["action_counts"], summary["action_counts"])
        self.assertEqual(result["conflicts"], complete["conflicts"])


if __name__ == "__main__":
    unittest.main()
