"""Observable code-sync behavior, resource portability and safe reviewed writes."""
import importlib.util
import base64
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / "skills/ai-docs-sync/scripts"
SOURCE = ROOT / "skills/ai-docs-check/assets/templates"
spec = importlib.util.spec_from_file_location("code_sync_tested", HERE / "sync.py")
sync = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sync)


class SyncTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="ai-docs-sync-test-")
        self.root = Path(self.temp.name).resolve() / "project"
        self.root.mkdir()
        (self.root / "src").mkdir()
        (self.root / "src/main.py").write_text("print('Hello')\n")
        (self.root / "package.json").write_text(json.dumps({
            "name": "fixture", "engines": {"node": ">=20"},
            "packageManager": "npm@10", "scripts": {"test": "exit 77"}}))
        self.installer, self.docctl = sync.modules(SOURCE)
        self.installer.bootstrap(SOURCE, self.root, dry_run=False)

    def tearDown(self):
        self.temp.cleanup()

    def files(self):
        return {p.relative_to(self.root).as_posix(): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}

    def test_preview_is_readonly_apply_creates_only_minimum_drafts(self):
        before = self.files()
        plan = sync.plan_sync(SOURCE, self.root)
        self.assertEqual(self.files(), before)
        self.assertEqual(len(plan["actions"]), 2)
        result = sync.apply_sync(SOURCE, self.root, plan)
        self.assertTrue(result["validation"]["ok"], result["validation"])
        records = self.docctl.collect_records(self.root)
        self.assertEqual({r["type"] for r in records}, {"architecture-overview", "development-guide"})
        for record in records:
            self.assertEqual(record["status"], "draft")
            self.assertIsNone(record["verified_at"])
            self.assertIsNone(record["verification_ref"])
        self.assertEqual((self.root / "docs/.ai-docs.json").read_bytes(), before["docs/.ai-docs.json"])
        self.assertIn('"test": "exit 77"', (self.root / sync.SLOTS["development-guide"][0]).read_text())

    def test_repeat_is_noop_and_source_change_refreshes_owned_document(self):
        sync.apply_sync(SOURCE, self.root, sync.plan_sync(SOURCE, self.root))
        original = self.files()
        repeat = sync.plan_sync(SOURCE, self.root)
        self.assertEqual(repeat["status"], "noop")
        sync.apply_sync(SOURCE, self.root, repeat)
        self.assertEqual(self.files(), original)
        (self.root / "src/main.py").write_text("print('Changed')\n")
        plan = sync.plan_sync(SOURCE, self.root)
        self.assertEqual({item["operation"] for item in plan["actions"]}, {"update"})
        self.assertTrue(sync.apply_sync(SOURCE, self.root, plan)["validation"]["ok"])

    def test_local_edits_and_same_type_elsewhere_are_preserved(self):
        sync.apply_sync(SOURCE, self.root, sync.plan_sync(SOURCE, self.root))
        architecture = self.root / sync.SLOTS["architecture-overview"][0]
        text = architecture.read_text() + "\n人工确认的模块职责。\n"
        architecture.write_text(text)
        quickstart = self.root / sync.SLOTS["development-guide"][0]
        moved = self.root / "docs/local-development.md"
        quickstart.rename(moved)
        plan = sync.plan_sync(SOURCE, self.root)
        self.assertEqual(plan["status"], "noop")
        self.assertEqual(len(plan["preserved"]), 2)
        sync.apply_sync(SOURCE, self.root, plan)
        self.assertEqual(architecture.read_text(), text)
        self.assertTrue(moved.exists())
        self.assertFalse(quickstart.exists())

    def test_code_changes_or_new_docs_invalidate_reviewed_plan(self):
        for mutation in (lambda: (self.root / "src/main.py").write_text("changed\n"),
                         lambda: (self.root / "src/new.py").write_text("new\n"),
                         lambda: (self.root / "docs/legacy.md").write_text("# Original facts\n")):
            with self.subTest(mutation=mutation):
                plan = sync.plan_sync(SOURCE, self.root)
                mutation()
                before = self.files()
                with self.assertRaises(sync.SyncError):
                    sync.apply_sync(SOURCE, self.root, plan)
                self.assertEqual(self.files(), before)

    def test_failure_rolls_back_all_created_documents(self):
        plan = sync.plan_sync(SOURCE, self.root)
        before = self.files()
        original_write = self.installer._atomic_write
        calls = 0

        def fail_second(path, content, *, create):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("simulated disk failure")
            return original_write(path, content, create=create)

        with patch.object(self.installer, "_atomic_write", fail_second), patch.object(
                sync, "modules", return_value=(self.installer, self.docctl)):
            with self.assertRaises(OSError):
                sync.apply_sync(SOURCE, self.root, plan)
        self.assertEqual(self.files(), before)
        self.assertFalse((self.root / "docs/engineering").exists())

    def test_concurrent_source_change_during_apply_rolls_back_drafts(self):
        plan = sync.plan_sync(SOURCE, self.root)
        original_write = self.installer._atomic_write

        def change_source(path, content, *, create):
            original_write(path, content, create=create)
            (self.root / "src/main.py").write_text("Concurrent source update\n")

        with patch.object(self.installer, "_atomic_write", change_source), patch.object(
                sync, "modules", return_value=(self.installer, self.docctl)):
            with self.assertRaises(sync.SyncError):
                sync.apply_sync(SOURCE, self.root, plan)
        self.assertFalse((self.root / "docs/engineering").exists())
        self.assertEqual((self.root / "src/main.py").read_text(), "Concurrent source update\n")

    def test_total_init_separation_and_optional_explicit_overview(self):
        new = self.root.parent / "new"
        new.mkdir()
        with self.assertRaises(sync.SyncError):
            sync.plan_sync(SOURCE, new)
        self.assertEqual(list(new.iterdir()), [])
        plan = sync.plan_sync(SOURCE, self.root, overview_title="确认的项目", overview_summary="用户明确提供的项目概况。")
        self.assertEqual(len(plan["actions"]), 3)
        result = sync.apply_sync(SOURCE, self.root, plan)
        self.assertTrue(result["validation"]["ok"])
        overview = self.root / sync.SLOTS["project-overview"][0]
        self.assertIn("用户明确提供", overview.read_text())
        self.assertIsNone(self.docctl.parse_frontmatter(overview.read_text())["approved_by"])

    def test_symlink_destination_and_cooperative_lock_block_writes(self):
        outside = self.root.parent / "outside"
        outside.mkdir()
        (self.root / "docs/engineering").symlink_to(outside, target_is_directory=True)
        with self.assertRaises(ValueError):
            sync.plan_sync(SOURCE, self.root)
        self.assertEqual(list(outside.iterdir()), [])
        (self.root / "docs/engineering").unlink()
        plan = sync.plan_sync(SOURCE, self.root)
        lock = self.root / "docs/.docctl.lock"
        lock.write_text("other writer")
        before = self.files()
        with self.assertRaises(OSError):
            sync.apply_sync(SOURCE, self.root, plan)
        self.assertEqual(self.files(), before)

    def test_invalid_manifest_fails_without_doc_writes(self):
        (self.root / "package.json").write_text('{"scripts": null}')
        before = self.files()
        with self.assertRaises(sync.SyncError):
            sync.plan_sync(SOURCE, self.root)
        self.assertEqual(self.files(), before)

    def test_uncommon_code_and_manifest_routes_have_minimum_drafts(self):
        (self.root / "src/main.py").unlink()
        (self.root / "package.json").unlink()
        (self.root / "src/main.exs").write_text('IO.puts("Hi")\n')
        self.assertEqual(len(sync.plan_sync(SOURCE, self.root)["actions"]), 2)
        (self.root / "src/main.exs").unlink()
        (self.root / "pom.xml").write_text("<project />\n")
        self.assertEqual(len(sync.plan_sync(SOURCE, self.root)["actions"]), 2)

    def test_reviewed_plan_cannot_claim_introduced_link_error_as_baseline(self):
        plan = sync.plan_sync(SOURCE, self.root)
        action = plan["actions"][0]
        relative = action["path"]
        original = base64.b64decode(plan["_payloads"][relative]).decode()
        text = sync.marked(sync.original_text(original) + "\n[bad](not-real.md)\n")
        plan["_payloads"][relative] = base64.b64encode(text.encode()).decode()
        action["after_sha256"] = sync.sha(text.encode())
        plan["baseline_errors"] += self.docctl.relative_link_errors(self.root, self.root / relative, text)
        before = self.files()
        with self.assertRaises(sync.SyncError):
            sync.apply_sync(SOURCE, self.root, plan)
        self.assertEqual(self.files(), before)


if __name__ == "__main__":
    unittest.main()
