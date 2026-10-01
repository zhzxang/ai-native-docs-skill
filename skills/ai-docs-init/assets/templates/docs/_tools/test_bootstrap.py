"""Behavioral tests for incremental AI documentation installation.

All installation and upgrade targets live in temporary directories. These tests
never execute a registered project command or migrate historical documents.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import docctl
import init_docs


KIT_ROOT = Path(__file__).resolve().parents[2]
MANIFEST = "docs/_system/installation.json"
BEGIN = "<!-- ai-docs-init:begin -->"
END = "<!-- ai-docs-init:end -->"


def snapshot(root: Path) -> dict:
    """Include bytes, directory layout and timestamps to detect unintended writes."""
    if not root.exists():
        return {}
    result = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            result[relative] = ("symlink", str(path.readlink()))
        elif path.is_file():
            result[relative] = ("file", path.read_bytes(), path.stat().st_mtime_ns)
        else:
            result[relative] = ("directory",)
    return result


class BootstrapTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="ai-docs-bootstrap-test-")
        self.work = Path(self.tmp.name).resolve()
        self.source = self.work / "kit"
        shutil.copytree(KIT_ROOT, self.source,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        self.target = self.work / "project"

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, relative: str, content: bytes | str, *, root: Path | None = None):
        path = (root or self.target) / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content.encode("utf-8") if isinstance(content, str) else content)
        return path

    def apply(self, **kwargs):
        return init_docs.bootstrap(self.source, self.target, dry_run=False, **kwargs)

    def manifest(self):
        return json.loads((self.target / MANIFEST).read_text())

    def upgrade_source(self):
        package = self.source / "docs/_system/package.json"
        data = json.loads(package.read_text())
        data["system_version"] = "2.0.0"
        package.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
        return data

    def test_new_project_installs_minimal_system_with_ownership_manifest(self):
        result = self.apply()
        self.assertTrue(result["applied"])
        self.assertEqual(result["mode"], "init")
        self.assertFalse(result["conflicts"])
        self.assertEqual(sorted(path.name for path in (self.target / "docs").iterdir()),
                         ["AGENTS.md", "README.md", "_system", "_templates", "_tools"])
        self.assertFalse((self.target / "docs/project").exists())
        manifest = self.manifest()
        self.assertEqual(manifest["system_version"],
                         json.loads((self.source / "docs/_system/package.json").read_text())["system_version"])
        self.assertIn("docs/_tools/docctl.py", manifest["owned_files"])
        for relative, record in manifest["owned_files"].items():
            self.assertEqual(record["sha256"], hashlib.sha256((self.target / relative).read_bytes()).hexdigest())

    def test_overview_requires_a_valid_title_and_summary_pair_without_writing(self):
        invalid = [
            {"overview_title": "用户提供的项目标题"},
            {"overview_summary": "用户提供的项目摘要"},
            {"overview_title": "   ", "overview_summary": "摘要"},
            {"overview_title": "标题", "overview_summary": "   "},
            {"overview_title": "第一行\n第二行", "overview_summary": "摘要"},
        ]
        for arguments in invalid:
            with self.subTest(arguments=arguments):
                with self.assertRaises(init_docs.InstallError):
                    self.apply(**arguments)
                self.assertFalse(self.target.exists())

    def test_explicit_overview_creates_only_an_unowned_draft_with_supplied_facts(self):
        arguments = {"overview_title": "用户提供的项目标题", "overview_summary": "用户提供的项目目的"}
        result = self.apply(**arguments)
        relative = "docs/project/overview.md"
        self.assertEqual(result["business_documents"], [relative])
        path = self.target / relative
        text = path.read_text()
        data = docctl.parse_frontmatter(text)
        self.assertEqual(data["status"], "draft")
        self.assertEqual(data["summary"], arguments["overview_summary"])
        self.assertIsNone(data["owner"])
        self.assertIsNone(data["verified_at"])
        self.assertIsNone(data["verification_ref"])
        self.assertIn("# " + arguments["overview_title"], text)
        self.assertEqual(sorted(path.name for path in (self.target / "docs/project").iterdir()),
                         ["overview.md"])
        self.assertFalse((self.target / "docs/engineering").exists())
        self.assertNotIn(relative, self.manifest()["owned_files"])
        self.assertNotIn(relative, self.manifest()["owned_blocks"])
        before = snapshot(self.target)
        repeated = self.apply(**arguments)
        self.assertEqual(repeated["status"], "noop")
        self.assertEqual(snapshot(self.target), before)

    def test_existing_overview_is_preserved_and_not_claimed(self):
        relative = "docs/project/overview.md"
        approved = b"# Existing approved overview\nOriginal project scope and decision evidence.\n"
        self.write(relative, approved)
        result = self.apply(overview_title="New requested title", overview_summary="New requested summary")
        self.assertEqual((self.target / relative).read_bytes(), approved)
        self.assertIn(relative, [conflict["path"] for conflict in result["conflicts"]])
        self.assertNotIn(relative, self.manifest()["owned_files"])
        self.assertNotIn(relative, self.manifest()["owned_blocks"])

    def test_adopt_preserves_all_existing_entries_and_historical_content(self):
        entries = {
            "README.md": b"# Product\r\nReal project facts without a final newline",
            "AGENTS.md": b"# Existing instructions\nRun only the documented checks.\n",
            "docs/README.md": b"# Historic docs\n[Architecture](architecture.md)\n",
            "docs/AGENTS.md": b"Keep approved historical records.\n",
        }
        for relative, original in entries.items():
            self.write(relative, original)
        self.write("docs/architecture.md", "# Architecture\nSource facts and original links.\n")
        self.write("docs/assets/diagram.bin", b"\x00\xff\x10asset")
        historic = {relative: (self.target / relative).read_bytes()
                    for relative in ("docs/architecture.md", "docs/assets/diagram.bin")}
        result = self.apply()
        self.assertEqual(result["mode"], "adopt")
        for relative, original in entries.items():
            data = (self.target / relative).read_bytes()
            self.assertTrue(data.startswith(original), relative)
            self.assertEqual(data.count(BEGIN.encode()), 1, relative)
            self.assertEqual(data.count(END.encode()), 1, relative)
        for relative, original in historic.items():
            self.assertEqual((self.target / relative).read_bytes(), original)
        self.assertFalse((self.target / "docs/engineering").exists())

    def test_install_does_not_infer_project_facts_or_commands(self):
        self.write("package.json", '{"name":"existing-app","scripts":{"test":"touch unsafe"}}\n')
        self.apply()
        self.assertEqual((self.target / "docs/_system/project-map.json").read_bytes(),
                         (self.source / "docs/_system/project-map.json").read_bytes())
        self.assertEqual((self.target / "docs/_system/commands.json").read_bytes(),
                         (self.source / "docs/_system/commands.json").read_bytes())
        self.assertFalse((self.target / "unsafe").exists())

    def test_scan_finds_historical_documents_without_mutating_or_traversing_dependencies(self):
        self.write("README.md", "# Existing product\n## Purpose\nOriginal prose.\n")
        self.write("docs/legacy/decision.md", "---\nid: OLD-1\n---\n# Approved decision\n")
        self.write("node_modules/package/README.md", "# Dependency documentation\n")
        before = snapshot(self.target)
        result = init_docs.scan(self.target)
        self.assertEqual(result["mode_hint"], "adopt")
        documents = {document["path"]: document for document in result["markdown_documents"]}
        self.assertEqual(documents["README.md"]["headings"], ["Existing product", "Purpose"])
        self.assertTrue(documents["docs/legacy/decision.md"]["has_doc_meta"])
        self.assertNotIn("node_modules/package/README.md", documents)
        self.assertEqual(snapshot(self.target), before)

    def test_repeated_install_is_noop_including_timestamps_and_manifest(self):
        self.write("README.md", "# Existing project\n")
        self.apply()
        before = snapshot(self.target)
        result = self.apply()
        self.assertEqual(result["status"], "noop")
        self.assertFalse(result["actions"])
        self.assertEqual(snapshot(self.target), before)

    def test_default_bootstrap_and_plan_leave_new_target_absent(self):
        plan = init_docs.plan_install(self.source, self.target)
        self.assertEqual(plan["mode"], "init")
        self.assertTrue(plan["actions"])
        self.assertFalse(self.target.exists())
        result = init_docs.bootstrap(self.source, self.target)
        self.assertFalse(result["applied"])
        self.assertFalse(self.target.exists())

    def test_dry_run_does_not_change_an_existing_project(self):
        self.write("README.md", "# Existing product\n")
        self.write("docs/history.md", "Do not relocate this approved record.\n")
        before = snapshot(self.target)
        result = init_docs.bootstrap(self.source, self.target, dry_run=True)
        self.assertEqual(result["mode"], "adopt")
        self.assertTrue(result["actions"])
        self.assertEqual(snapshot(self.target), before)

    def test_upgrade_updates_unedited_system_assets_and_version(self):
        self.apply()
        relative = "docs/_system/writing-policy.md"
        new = (self.source / relative).read_bytes() + b"\nNew package policy.\n"
        self.write(relative, new, root=self.source)
        self.upgrade_source()
        result = self.apply(mode="upgrade")
        self.assertEqual(result["mode"], "upgrade")
        self.assertFalse(result["conflicts"])
        self.assertEqual((self.target / relative).read_bytes(), new)
        self.assertEqual(self.manifest()["system_version"], "2.0.0")
        self.assertEqual(self.manifest()["owned_files"][relative]["sha256"],
                         hashlib.sha256(new).hexdigest())

    def test_upgrade_preserves_modified_asset_and_reports_conflict(self):
        self.apply()
        relative = "docs/_system/writing-policy.md"
        original_record = self.manifest()["owned_files"][relative]
        local = (self.target / relative).read_bytes() + b"\nLocal project rules.\n"
        self.write(relative, local)
        self.write(relative, b"Upstream replacement policy.\n", root=self.source)
        self.upgrade_source()
        result = self.apply(mode="upgrade")
        self.assertIn(relative, [conflict["path"] for conflict in result["conflicts"]])
        self.assertEqual((self.target / relative).read_bytes(), local)
        self.assertEqual(self.manifest()["owned_files"][relative], original_record)

    def test_upgrade_keeps_confirmed_project_map_and_command_facts(self):
        self.apply()
        project_path = self.target / "docs/_system/project-map.json"
        project = json.loads(project_path.read_text())
        project["project"]["name"] = "Confirmed existing product"
        project["locations"][0]["paths"] = ["src/application.py"]
        project_path.write_text(json.dumps(project, ensure_ascii=False))
        commands_path = self.target / "docs/_system/commands.json"
        commands = json.loads(commands_path.read_text())
        commands["commands"][0].update({"argv": ["python3", "-m", "venv", ".venv"],
                                       "cwd": ".", "verification_ref": "record:setup-reviewed"})
        commands_path.write_text(json.dumps(commands, ensure_ascii=False))
        facts = {path: path.read_bytes() for path in (project_path, commands_path)}
        self.upgrade_source()
        self.apply(mode="upgrade")
        for path, content in facts.items():
            self.assertEqual(path.read_bytes(), content)

    def test_upgrade_keeps_edits_outside_managed_entry_block(self):
        self.write("docs/README.md", "# Real project docs\nOriginal facts.\n")
        self.apply()
        path = self.target / "docs/README.md"
        path.write_bytes(path.read_bytes() + b"\nNew project fact outside managed block.\n")
        self.write("docs/_README.md", "# New upstream entry\nUpdated system navigation.\n", root=self.source)
        self.upgrade_source()
        result = self.apply(mode="upgrade")
        text = path.read_text()
        self.assertIn("Original facts.", text)
        self.assertIn("New project fact outside managed block.", text)
        self.assertIn("Updated system navigation.", text)
        self.assertEqual(text.count(BEGIN), 1)
        self.assertNotIn("docs/README.md", [conflict["path"] for conflict in result["conflicts"]])

    def test_upgrade_protects_edits_inside_managed_entry_block(self):
        self.write("AGENTS.md", "# Local rules\n")
        self.apply()
        path = self.target / "AGENTS.md"
        content = path.read_text().replace(BEGIN, BEGIN + "\nManual block customization.", 1)
        path.write_text(content)
        baseline = self.manifest()["owned_blocks"]["AGENTS.md"]
        self.write("_AGENTS.md", "# Upstream replacement\n", root=self.source)
        self.upgrade_source()
        result = self.apply(mode="upgrade")
        self.assertIn("AGENTS.md", [conflict["path"] for conflict in result["conflicts"]])
        self.assertEqual(path.read_text(), content)
        self.assertEqual(self.manifest()["owned_blocks"]["AGENTS.md"], baseline)

    def test_unknown_system_file_collision_is_not_overwritten_or_claimed(self):
        relative = "docs/_tools/docctl.py"
        local = b"# Existing unrelated tool with the same name.\n"
        self.write(relative, local)
        result = self.apply(mode="adopt")
        self.assertEqual(result["status"], "partial")
        self.assertEqual((self.target / relative).read_bytes(), local)
        self.assertIn(relative, [conflict["path"] for conflict in result["conflicts"]])
        self.assertNotIn(relative, self.manifest()["owned_files"])

    def test_existing_unowned_matching_asset_is_not_claimed(self):
        relative = "docs/_templates/feature.md"
        local = (self.source / relative).read_bytes()
        self.write(relative, local)
        self.apply(mode="adopt")
        self.assertEqual((self.target / relative).read_bytes(), local)
        self.assertNotIn(relative, self.manifest()["owned_files"])

    def test_schema_one_registry_blocks_mixed_installation_without_writing(self):
        self.write("README.md", "# Legacy project\n")
        self.write("docs/_system/collections.json", '{"schema_version":1,"collections":[]}\n')
        self.write("docs/_tools/docctl.py", "# Legacy registry writer\n")
        before = snapshot(self.target)
        result = self.apply(mode="adopt")
        self.assertEqual(result["status"], "blocked")
        self.assertFalse(result["applied"])
        self.assertFalse(result["actions"])
        self.assertEqual(snapshot(self.target), before)
        self.assertFalse((self.target / MANIFEST).exists())

    def test_schema_one_routes_alone_also_block_mixed_installation(self):
        self.write("docs/_system/routes.json", '{"schema_version":1,"routes":[]}\n')
        before = snapshot(self.target)
        result = self.apply()
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(snapshot(self.target), before)

    def test_destination_symlink_cannot_write_outside_project(self):
        self.target.mkdir()
        outside = self.work / "outside"
        outside.mkdir()
        (self.target / "docs").symlink_to(outside, target_is_directory=True)
        before = snapshot(self.target)
        with self.assertRaises(init_docs.InstallError):
            self.apply()
        self.assertEqual(snapshot(self.target), before)
        self.assertEqual(snapshot(outside), {})

    def test_symlink_entry_is_not_followed_or_replaced(self):
        self.target.mkdir()
        outside = self.write("outside.txt", "Existing outside content.\n", root=self.work)
        (self.target / "README.md").symlink_to(outside)
        with self.assertRaises(init_docs.InstallError):
            self.apply()
        self.assertEqual(outside.read_text(), "Existing outside content.\n")
        self.assertTrue((self.target / "README.md").is_symlink())
        self.assertFalse((self.target / "docs").exists())

    def test_symlink_project_root_is_rejected_without_following_it(self):
        outside = self.work / "outside-project"
        outside.mkdir()
        self.target.symlink_to(outside, target_is_directory=True)
        with self.assertRaises(init_docs.InstallError):
            self.apply()
        self.assertTrue(self.target.is_symlink())
        self.assertEqual(snapshot(outside), {})

    def test_source_symlink_is_rejected_before_any_target_write(self):
        original = self.source / "docs/_templates/feature.md"
        outside = self.work / "source-outside.md"
        original.rename(outside)
        original.symlink_to(outside)
        with self.assertRaises(init_docs.InstallError):
            self.apply()
        self.assertFalse(self.target.exists())

    def test_target_inside_source_package_is_rejected(self):
        target = self.source / "nested-project"
        with self.assertRaises(init_docs.InstallError):
            init_docs.bootstrap(self.source, target, dry_run=False)
        self.assertFalse(target.exists())

    def test_stale_plan_does_not_overwrite_new_project_content(self):
        self.write("README.md", "# Original project\n")
        plan = init_docs.plan_install(self.source, self.target)
        self.write("README.md", "# Edited after planning\n")
        before = snapshot(self.target)
        try:
            result = init_docs.bootstrap(self.source, self.target, plan=plan, dry_run=False)
        except init_docs.InstallError:
            pass
        else:
            self.assertEqual(result["status"], "blocked")
            self.assertFalse(result["applied"])
        self.assertEqual(snapshot(self.target), before)

    def test_concurrent_install_lock_prevents_partial_writes(self):
        self.write("README.md", "# Local project\n")
        self.write(".ai-docs-init.lock", "Another installer is active.\n")
        before = snapshot(self.target)
        try:
            result = self.apply()
        except init_docs.InstallError:
            pass
        else:
            self.assertEqual(result["status"], "blocked")
            self.assertFalse(result["applied"])
        self.assertEqual(snapshot(self.target), before)

    def test_manifest_path_traversal_is_blocked_without_writing(self):
        self.apply()
        outside = self.write("outside.md", "Outside file must remain unchanged.\n", root=self.work)
        data = self.manifest()
        data["owned_files"]["../outside.md"] = {
            "sha256": hashlib.sha256(outside.read_bytes()).hexdigest()
        }
        self.write(MANIFEST, json.dumps(data))
        before = snapshot(self.target)
        try:
            result = self.apply(mode="upgrade")
        except init_docs.InstallError:
            pass
        else:
            self.assertEqual(result["status"], "blocked")
            self.assertFalse(result["applied"])
        self.assertEqual(snapshot(self.target), before)
        self.assertEqual(outside.read_text(), "Outside file must remain unchanged.\n")

    def test_manifest_block_ownership_outside_entry_files_is_blocked_without_writing(self):
        self.apply()
        relative = "docs/history.md"
        history = self.write(relative, "# Approved historical record\nOriginal evidence.\n")
        data = self.manifest()
        data["owned_blocks"][relative] = {
            "id": "ai-docs-init", "sha256": hashlib.sha256(history.read_bytes()).hexdigest()
        }
        self.write(MANIFEST, json.dumps(data))
        before = snapshot(self.target)
        try:
            result = self.apply(mode="upgrade")
        except init_docs.InstallError:
            pass
        else:
            self.assertEqual(result["status"], "blocked")
            self.assertFalse(result["applied"])
            self.assertFalse(result["actions"])
        self.assertEqual(snapshot(self.target), before)

    def test_manifest_unknown_block_id_is_blocked_without_writing(self):
        self.apply()
        data = self.manifest()
        data["owned_blocks"]["AGENTS.md"]["id"] = "another-tool"
        self.write(MANIFEST, json.dumps(data))
        before = snapshot(self.target)
        try:
            result = self.apply(mode="upgrade")
        except init_docs.InstallError:
            pass
        else:
            self.assertEqual(result["status"], "blocked")
            self.assertFalse(result["applied"])
            self.assertFalse(result["actions"])
        self.assertEqual(snapshot(self.target), before)

    def test_failed_application_restores_existing_content_and_removes_new_files(self):
        self.write("README.md", b"# Local project\r\nOriginal approved facts.\r\n")
        self.write("docs/historical.md", "Historical approved content.\n")
        before = {path.relative_to(self.target).as_posix(): path.read_bytes()
                  for path in self.target.rglob("*") if path.is_file()}
        original = init_docs._atomic_write
        calls = 0

        def fail_midway(path, content, *, create):
            nonlocal calls
            calls += 1
            if calls == 4:
                raise OSError("Simulated storage failure")
            return original(path, content, create=create)

        with mock.patch.object(init_docs, "_atomic_write", side_effect=fail_midway):
            with self.assertRaises((init_docs.InstallError, OSError)):
                self.apply()
        after = {path.relative_to(self.target).as_posix(): path.read_bytes()
                 for path in self.target.rglob("*") if path.is_file()}
        self.assertEqual(after, before)
        self.assertFalse((self.target / ".ai-docs-init.lock").exists())


if __name__ == "__main__":
    unittest.main()
