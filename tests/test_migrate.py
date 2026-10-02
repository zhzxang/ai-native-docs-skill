"""Migration behavior tests: only disposable initialized target repositories."""
from __future__ import annotations

import importlib.util
import io
from contextlib import redirect_stdout
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "skills/ai-docs-check/assets/templates"
sys.path.insert(0, str(ROOT / "skills/ai-docs-migrate/scripts"))
import migrate



def load_installer():
    spec = importlib.util.spec_from_file_location("migration_test_installer", SOURCE / "docs/_tools/init_docs.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def complete_snapshot(root):
    return {p.relative_to(root).as_posix(): ("directory",) if p.is_dir() else (p.read_bytes(), p.stat().st_mode)
            for p in root.rglob("*") if not p.is_symlink()}


class MigrationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="ai-docs-migration-test-")
        self.work = Path(self.temporary.name).resolve()
        self.root = self.work / "project"
        self.source = SOURCE
        result = load_installer().bootstrap(self.source, self.root, dry_run=False)
        self.assertTrue(result["applied"])

    def tearDown(self):
        self.temporary.cleanup()

    def write(self, relative, text):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.encode() if isinstance(text, str) else text)
        return path

    def mapping(self, source="legacy/design.md", *, number=1, typ="adr", meta=None):
        return {"source": source, "type": typ, "id": f"ADR-{number}" if typ == "adr" else f"TASK-{number}",
                "title": f"设计 {number}", "slug": f"design-{number}", **({"meta": meta} if meta is not None else {})}

    def plan(self, *records):
        return migrate.plan_migration(self.root, self.source, list(records) or [self.mapping()])

    def apply(self, plan):
        return migrate.apply_plan(self.root, self.source, plan)

    def test_inventory_is_read_only_and_does_not_classify_plain_markdown(self):
        self.write("legacy/design.md", "# 我的设计\n\n完整内容。\n")
        before = complete_snapshot(self.root)
        result = migrate.inventory(self.root, self.source)
        legacy = next(d for d in result["documents"] if d["path"] == "legacy/design.md")
        self.assertEqual(legacy["format"], "markdown")
        self.assertEqual(legacy["entries"], [])
        self.assertEqual(before, complete_snapshot(self.root))

    def test_plan_does_not_write_and_apply_creates_draft_with_null_unknowns(self):
        original = "# 我的设计\n\n不得遗漏的第一段。\n\n## 后果\n完整事实二。\n"
        self.write("legacy/design.md", original)
        before = complete_snapshot(self.root)
        plan = self.plan()
        self.assertEqual(plan["status"], "planned", plan["conflicts"])
        self.assertEqual(before, complete_snapshot(self.root))
        result = self.apply(plan)
        self.assertEqual(result["status"], "applied")
        text = (self.root / "docs/engineering/adrs.md").read_text()
        self.assertIn("不得遗漏的第一段", text)
        self.assertIn("完整事实二", text)
        entry = migrate.load_tool(self.source).parse_compact_entries(text)[0]
        self.assertEqual(entry["meta"]["status"], "draft")
        self.assertIsNone(entry["meta"]["owner"])
        self.assertIsNone(entry["meta"]["summary"])
        self.assertIsNone(entry["meta"]["approval_ref"])
        self.assertTrue(migrate.load_tool(self.source).thin_redirect((self.root / "legacy/design.md").read_text()))
        self.assertFalse((self.root / migrate.LOCK).exists())

    def test_rewrites_all_repository_incoming_outgoing_anchors_and_attachments(self):
        self.write("legacy/design.md", '# 原标题\n\n## 后果\n[附件](image.png)\n[说明](../notes.md#记录)\n[自身](#后果)\n')
        self.write("legacy/image.png", b"image bytes")
        self.write("notes.md", "# 记录\n[旧标题](legacy/design.md#原标题)\n![图片](legacy/image.png)\n")
        self.write("code/components/README.md", '[详细](../../legacy/design.md#后果 "说明")\n[参考]: ../../legacy/design.md#原标题\n')
        plan = self.plan()
        self.assertEqual(plan["status"], "planned", plan["conflicts"])
        self.apply(plan)
        content = (self.root / "docs/engineering/adrs.md").read_text()
        self.assertIn("../../legacy/image.png", content)
        self.assertIn("../../notes.md#", content)
        self.assertIn("(#adr-1--", content)
        incoming = (self.root / "code/components/README.md").read_text()
        self.assertIn("../../docs/engineering/adrs.md#adr-1--", incoming)
        self.assertIn('"说明"', incoming)
        self.assertEqual((self.root / "legacy/image.png").read_bytes(), b"image bytes")

    def test_preserves_frontmatter_identity_status_approval_and_extensions(self):
        tool = migrate.load_tool(self.source)
        template = tool.parse_frontmatter((self.source / "docs/_templates/adr.md").read_text())
        meta = {key: None for key in template}
        meta.update(id="ADR-1", slug="design-1", type="adr", status="active", summary="已批准决策",
                    owner="团队", applies_to="v1", verified_at="2026-10-01", verification_ref="https://example.com/evidence",
                    authority="normative", approved_by="负责人", approval_ref="https://example.com/approval", old_revision=7)
        self.write("legacy/design.md", "---\n" + tool.metadata_text(meta) + "\n---\n# 已批准\n历史全文。\n")
        plan = self.plan()
        self.assertEqual(plan["status"], "planned", plan["conflicts"])
        self.apply(plan)
        entry = tool.parse_compact_entries((self.root / "docs/engineering/adrs.md").read_text())[0]
        self.assertEqual(entry["meta"], meta)

    def test_does_not_guess_task_kind_or_state(self):
        self.write("legacy/design.md", "# 工作\n明确目标。\n")
        with self.assertRaisesRegex(ValueError, "kind|state"):
            self.plan(self.mapping(typ="task"))
        plan = self.plan(self.mapping(typ="task", meta={"kind": "docs", "state": "done"}))
        self.assertEqual(plan["documents"][0]["meta"]["state"], "done")

    def test_mapping_cannot_rewrite_established_fact(self):
        self.write("legacy/design.md", '---\nid: "ADR-1"\nstatus: "archived"\n---\n# 旧设计\n全文。\n')
        with self.assertRaisesRegex(ValueError, "覆盖既有事实"):
            self.plan(self.mapping(meta={"status": "active"}))
        with self.assertRaisesRegex(ValueError, "既有元数据 id"):
            self.plan(self.mapping(number=2))

    def test_one_and_two_compact_third_expands_and_repairs_old_collection_links(self):
        tool = migrate.load_tool(self.source)
        tool.make_new(self.root, "adr", "ADR-OLD", "old", "旧决策", resources=self.source)
        self.write("legacy/a.md", "# 决策 A\n\n## 唯一章节 A\n原文 A。\n")
        self.write("legacy/b.md", "# 决策 B\n\n## 唯一章节 B\n原文 B。\n")
        self.write("notes.md", "[旧](docs/engineering/adrs.md#adr-old)\n")
        plan = self.plan(self.mapping("legacy/a.md", number=1), self.mapping("legacy/b.md", number=2))
        self.assertEqual(plan["status"], "planned", plan["conflicts"])
        self.apply(plan)
        self.assertTrue((self.root / "docs/engineering/adrs/ADR-OLD-old.md").is_file())
        self.assertTrue((self.root / "docs/engineering/adrs/ADR-1-design-1.md").is_file())
        self.assertIn("原文 A", (self.root / "docs/engineering/adrs/ADR-1-design-1.md").read_text())
        self.assertTrue(tool.thin_redirect((self.root / "docs/engineering/adrs.md").read_text()))
        self.assertIn("adrs/ADR-OLD-old.md#adr-old", (self.root / "notes.md").read_text())
        self.assertTrue(tool.validate(self.root, resources=self.source)["ok"])

    def test_existing_expanded_collection_does_not_collapse(self):
        (self.root / "docs/engineering/adrs").mkdir(parents=True)
        self.write("legacy/design.md", "# 原标题\n全部正文。\n")
        plan = self.plan()
        self.apply(plan)
        self.assertTrue((self.root / "docs/engineering/adrs/ADR-1-design-1.md").is_file())
        self.assertFalse((self.root / "docs/engineering/adrs.md").exists())

    def test_third_item_expands_two_existing_records_with_repeated_section_headings(self):
        tool = migrate.load_tool(self.source)
        tool.make_new(self.root, "adr", "ADR-OLD1", "old-1", "旧决策一", resources=self.source)
        tool.make_new(self.root, "adr", "ADR-OLD2", "old-2", "旧决策二", resources=self.source)
        self.write("legacy/design.md", "# 新设计\n实际内容。\n")
        self.write("notes.md", "[第二条背景](docs/engineering/adrs.md#背景与方案-1)\n")
        plan = self.plan()
        self.assertEqual(plan["status"], "planned", plan["conflicts"])
        self.apply(plan)
        self.assertIn("adrs/ADR-OLD2-old-2.md#adr-old2--", (self.root / "notes.md").read_text())
        self.assertTrue(tool.validate(self.root, resources=self.source)["ok"])

    def test_common_singleton_types_use_their_reference_paths_without_collection_layout(self):
        for typ, doc_id, target in (
            ("project-overview", "PROJECT-OVERVIEW", "docs/project/overview.md"),
            ("architecture-overview", "ARCH-OVERVIEW", "docs/engineering/architecture/overview.md"),
            ("development-guide", "DEV-QUICKSTART", "docs/engineering/development/quickstart.md"),
        ):
            source = "legacy/" + typ + ".md"
            self.write(source, "# 原有标题\n原有必要全文。\n")
            record = self.mapping(source)
            record.update(type=typ, id=doc_id, slug=typ, title=typ)
            plan = self.plan(record)
            self.assertEqual(plan["status"], "planned", plan["conflicts"])
            self.apply(plan)
            meta = migrate.load_tool(self.source).parse_frontmatter((self.root / target).read_text())
            self.assertEqual(meta["id"], doc_id)
            self.assertEqual(meta["status"], "draft")
            self.assertIn("原有必要全文", (self.root / target).read_text())

    def test_singleton_existing_default_path_can_be_normalized_in_place(self):
        self.write("docs/project/overview.md", "# 原总纲\n原项目事实。\n")
        self.write("notes.md", "[总纲](docs/project/overview.md#原总纲)\n")
        record = self.mapping("docs/project/overview.md")
        record.update(type="project-overview", id="PROJECT-OVERVIEW", slug="overview", title="项目总纲")
        plan = self.plan(record)
        self.assertEqual(plan["status"], "planned", plan["conflicts"])
        self.apply(plan)
        output = (self.root / "docs/project/overview.md").read_text()
        self.assertNotIn("doc-redirect", output)
        self.assertIn("原项目事实", output)
        self.assertIn("project-overview--", (self.root / "notes.md").read_text())

    def test_singleton_destination_cannot_overwrite_another_document(self):
        self.write("legacy/design.md", "# 原总纲\n项目事实。\n")
        self.write("docs/project/overview.md", "# 另一总纲\n另一对象。\n")
        record = self.mapping()
        record.update(type="project-overview", id="PROJECT-OVERVIEW")
        with self.assertRaisesRegex(ValueError, "既有单例"):
            self.plan(record)

    def test_cross_type_links_repaired_once_all_final_targets_known(self):
        self.write("legacy/a.md", "# 决策\n[工作](b.md#工作)\n")
        self.write("legacy/b.md", "# 工作\n[决策](a.md#决策)\n")
        records = [self.mapping("legacy/a.md"), self.mapping("legacy/b.md", typ="task", meta={"kind": "docs", "state": "queued"})]
        plan = self.plan(*records)
        self.assertEqual(plan["status"], "planned", plan["conflicts"])
        self.apply(plan)
        self.assertIn("../work/items.md#task-1--", (self.root / "docs/engineering/adrs.md").read_text())
        self.assertIn("../engineering/adrs.md#adr-1--", (self.root / "docs/work/items.md").read_text())

    def test_meta_references_follow_moved_document(self):
        self.write("legacy/design.md", "# 原标题\n全部正文。\n")
        self.write("legacy/other.md", '---\nverification_ref: "legacy/design.md#原标题"\n---\n# 其他\n')
        plan = self.plan()
        self.assertEqual(plan["status"], "planned", plan["conflicts"])
        self.apply(plan)
        self.assertIn("docs/engineering/adrs.md#adr-1--", (self.root / "legacy/other.md").read_text())

    def test_old_unknown_anchor_and_unsupported_local_html_block(self):
        self.write("legacy/design.md", "# 原标题\n全部正文。\n")
        self.write("notes.md", "[无锚点](legacy/design.md#missing)\n")
        with self.assertRaisesRegex(ValueError, "旧锚点"):
            self.plan()
        self.write("notes.md", '<a href="legacy/design.md">旧设计</a>\n')
        with self.assertRaisesRegex(ValueError, "HTML"):
            self.plan()

    def test_setext_and_wiki_formats_fail_without_writing(self):
        for text in ("标题\n====\n内容\n", "# 标题\n[[其他]]\n"):
            self.write("legacy/design.md", text)
            before = complete_snapshot(self.root)
            with self.assertRaises(ValueError):
                self.plan()
            self.assertEqual(before, complete_snapshot(self.root))

    def test_fenced_examples_stay_unchanged(self):
        self.write("legacy/design.md", '# 原标题\n\n实际正文。\n\n```md\n# 示例\n[示例](missing.md#old)\n```\n')
        plan = self.plan()
        self.assertEqual(plan["status"], "planned", plan["conflicts"])
        self.apply(plan)
        self.assertIn('# 示例\n[示例](missing.md#old)', (self.root / "docs/engineering/adrs.md").read_text())

    def test_requires_initialization_before_migration(self):
        (self.root / migrate.CONFIG).unlink()
        with self.assertRaisesRegex(ValueError, "先初始化"):
            self.plan()

    def test_protocol_entry_files_cannot_be_migrated_away(self):
        before = complete_snapshot(self.root)
        for relative in migrate.ENTRY_FILES:
            with self.assertRaisesRegex(ValueError, "协议入口"):
                self.plan(self.mapping(relative))
        self.assertEqual(before, complete_snapshot(self.root))

    def test_path_traversal_symlink_and_source_resource_boundary_rejected(self):
        self.write("legacy/design.md", "# 正文\n事实正文。\n")
        with self.assertRaises(ValueError):
            self.plan(self.mapping("../escape.md"))
        outside = self.work / "outside.md"
        outside.write_text("# 外部\n")
        (self.root / "legacy/link.md").symlink_to(outside)
        with self.assertRaisesRegex(ValueError, "符号链接"):
            self.plan(self.mapping("legacy/link.md"))
        with self.assertRaisesRegex(ValueError, "互相包含"):
            migrate.plan_migration(self.source, self.source, [self.mapping()])

    def test_standard_macos_temporary_aliases_are_allowed_but_custom_ancestors_are_not(self):
        self.write("legacy/design.md", "# 正文\n事实正文。\n")
        if str(self.root).startswith("/private/var/") and Path("/var").is_symlink():
            alias = Path(str(self.root).replace("/private/var/", "/var/", 1))
            plan = migrate.plan_migration(alias, self.source, [self.mapping()])
            self.assertEqual(plan["target"], str(self.root))
        with tempfile.TemporaryDirectory(dir="/tmp", prefix="migration-alias-") as temporary:
            external = Path(temporary).resolve()
            alias = Path("/tmp") / external.name if external.parent == Path("/private/tmp") else external
            migrate.reject_symlinks(alias / "plan.json")
            migrate.save_plan(alias / "plan.json", self.root, self.plan())
        (self.work / "custom-alias").symlink_to(self.root, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "符号链接"):
            migrate.plan_migration(self.work / "custom-alias", self.source, [self.mapping()])

    def test_scan_cli_aliases_inventory_without_requiring_initialization(self):
        for flag in ("--scan", "--inventory"):
            output = io.StringIO()
            with redirect_stdout(output):
                code = migrate.cli(["--target", str(self.root), "--source", str(self.source), flag])
            self.assertEqual(code, 0)
            self.assertIn("documents", json.loads(output.getvalue()))

    def test_plan_file_must_be_outside_repo_and_cannot_overwrite(self):
        self.write("legacy/design.md", "# 正文\n事实正文。\n")
        plan = self.plan()
        with self.assertRaisesRegex(ValueError, "仓库之外"):
            migrate.save_plan(self.root / "plan.json", self.root, plan)
        path = self.work / "plan.json"
        migrate.save_plan(path, self.root, plan)
        with self.assertRaises(FileExistsError):
            migrate.save_plan(path, self.root, plan)

    def test_stale_source_config_or_incoming_file_added_refuses_application(self):
        self.write("legacy/design.md", "# 正文\n事实正文。\n")
        for relative, content in (("legacy/design.md", "# 改变\n改变后的正文。\n"), ("notes.md", "[新引用](legacy/design.md)\n")):
            plan = self.plan()
            self.write(relative, content)
            before = complete_snapshot(self.root)
            with self.assertRaisesRegex(ValueError, "陈旧计划"):
                self.apply(plan)
            self.assertEqual(before, complete_snapshot(self.root))

    def test_tampered_plan_even_with_recomputed_hash_is_rejected(self):
        self.write("legacy/design.md", "# 正文\n事实正文。\n")
        plan = self.plan()
        plan["actions"][0]["content"] = "danger"
        plan["actions"][0]["content_sha256"] = migrate.digest("danger")
        plan["plan_sha256"] = migrate.digest(migrate.canonical({k: v for k, v in plan.items() if k != "plan_sha256"}))
        before = complete_snapshot(self.root)
        with self.assertRaisesRegex(ValueError, "重建结果"):
            self.apply(plan)
        self.assertEqual(before, complete_snapshot(self.root))

    def test_config_and_resource_changes_make_saved_plan_stale(self):
        self.write("legacy/design.md", "# 正文\n事实正文。\n")
        plan = self.plan()
        config = self.root / migrate.CONFIG
        config.write_text(config.read_text() + "\n")
        with self.assertRaisesRegex(ValueError, "陈旧计划"):
            self.apply(plan)
        self.source = self.work / "resources"
        shutil.copytree(SOURCE, self.source, ignore=shutil.ignore_patterns("__pycache__"))
        plan = self.plan()
        path = self.source / "docs/_system/writing-policy.md"
        path.write_text(path.read_text() + "\n")
        with self.assertRaisesRegex(ValueError, "陈旧计划"):
            self.apply(plan)

    def test_existing_generated_indexes_and_machine_catalog_refresh_in_same_plan(self):
        tool = migrate.load_tool(self.source)
        tool.generate_indexes(self.root, resources=self.source)
        self.write("legacy/design.md", "# 正文\n事实正文。\n")
        plan = self.plan()
        self.assertEqual(plan["status"], "planned", plan["conflicts"])
        self.assertTrue(any(a["path"] == "docs/_generated/catalog/adr/page-001.json" for a in plan["actions"]))
        self.apply(plan)
        catalog = json.loads((self.root / "docs/_generated/catalog/adr/page-001.json").read_text())
        self.assertEqual(catalog["records"][0]["path"], "docs/engineering/adrs.md")
        self.assertEqual(catalog["records"][0]["id"], "ADR-1")
        self.assertTrue(tool.validate(self.root, resources=self.source)["ok"])

    def test_rollback_does_not_overwrite_external_changes_to_written_files(self):
        self.write("legacy/design.md", "# 正文\n事实正文。\n")
        self.write("notes.md", "[旧](legacy/design.md)\n")
        plan = self.plan()
        original_write = migrate.atomic_write
        calls = 0
        first = self.root / plan["actions"][0]["path"]
        def concurrent_write(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                first.write_text("other writer change")
                raise OSError("injected concurrent failure")
            return original_write(*args, **kwargs)
        with mock.patch.object(migrate, "atomic_write", side_effect=concurrent_write):
            with self.assertRaisesRegex(ValueError, "回滚未完成"):
                self.apply(plan)
        self.assertEqual(first.read_text(), "other writer change")
        self.assertFalse((self.root / migrate.LOCK).exists())

    def test_write_lock_prevents_application_and_remains_owned_by_other_writer(self):
        self.write("legacy/design.md", "# 正文\n事实正文。\n")
        plan = self.plan()
        self.write(migrate.LOCK, "other writer")
        with self.assertRaisesRegex(ValueError, "持有"):
            self.apply(plan)
        self.assertEqual((self.root / migrate.LOCK).read_text(), "other writer")

    def test_mid_application_failure_restores_bytes_modes_and_directory_layout(self):
        self.write("legacy/design.md", "# 正文\n事实正文。\n")
        self.write("notes.md", "[入链](legacy/design.md)\n")
        plan = self.plan()
        before = complete_snapshot(self.root)
        original_write = migrate.atomic_write
        calls = 0
        def failing_write(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("injected failure")
            return original_write(*args, **kwargs)
        with mock.patch.object(migrate, "atomic_write", side_effect=failing_write):
            with self.assertRaisesRegex(OSError, "injected"):
                self.apply(plan)
        self.assertEqual(before, complete_snapshot(self.root))

    def test_failure_after_actual_publication_rolls_back_current_action_too(self):
        self.write("legacy/design.md", "# 正文\n事实正文。\n")
        self.write("notes.md", "[入链](legacy/design.md)\n")
        plan = self.plan()
        before = complete_snapshot(self.root)
        original_write = migrate.atomic_write
        calls = 0
        def publish_then_fail(*args, **kwargs):
            nonlocal calls
            calls += 1
            result = original_write(*args, **kwargs)
            if calls == 2:
                raise OSError("post-publication failure")
            return result
        with mock.patch.object(migrate, "atomic_write", side_effect=publish_then_fail):
            with self.assertRaisesRegex(OSError, "post-publication"):
                self.apply(plan)
        self.assertEqual(before, complete_snapshot(self.root))

    def test_bom_frontmatter_preserves_existing_meta_and_body(self):
        self.write("legacy/design.md", '\ufeff---\nid: "ADR-1"\nstatus: "archived"\n---\n# 旧标题\n历史正文。\n')
        plan = self.plan()
        self.assertEqual(plan["status"], "planned", plan["conflicts"])
        self.apply(plan)
        text = (self.root / "docs/engineering/adrs.md").read_text()
        self.assertIn('status: "archived"', text)
        self.assertIn("历史正文", text)

    def test_new_link_errors_block_plan_and_prevent_application(self):
        self.write("legacy/design.md", "# 正文\n[原先缺失](missing.png)\n")
        plan = self.plan()
        # Relocation changes the diagnostic path, so a retained source defect is explicit.
        self.assertEqual(plan["status"], "blocked")
        self.assertTrue(plan["conflicts"])
        with self.assertRaisesRegex(ValueError, "受阻"):
            self.apply(plan)

    def test_duplicate_id_or_topic_requires_manual_resolution(self):
        self.write("legacy/a.md", "# A\n")
        self.write("legacy/b.md", "# B\n")
        one = self.mapping("legacy/a.md")
        two = self.mapping("legacy/b.md", number=2)
        two["slug"] = one["slug"]
        with self.assertRaisesRegex(ValueError, "查重"):
            self.plan(one, two)


if __name__ == "__main__":
    unittest.main()
