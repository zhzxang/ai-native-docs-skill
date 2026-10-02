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

ROOT = Path(__file__).resolve().parents[1]
KIT_ROOT = ROOT / "skills/ai-docs-check/assets/templates"
sys.path.insert(0, str(KIT_ROOT / "docs/_tools"))
import init_docs


CONFIG = "docs/.ai-docs.json"
LEGACY_MANIFEST = "docs/_system/installation.json"
ENTRY_FILES = {"README.md", "AGENTS.md", "docs/README.md", "docs/AGENTS.md"}
LIGHT_FILES = ENTRY_FILES | {CONFIG}
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
        self.system_version = json.loads((self.source / "docs/_system/package.json").read_text())["system_version"]
        major, minor, _ = self.system_version.split(".")
        self.upgraded_version = f"{major}.{int(minor) + 1}.0"
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
        return json.loads((self.target / CONFIG).read_text())["installation"]

    def upgrade_source(self):
        package = self.source / "docs/_system/package.json"
        data = json.loads(package.read_text())
        data["system_version"] = self.upgraded_version
        package.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
        return data

    def config(self):
        return json.loads((self.target / CONFIG).read_text())

    def assert_light_layout(self):
        self.assertEqual({path.relative_to(self.target).as_posix() for path in self.target.rglob("*")
                          if path.is_file()}, LIGHT_FILES)
        self.assertEqual(sorted(path.name for path in (self.target / "docs").iterdir()),
                         [".ai-docs.json", "AGENTS.md", "README.md"])
        for folder in ("_system", "_tools", "_templates"):
            self.assertFalse((self.target / "docs" / folder).exists())

    def legacy_project(self):
        """Recreate a previous full install using baselines recorded before customization."""
        owned_files = {}
        for name in ("_system", "_tools", "_templates"):
            for source in sorted((self.source / "docs" / name).rglob("*")):
                if not source.is_file() or "__pycache__" in source.parts or source.suffix == ".pyc":
                    continue
                relative = source.relative_to(self.source).as_posix()
                self.write(relative, source.read_bytes())
                owned_files[relative] = {"sha256": hashlib.sha256(source.read_bytes()).hexdigest()}
        entries = {"_README.md": "README.md", "_AGENTS.md": "AGENTS.md",
                   "docs/_README.md": "docs/README.md", "docs/_AGENTS.md": "docs/AGENTS.md"}
        owned_blocks = {}
        for source, relative in entries.items():
            block = (BEGIN + "\n" + (self.source / source).read_text().strip() + "\n" + END + "\n")
            self.write(relative, block)
            owned_blocks[relative] = {"id": "ai-docs-init", "sha256": hashlib.sha256(block.encode()).hexdigest()}
        self.write(LEGACY_MANIFEST, json.dumps({"schema_version": 1, "system_version": "1.0.0",
                   "status": "installed", "owned_files": owned_files, "owned_blocks": owned_blocks}))
        return owned_files

    def test_new_project_installs_exactly_four_entries_and_one_sparse_configuration(self):
        source_before = snapshot(self.source)
        result = self.apply()
        self.assertTrue(result["applied"])
        self.assertEqual(result["mode"], "init")
        self.assertFalse(result["conflicts"])
        self.assert_light_layout()
        config = self.config()
        self.assertEqual(config["schema_version"], 1)
        self.assertEqual(config["system"], {"name": "ai-docs-system", "version": self.system_version})
        self.assertEqual(config.get("locations", []), [])
        self.assertEqual(config.get("commands", []), [])
        self.assertNotIn("owned_files", self.manifest())
        self.assertEqual(set(self.manifest()["owned_blocks"]), ENTRY_FILES)
        for relative, record in self.manifest()["owned_blocks"].items():
            raw = (self.target / relative).read_bytes()
            self.assertIn(BEGIN.encode(), raw)
            self.assertIn(END.encode(), raw)
            self.assertEqual(record["sha256"], hashlib.sha256(raw).hexdigest())
        self.assertEqual(snapshot(self.source), source_before)

    def test_overview_options_are_rejected_with_the_independent_sync_entry(self):
        options = [
            {"overview_title": "用户提供的项目标题"},
            {"overview_summary": "用户提供的项目摘要"},
            {"overview_title": "   ", "overview_summary": "摘要"},
            {"overview_title": "标题", "overview_summary": "   "},
            {"overview_title": "第一行\n第二行", "overview_summary": "摘要"},
            {"overview_title": "标题", "overview_summary": "明确提供的摘要"},
            {"overview_title": ""},
        ]
        for arguments in options:
            with self.subTest(arguments=arguments):
                with self.assertRaisesRegex(init_docs.InstallError, "ai-docs-sync/scripts/sync.py"):
                    self.apply(**arguments)
                self.assertFalse(self.target.exists())

    def test_saved_plan_does_not_silently_ignore_overview_options(self):
        plan = init_docs.plan_install(self.source, self.target)
        with self.assertRaisesRegex(init_docs.InstallError, "ai-docs-sync/scripts/sync.py"):
            self.apply(plan=plan, overview_title="标题", overview_summary="摘要")
        self.assertFalse(self.target.exists())

    def test_init_mode_safely_merges_the_same_minimum_into_an_existing_code_project(self):
        readme = b"# Existing product\r\nOriginal project facts.\r\n"
        self.write("README.md", readme)
        self.write("src/app.py", "print('existing code')\n")
        result = self.apply(mode="init")
        self.assertEqual(result["mode"], "init")
        self.assertEqual(result["operation"], "initialize")
        self.assertEqual(result["status"], "installed")
        self.assertEqual(result["follow_up"], "sync_minimum_docs")
        self.assertEqual(result["business_documents"], [])
        self.assertTrue((self.target / "README.md").read_bytes().startswith(readme))
        self.assertEqual((self.target / "src/app.py").read_text(), "print('existing code')\n")
        self.assertFalse((self.target / "docs/project").exists())
        before = snapshot(self.target)
        repeated = self.apply(mode="init")
        self.assertEqual(repeated["status"], "noop")
        self.assertEqual(repeated["follow_up"], "sync_minimum_docs")
        self.assertEqual(snapshot(self.target), before)

    def test_existing_overview_is_preserved_and_routed_without_being_claimed(self):
        relative = "docs/project/overview.md"
        approved = b"# Existing approved overview\nOriginal project scope and decision evidence.\n"
        self.write(relative, approved)
        result = self.apply()
        self.assertEqual((self.target / relative).read_bytes(), approved)
        self.assertEqual(result["follow_up"], "ask_user_migration")
        self.assertNotIn(relative, self.manifest().get("owned_files", {}))
        self.assertNotIn(relative, self.manifest()["owned_blocks"])

    def test_empty_minimum_and_navigation_only_documents_do_not_trigger_follow_up(self):
        result = self.apply()
        self.assertIsNone(result["follow_up"])
        inventory = init_docs.scan(self.target)
        self.assertEqual(inventory["documentation_state"], "navigation_only")
        self.assertEqual(inventory["historical_documents"], [])
        self.assertEqual(inventory["business_documents"], [])
        self.assertEqual(inventory["readme_evidence"], [])

    def test_standard_business_documents_do_not_ask_for_history_migration(self):
        self.write("src/app.py", "pass\n")
        self.write("docs/project/overview.md", "---\nid: PROJECT-OVERVIEW\ntype: project-overview\n---\n# Product\n")
        result = self.apply()
        inventory = init_docs.scan(self.target)
        self.assertIsNone(result["follow_up"])
        self.assertEqual(inventory["documentation_state"], "documented")
        self.assertEqual(inventory["business_documents"], ["docs/project/overview.md"])
        self.assertEqual(inventory["historical_documents"], [])

    def test_readme_facts_are_evidence_but_do_not_count_as_business_documents(self):
        self.write("README.md", "# Product\n\nThe service schedules deliveries.\n")
        self.write("AGENTS.md", "# Instructions\nRespect project instructions.\n")
        self.write("src/app.py", "pass\n")
        before = snapshot(self.target)
        inventory = init_docs.scan(self.target)
        self.assertEqual(inventory["documentation_state"], "code_only")
        self.assertEqual(inventory["readme_evidence"], ["README.md"])
        self.assertEqual(inventory["follow_up"], "sync_minimum_docs")
        self.assertEqual(inventory["business_documents"], [])
        self.assertEqual(inventory["historical_documents"], [])
        self.assertEqual(inventory["code_files"], ["src/app.py"])
        self.assertEqual(snapshot(self.target), before)

    def test_plain_readme_prose_without_code_is_a_migration_candidate(self):
        self.write("README.md", "# Product\n\nOriginal project facts.\n")
        inventory = init_docs.scan(self.target)
        self.assertEqual(inventory["documentation_state"], "navigation_only")
        self.assertEqual(inventory["follow_up"], "ask_user_migration")

    def test_navigation_links_are_not_readme_fact_evidence(self):
        self.write("README.md", "# Product\n\n- [Documentation](docs/README.md)\n")
        self.write("docs/README.md", "# Documentation\n")
        inventory = init_docs.scan(self.target)
        self.assertEqual(inventory["readme_evidence"], [])
        self.assertIsNone(inventory["follow_up"])

    def test_upgrade_still_requires_an_existing_installation_baseline(self):
        self.write("src/app.py", "pass\n")
        before = snapshot(self.target)
        result = self.apply(mode="upgrade")
        self.assertEqual(result["status"], "blocked")
        self.assertFalse(result["applied"])
        self.assertEqual(snapshot(self.target), before)

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
        config = self.config()
        self.assertFalse(config.get("project", {}).get("name"))
        self.assertEqual(config.get("locations", []), [])
        self.assertEqual(config.get("commands", []), [])
        self.assertFalse((self.target / "unsafe").exists())
        self.assertFalse((self.target / "docs/_system").exists())

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
        self.assertEqual(documents["README.md"]["kind"], "navigation")
        self.assertEqual(documents["docs/legacy/decision.md"]["kind"], "historical")
        self.assertEqual(result["historical_documents"], ["docs/legacy/decision.md"])
        self.assertNotIn("node_modules/package/README.md", documents)
        self.assertEqual(snapshot(self.target), before)

    def test_user_config_formatting_and_facts_survive_repeat_without_writes(self):
        self.apply()
        config = self.config()
        config["project"]["name"] = "真实项目名称"
        config["project_custom"] = {"confirmed": "保留扩展字段"}
        self.write(CONFIG, json.dumps(config, ensure_ascii=False, indent=4) + "\n\n")
        before = snapshot(self.target)
        result = self.apply()
        self.assertEqual(result["status"], "noop")
        self.assertEqual(result["actions"], [])
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

    def test_upgrade_changes_version_without_copying_shared_assets(self):
        self.apply()
        relative = "docs/_system/writing-policy.md"
        self.write(relative, (self.source / relative).read_bytes() + b"\nNew shared policy.\n", root=self.source)
        self.upgrade_source()
        result = self.apply(mode="upgrade")
        self.assertFalse(result["conflicts"])
        self.assertEqual(self.config()["system"]["version"], self.upgraded_version)
        self.assertEqual(self.manifest()["system_version"], self.upgraded_version)
        self.assert_light_layout()

    def test_upgrade_keeps_confirmed_project_facts_commands_and_unknown_fields(self):
        self.apply()
        config = self.config()
        config["project"]["name"] = "Confirmed existing product"
        config["locations"] = [{"id": "application", "kind": "code", "enabled": True,
                                 "repository": ".", "paths": ["src/application.py"],
                                 "verified_at": None, "verification_ref": "record:reviewed"}]
        config["commands"] = [{"id": "verify", "argv": ["python3", "-m", "unittest"], "cwd": ".",
                                "side_effect": "local-write", "verification_ref": "record:reviewed"}]
        config["custom_project_setting"] = {"keep": "User-owned value"}
        self.write(CONFIG, json.dumps(config))
        before = {key: config[key] for key in ("project", "locations", "commands", "custom_project_setting")}
        self.upgrade_source()
        result = self.apply(mode="upgrade")
        self.assertFalse(result["conflicts"])
        for key, value in before.items():
            self.assertEqual(self.config()[key], value)

    def test_existing_sparse_configuration_is_adopted_without_losing_user_fields(self):
        config = {"schema_version": 1, "system": {"name": "ai-docs-system", "version": self.system_version},
                  "project": {"name": "Original product", "owner": "team", "operating_mode": "bootstrap"},
                  "work_tracking": {"mode": "repository", "source": "docs/work/items", "external_ref": None},
                  "locations": [], "commands": [], "custom": {"original": True}}
        self.write(CONFIG, json.dumps(config))
        result = self.apply(mode="adopt")
        self.assertFalse(result["conflicts"])
        for key, value in config.items():
            self.assertEqual(self.config()[key], value)
        self.assertEqual(set(self.manifest()["owned_blocks"]), ENTRY_FILES)

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

    def test_existing_unowned_resource_folders_remain_user_owned(self):
        original = {"docs/_tools/docctl.py": b"# Existing unrelated project tool.\n",
                    "docs/_templates/feature.md": b"# Existing project-specific template.\n",
                    "docs/_system/custom-guidelines.md": b"# Historic project-specific guidelines.\n"}
        for relative, content in original.items():
            self.write(relative, content)
        self.apply(mode="adopt")
        for relative, content in original.items():
            self.assertEqual((self.target / relative).read_bytes(), content)
        self.assertNotIn("owned_files", self.manifest())

    def test_legacy_full_install_imports_project_facts_and_removes_only_owned_resources(self):
        self.legacy_project()
        project_path = self.target / "docs/_system/project-map.json"
        project = json.loads(project_path.read_text())
        project["project"]["name"] = "Confirmed legacy product"
        project["locations"][0]["paths"] = ["src/app.py"]
        project_path.write_text(json.dumps(project))
        commands_path = self.target / "docs/_system/commands.json"
        commands = json.loads(commands_path.read_text())
        commands["commands"][0].update({"argv": ["python3", "-m", "venv", ".venv"], "cwd": "."})
        commands_path.write_text(json.dumps(commands))
        self.write("docs/legacy/decision.md", "# Approved historic decision\nOriginal project evidence.\n")
        result = self.apply()
        self.assertTrue(result["applied"])
        config = self.config()
        self.assertEqual(config["project"], project["project"])
        self.assertEqual(config["locations"], project["locations"])
        self.assertEqual(config["commands"], commands["commands"])
        self.assertIn("migration", config)
        self.assertFalse((self.target / "docs/_templates/feature.md").exists())
        self.assertFalse((self.target / "docs/_tools/docctl.py").exists())
        self.assertEqual((self.target / "docs/legacy/decision.md").read_text(),
                         "# Approved historic decision\nOriginal project evidence.\n")
        self.assertTrue(project_path.exists())
        self.assertTrue(commands_path.exists())
        self.assertIn("docs/_system/project-map.json", [item["path"] for item in result["conflicts"]])
        self.assertIn("docs/_system/commands.json", [item["path"] for item in result["conflicts"]])

    def test_legacy_modified_assets_custom_files_and_referenced_sources_are_preserved(self):
        self.legacy_project()
        local = b"# Project-specific approved policy.\n"
        self.write("docs/_system/writing-policy.md", local)
        self.write("docs/_templates/custom.md", "# User-owned legacy template\n")
        self.write("docs/legacy-guide.md", "[Approved rule](_system/authority.md)\n")
        authority = (self.target / "docs/_system/authority.md").read_bytes()
        result = self.apply()
        self.assertEqual((self.target / "docs/_system/writing-policy.md").read_bytes(), local)
        self.assertTrue((self.target / "docs/_templates/custom.md").exists())
        self.assertEqual((self.target / "docs/_system/authority.md").read_bytes(), authority)
        self.assertIn("docs/_system/writing-policy.md", [item["path"] for item in result["conflicts"]])
        self.assertIn("docs/_system/authority.md", [item["path"] for item in result["conflicts"]])

    def test_legacy_migration_keeps_each_known_fact_once_and_preserves_unknown_fields(self):
        self.legacy_project()
        project_path = self.target / "docs/_system/project-map.json"
        project = json.loads(project_path.read_text())
        project["project"]["name"] = "Unique confirmed project fact"
        project["unknown_existing_field"] = {"evidence": "Original user-maintained evidence"}
        project_path.write_text(json.dumps(project))
        commands_path = self.target / "docs/_system/commands.json"
        commands = json.loads(commands_path.read_text())
        commands["unknown_command_field"] = "Original command registry note"
        commands_path.write_text(json.dumps(commands))
        self.apply()
        config = self.config()
        self.assertEqual(config["project"], project["project"])
        self.assertEqual(config["commands"], commands["commands"])
        self.assertEqual(json.dumps(config).count("Unique confirmed project fact"), 1)
        legacy = config["migration"]["legacy_fields"]
        self.assertEqual(legacy["docs/_system/project-map.json"]["unknown_existing_field"],
                         project["unknown_existing_field"])
        self.assertEqual(legacy["docs/_system/commands.json"]["unknown_command_field"],
                         commands["unknown_command_field"])
        for data in legacy.values():
            self.assertFalse(set(data) & {"project", "work_tracking", "locations", "readiness", "commands"})
        self.assertNotIn("legacy_configurations", config["migration"])
        self.assertNotIn("collections", config.get("overrides", {}))
        self.assertNotIn("routes", config.get("overrides", {}))

    def test_unchanged_legacy_install_migrates_to_exact_lightweight_layout(self):
        self.legacy_project()
        result = self.apply()
        self.assertTrue(result["applied"])
        self.assertFalse(result["conflicts"])
        self.assert_light_layout()
        self.assertNotIn("collections", self.config().get("overrides", {}))
        self.assertNotIn("routes", self.config().get("overrides", {}))

    def test_legacy_reference_outside_managed_entry_block_protects_the_owned_resource(self):
        self.legacy_project()
        relative = "docs/_system/execution-policy.md"
        original = (self.target / relative).read_bytes()
        path = self.target / "AGENTS.md"
        outside = b"\nProject instructions: [approved rules](docs/_system/execution-policy.md).\n"
        path.write_bytes(path.read_bytes() + outside)
        result = self.apply()
        self.assertEqual((self.target / relative).read_bytes(), original)
        self.assertTrue(path.read_bytes().endswith(outside))
        self.assertIn(relative, [item["path"] for item in result["conflicts"]])

    def test_custom_legacy_template_keeps_its_referenced_owned_protocol(self):
        self.legacy_project()
        relative = "docs/_system/authority.md"
        original = (self.target / relative).read_bytes()
        custom = "docs/_templates/custom-project-template.md"
        body = "# User-owned project template\n[Approved authority](../_system/authority.md)\n"
        self.write(custom, body)
        result = self.apply()
        self.assertEqual((self.target / custom).read_text(), body)
        self.assertTrue((self.target / relative).exists())
        self.assertEqual((self.target / relative).read_bytes(), original)
        self.assertIn(relative, [item["path"] for item in result["conflicts"]])

    def test_legacy_tool_referenced_by_active_command_is_preserved_without_execution(self):
        self.legacy_project()
        relative = "docs/_tools/docctl.py"
        original = (self.target / relative).read_bytes()
        path = self.target / "docs/_system/commands.json"
        commands = json.loads(path.read_text())
        commands["commands"][0].update({"argv": [sys.executable, relative, "check"], "cwd": "."})
        path.write_text(json.dumps(commands))
        result = self.apply()
        self.assertEqual((self.target / relative).read_bytes(), original)
        self.assertEqual(self.config()["commands"], commands["commands"])
        self.assertIn(relative, [item["path"] for item in result["conflicts"]])

    def test_legacy_deletion_failure_restores_retired_resources_and_existing_entries(self):
        self.legacy_project()
        before = {p.relative_to(self.target).as_posix(): p.read_bytes()
                  for p in self.target.rglob("*") if p.is_file()}
        before_directories = {p.relative_to(self.target).as_posix()
                              for p in self.target.rglob("*") if p.is_dir()}
        original = Path.unlink
        sentinel = self.target / "docs/_templates/feature.md"
        injected = False

        def fail_one_deletion(path, *args, **kwargs):
            nonlocal injected
            if path == sentinel and not injected:
                injected = True
                raise OSError("Injected failure after earlier owned resources were deleted")
            return original(path, *args, **kwargs)

        with mock.patch.object(Path, "unlink", new=fail_one_deletion):
            with self.assertRaises((init_docs.InstallError, OSError)):
                self.apply()
        self.assertTrue(injected)
        self.assertEqual(before, {p.relative_to(self.target).as_posix(): p.read_bytes()
                                  for p in self.target.rglob("*") if p.is_file()})
        self.assertEqual(before_directories, {p.relative_to(self.target).as_posix()
                                             for p in self.target.rglob("*") if p.is_dir()})
        self.assertFalse((self.target / ".ai-docs-init.lock").exists())

    def test_legacy_saved_plan_rechecks_new_project_references_before_deleting_resources(self):
        self.legacy_project()
        plan = init_docs.plan_install(self.source, self.target)
        relative = "docs/_system/authority.md"
        self.assertIn(relative, [item["path"] for item in plan["actions"] if item["operation"] == "delete"])
        self.write("docs/new-approved-guide.md", "[Approved authority](_system/authority.md)\n")
        before = {p.relative_to(self.target).as_posix(): p.read_bytes()
                  for p in self.target.rglob("*") if p.is_file()}
        try:
            result = self.apply(plan=plan)
        except init_docs.InstallError:
            pass
        else:
            self.assertFalse(result["applied"])
            self.assertEqual(result["status"], "blocked")
        self.assertEqual(before, {p.relative_to(self.target).as_posix(): p.read_bytes()
                                  for p in self.target.rglob("*") if p.is_file()})

    def test_legacy_schema_one_registry_blocks_unsafe_protocol_migration(self):
        self.legacy_project()
        self.write("docs/_system/collections.json", '{"schema_version":1,"collections":[]}\n')
        before = snapshot(self.target)
        result = self.apply()
        self.assertEqual(result["status"], "blocked")
        self.assertFalse(result["applied"])
        self.assertEqual(snapshot(self.target), before)

    def test_conflicting_system_and_installation_versions_are_blocked(self):
        self.apply()
        config = self.config()
        config["system"]["version"] = "99.0.0"
        self.write(CONFIG, json.dumps(config))
        before = snapshot(self.target)
        result = self.apply(mode="upgrade")
        self.assertEqual(result["status"], "blocked")
        self.assertFalse(result["applied"])
        self.assertEqual(snapshot(self.target), before)

    def test_invalid_collection_override_is_blocked_without_lowering_the_threshold(self):
        self.apply()
        config = self.config()
        registry = json.loads((self.source / "docs/_system/collections.json").read_text())
        registry["defaults"]["compact_max_items"] = 99
        config["overrides"] = {"collections": registry}
        self.write(CONFIG, json.dumps(config))
        before = snapshot(self.target)
        result = self.apply(mode="upgrade")
        self.assertEqual(result["status"], "blocked")
        self.assertFalse(result["applied"])
        self.assertEqual(snapshot(self.target), before)

    def test_unknown_route_override_is_blocked_without_installing_shared_resources(self):
        self.apply()
        config = self.config()
        routes = json.loads((self.source / "docs/_system/routes.json").read_text())
        routes["routes"][0]["must_read"] = [{"collection": "unknown-kind"}]
        config["overrides"] = {"routes": routes}
        self.write(CONFIG, json.dumps(config))
        before = snapshot(self.target)
        result = self.apply(mode="upgrade")
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(snapshot(self.target), before)
        self.assertFalse((self.target / "docs/_system").exists())

    def test_custom_route_requiring_an_unavailable_shared_protocol_is_blocked_before_upgrade(self):
        self.apply()
        config = self.config()
        routes = json.loads((self.source / "docs/_system/routes.json").read_text())
        routes["routes"][0]["must_read"].append("docs/_system/missing-approved-policy.md")
        config["overrides"] = {"routes": routes}
        self.write(CONFIG, json.dumps(config))
        before = snapshot(self.target)
        result = self.apply(mode="upgrade")
        self.assertEqual(result["status"], "blocked")
        self.assertFalse(result["applied"])
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
        original = self.source / "_AGENTS.md"
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

    def test_legacy_manifest_path_traversal_is_blocked_without_writing(self):
        self.legacy_project()
        outside = self.write("outside.md", "Outside file must remain unchanged.\n", root=self.work)
        data = json.loads((self.target / LEGACY_MANIFEST).read_text())
        data["owned_files"]["../outside.md"] = {
            "sha256": hashlib.sha256(outside.read_bytes()).hexdigest()}
        self.write(LEGACY_MANIFEST, json.dumps(data))
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
        config = json.loads((self.target / CONFIG).read_text())
        config["installation"] = data
        self.write(CONFIG, json.dumps(config))
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
        config = json.loads((self.target / CONFIG).read_text())
        config["installation"] = data
        self.write(CONFIG, json.dumps(config))
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
