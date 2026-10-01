"""Behavioral tests for adaptive documentation; never run application commands."""
from __future__ import annotations

import contextlib
import io
import json
import shutil
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import docctl
import init_docs

KIT_ROOT = Path(__file__).resolve().parents[2]


class ParserTests(unittest.TestCase):
    def test_flat_yaml_scalars(self):
        data = docctl.parse_frontmatter('---\nid: "A-1"\nowner: null\nflag: true\ncount: 3\n---\n# Title')
        self.assertEqual(data, {"id": "A-1", "owner": None, "flag": True, "count": 3})

    def test_plain_markdown(self):
        self.assertIsNone(docctl.parse_frontmatter("# No metadata\n"))

    def test_duplicate_keys_rejected(self):
        with self.assertRaises(docctl.DocError):
            docctl.parse_frontmatter('---\nid: "A-1"\nid: "A-2"\n---')

    def test_nested_metadata_rejected(self):
        with self.assertRaises(docctl.DocError):
            docctl.parse_frontmatter('---\nitems: ["a"]\n---')

    def test_unquoted_text_rejected(self):
        with self.assertRaises(docctl.DocError):
            docctl.parse_frontmatter('---\nid: ABC-1\n---')

    def test_unclosed_metadata_rejected(self):
        with self.assertRaises(docctl.DocError):
            docctl.parse_frontmatter('---\nid: "A-1"')

    def test_dates(self):
        self.assertTrue(docctl.date_is_valid("2026-10-01"))
        self.assertTrue(docctl.date_is_valid("2026-10-01T12:30:00+08:00"))
        self.assertFalse(docctl.date_is_valid("2026-10-01T12:30:00"))
        self.assertFalse(docctl.date_is_valid("2026-02-30"))

    def test_code_fences_not_links(self):
        body = "# Visible\n```markdown\n[x](missing.md)\n```\n[end](real.md)\n"
        visible = docctl.without_code_fences(body)
        self.assertNotIn("missing.md", visible)
        self.assertIn("real.md", visible)


class RepositoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="docctl-test-")
        self.root = (Path(self.tmp.name) / "repo").resolve()
        init_docs.install(KIT_ROOT, self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def new(self, number=900, key="feature", slug=None, title=None, kind=None):
        prefix = {"feature": "FEAT", "feedback": "FB", "task": "TASK", "plan": "PLAN"}[key]
        return docctl.make_new(self.root, key, f"{prefix}-{number}", slug or f"item-{number}",
                               title or f"条目 {number}", kind=kind)

    def records(self, key="feature"):
        return docctl.find_records(self.root, typ=key)["records"]

    def test_pristine_structure_passes(self):
        result = docctl.validate(self.root)
        self.assertTrue(result["ok"], result["errors"])

    def test_uninitialized_strict_readiness_fails(self):
        result = docctl.validate(self.root, strict=True)
        self.assertFalse(result["ok"])
        self.assertTrue(any("bootstrap" in e for e in result["errors"]))

    def test_reference_sources_are_not_records(self):
        self.assertEqual(docctl.collect_records(self.root), [])
        self.assertFalse((self.root / "docs/product").exists())
        self.assertFalse((self.root / "docs/research").exists())
        self.assertFalse((self.root / "docs/_generated").exists())

    def test_first_feedback_creates_only_compact_file(self):
        p = self.new(key="feedback")
        self.assertEqual(p, self.root / "docs/research/feedback.md")
        self.assertFalse((self.root / "docs/research/feedback").exists())
        record = self.records("feedback")[0]
        self.assertEqual(record["id"], "FB-900")
        self.assertEqual(record["status"], "draft")
        self.assertIsNone(record["verified_at"])
        self.assertEqual(record["anchor"], "fb-900")

    def test_second_feedback_keeps_independent_metadata_in_same_file(self):
        p = self.new(key="feedback")
        p.write_text(p.read_text().replace('applies_to: "{{VERSION_OR_SCOPE}}"', 'applies_to: "MVP"', 1))
        self.assertEqual(p, self.new(901, key="feedback"))
        records = self.records("feedback")
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0]["applies_to"], "MVP")
        self.assertNotEqual(records[1]["applies_to"], "MVP")
        self.assertFalse(p.with_suffix("").exists())

    def test_updating_one_item_does_not_expand(self):
        p = self.new(key="feedback")
        self.new(901, key="feedback")
        p.write_text(p.read_text().replace("### 来源与时间", "### 来源与时间\n补充同一反馈的实际来源", 1))
        self.assertEqual(len(self.records("feedback")), 2)
        self.assertFalse(p.with_suffix("").exists())
        self.assertTrue(docctl.validate(self.root)["ok"])

    def test_third_feedback_expands_and_preserves_identity_and_evidence(self):
        p = self.new(key="feedback", slug="first", title="第一条反馈")
        p.write_text(p.read_text().replace('applies_to: "{{VERSION_OR_SCOPE}}"', 'applies_to: "MVP"', 1)
                     .replace("verified_at: null", 'verified_at: "2026-10-01"', 1)
                     .replace("verification_ref: null", 'verification_ref: "record:source-1"', 1))
        self.new(901, key="feedback", slug="second", title="第二条反馈")
        self.new(902, key="feedback", slug="third", title="第三条反馈")
        self.assertFalse(p.exists())
        folder = self.root / "docs/research/feedback"
        self.assertEqual(sorted(x.name for x in folder.iterdir()),
                         ["FB-900-first.md", "FB-901-second.md", "FB-902-third.md"])
        data = docctl.parse_frontmatter((folder / "FB-900-first.md").read_text())
        self.assertEqual(data["id"], "FB-900")
        self.assertEqual(data["applies_to"], "MVP")
        self.assertEqual(data["verification_ref"], "record:source-1")
        self.assertEqual(data["verified_at"], "2026-10-01")
        self.assertTrue(docctl.validate(self.root)["ok"])

    def test_more_acceptance_conditions_are_not_more_items(self):
        p = self.new()
        p.write_text(p.read_text() + "\n### 额外验收\n1. 条件一\n2. 条件二\n3. 条件三\n")
        self.assertEqual(len(self.records()), 1)
        self.assertTrue(docctl.validate(self.root)["ok"])
        self.assertFalse(p.with_suffix("").exists())

    def test_duplicate_id_and_overwrite_rejected(self):
        p = self.new()
        original = p.read_bytes()
        with self.assertRaises(docctl.DocError):
            self.new(slug="another", title="另一个标题")
        self.assertEqual(p.read_bytes(), original)
        self.new(901)
        self.assertEqual(len(self.records()), 2)

    def test_concurrent_write_is_refused_without_overwriting(self):
        p = self.new()
        before = p.read_bytes()
        lock = self.root / "docs/_system/.docctl-new.lock"
        lock.write_text("active writer")
        with self.assertRaises(docctl.DocError):
            self.new(901)
        self.assertEqual(p.read_bytes(), before)
        self.assertEqual(lock.read_text(), "active writer")
        lock.unlink()
        self.new(901)
        self.assertEqual(len(self.records()), 2)

    def test_same_topic_requires_updating_existing_item(self):
        p = self.new(slug="login", title="登录")
        original = p.read_bytes()
        with self.assertRaises(docctl.DocError):
            self.new(901, slug="other", title="登录")
        with self.assertRaises(docctl.DocError):
            self.new(902, slug="login", title="登录补充")
        self.assertEqual(p.read_bytes(), original)

    def test_invalid_slug_and_wrong_prefix_rejected(self):
        with self.assertRaises(docctl.DocError):
            self.new(slug="../escape")
        with self.assertRaises(docctl.DocError):
            docctl.make_new(self.root, "feature", "TASK-900", "valid", "标题")

    def test_path_escape_rejected(self):
        with self.assertRaises(docctl.DocError):
            docctl.safe_path(self.root, "../outside")
        with self.assertRaises(docctl.DocError):
            docctl.safe_path(self.root, "/tmp/outside")

    def test_bug_task_state_is_independent_in_compact_file(self):
        p = self.new(key="task", kind="bug")
        p.write_text(p.read_text().replace('state: "queued"', 'state: "blocked"', 1))
        self.new(901, key="task", kind="bug")
        result = docctl.find_records(self.root, typ="task", state="queued", kind="bug")
        self.assertEqual(result["total_matches"], 1)
        self.assertEqual(result["records"][0]["id"], "TASK-901")

    def test_external_tracker_rejects_duplicate_local_source(self):
        p = self.root / "docs/_system/project-map.json"
        data = json.loads(p.read_text())
        data["work_tracking"]["mode"] = "external"
        p.write_text(json.dumps(data))
        with self.assertRaises(docctl.DocError):
            self.new(key="task", kind="bug")

    def test_broken_link_is_caught(self):
        p = self.new()
        p.write_text(p.read_text() + "\n[broken](missing-file.md)\n")
        result = docctl.validate(self.root)
        self.assertTrue(any("missing-file.md" in e for e in result["errors"]))

    def test_broken_anchor_is_caught(self):
        p = self.new()
        p.write_text(p.read_text() + "\n[broken](#does-not-exist)\n")
        self.assertFalse(docctl.validate(self.root)["ok"])

    def test_migration_repairs_inbound_outbound_and_cross_item_links(self):
        p = self.new(slug="first")
        self.new(901, slug="second")
        asset = self.root / "docs/assets/evidence.txt"
        asset.parent.mkdir()
        asset.write_text("safe evidence")
        p.write_text(p.read_text() +
                     "\n[proof](../assets/evidence.txt)\n[other](features.md#feat-900)\n")
        watcher = self.root / "docs/watcher.md"
        watcher.write_text("[first](product/features.md#feat-900)\n[second](product/features.md#feat-901)\n")
        self.new(902, slug="third")
        self.assertIn("product/features/FEAT-900-first.md#feat-900", watcher.read_text())
        self.assertIn("product/features/FEAT-901-second.md#feat-901", watcher.read_text())
        moved = self.root / "docs/product/features/FEAT-901-second.md"
        self.assertIn("../../assets/evidence.txt", moved.read_text())
        self.assertIn("FEAT-900-first.md#feat-900", moved.read_text())
        self.assertTrue(docctl.validate(self.root)["ok"])

    def test_expanded_collection_does_not_collapse_after_deletion(self):
        self.new()
        self.new(901)
        last = self.new(902)
        last.unlink()
        self.assertTrue(docctl.validate(self.root)["ok"])
        p = self.new(903)
        self.assertEqual(p.parent, self.root / "docs/product/features")
        self.assertFalse((self.root / "docs/product/features.md").exists())

    def test_ambiguous_old_anchor_stops_migration_without_partial_writes(self):
        p = self.new()
        self.new(901)
        watcher = self.root / "docs/watcher.md"
        watcher.write_text("[ambiguous](product/features.md#unmapped-section)\n")
        before = p.read_bytes()
        with self.assertRaises(docctl.DocError):
            self.new(902)
        self.assertEqual(p.read_bytes(), before)
        self.assertEqual(watcher.read_text(), "[ambiguous](product/features.md#unmapped-section)\n")
        self.assertFalse((self.root / "docs/product/features").exists())

    def test_index_failure_during_expansion_restores_source_and_inbound_links(self):
        p = self.new()
        self.new(901)
        docctl.generate_indexes(self.root)
        watcher = self.root / "docs/watcher.md"
        watcher.write_text("[first](product/features.md#feat-900)\n")
        before = p.read_bytes()
        with mock.patch.object(docctl, "generate_indexes", side_effect=OSError("injected index failure")):
            with self.assertRaises(OSError):
                self.new(902)
        self.assertEqual(p.read_bytes(), before)
        self.assertEqual(watcher.read_text(), "[first](product/features.md#feat-900)\n")
        self.assertFalse((self.root / "docs/product/features").exists())
        self.assertTrue(docctl.validate(self.root)["ok"])

    def test_plan_expansion_repairs_task_handover_metadata(self):
        self.new(key="plan", slug="first")
        self.new(901, key="plan", slug="second")
        task = self.new(key="task")
        task.write_text(task.read_text().replace("handover_ref: null", 'handover_ref: "docs/work/plans.md#plan-900"'))
        self.new(902, key="plan", slug="third")
        record = self.records("task")[0]
        self.assertEqual(record["handover_ref"], "docs/work/plans/PLAN-900-first.md#plan-900")
        self.assertTrue(docctl.validate(self.root)["ok"])

    def test_migration_repairs_inbound_links_outside_docs(self):
        p = self.new(slug="first")
        self.new(901, slug="second")
        guide = self.root / "guides/guide.md"
        guide.parent.mkdir()
        guide.write_text("[first](../docs/product/features.md#feat-900)\n")
        self.new(902, slug="third")
        self.assertFalse(p.exists())
        self.assertIn("../docs/product/features/FEAT-900-first.md#feat-900", guide.read_text())

    def test_old_entry_heading_anchor_remains_valid_after_expansion(self):
        p = self.new(slug="first", title="登录")
        self.new(901, slug="second")
        watcher = self.root / "docs/watcher.md"
        old_anchor = docctl.heading_anchor("FEAT-900 · 登录")
        watcher.write_text(f"[first](product/features.md#{old_anchor})\n")
        self.new(902, slug="third")
        self.assertFalse(p.exists())
        self.assertTrue(docctl.validate(self.root)["ok"])

    def test_registered_type_outside_collection_is_rejected(self):
        p = self.new()
        p.rename(self.root / "docs/unregistered.md")
        p.parent.rmdir()
        self.assertFalse(docctl.validate(self.root)["ok"])

    def test_expanded_file_cannot_hold_multiple_compact_entries(self):
        p = self.new()
        self.new(901)
        text = p.read_text()
        p.unlink()
        directory = self.root / "docs/product/features"
        directory.mkdir()
        (directory / "anything.md").write_text(text)
        self.assertFalse(docctl.validate(self.root)["ok"])

    def test_protocol_fenced_examples_are_not_records(self):
        policy = self.root / "docs/_system/writing-policy.md"
        self.assertIn("```yaml doc-meta", policy.read_text())
        self.assertEqual(docctl.collect_records(self.root), [])

    def test_compact_and_expanded_body_sources_are_rejected(self):
        compact = self.new()
        saved = compact.read_text()
        self.new(901)
        self.new(902)
        compact.write_text(saved)
        self.assertFalse(docctl.validate(self.root)["ok"])

    def test_thin_redirect_can_preserve_old_stable_anchor(self):
        compact = self.new(slug="first")
        self.new(901, slug="second")
        self.new(902, slug="third")
        compact.write_text('<!-- doc-redirect -->\n# 已迁移\n\n此集合已展开，请使用新入口。\n\n'
                           '<a id="feat-900"></a>\n[原条目](features/FEAT-900-first.md#feat-900)\n')
        self.assertTrue(docctl.validate(self.root)["ok"])
        self.assertEqual(len(self.records()), 3)

    def test_redirect_cannot_hide_old_body_or_metadata(self):
        compact = self.new()
        saved = compact.read_text()
        self.new(901)
        self.new(902)
        compact.write_text("<!-- doc-redirect -->\n" + saved)
        self.assertFalse(docctl.validate(self.root)["ok"])

    def test_third_item_left_in_compact_file_is_rejected(self):
        p = self.new()
        text = p.read_text()
        p.write_text(text + text[text.index('<a id='):].replace("FEAT-900", "FEAT-901").replace("feat-900", "feat-901") +
                     text[text.index('<a id='):].replace("FEAT-900", "FEAT-902").replace("feat-900", "feat-902"))
        self.assertFalse(docctl.validate(self.root)["ok"])

    def test_empty_collection_directory_is_rejected(self):
        (self.root / "docs/research/feedback").mkdir(parents=True)
        self.assertFalse(docctl.validate(self.root)["ok"])

    def test_empty_business_document_is_rejected(self):
        p = self.root / "docs/research/feedback.md"
        p.parent.mkdir()
        p.write_text("# 用户反馈\n")
        self.assertFalse(docctl.validate(self.root)["ok"])

    def test_missing_per_item_metadata_is_rejected(self):
        p = self.new()
        p.write_text(p.read_text().replace('id: "FEAT-900"\n', ""))
        self.assertFalse(docctl.validate(self.root)["ok"])

    def test_duplicate_record_id_is_caught(self):
        p = self.new()
        (self.root / "docs/duplicate.md").write_text(p.read_text())
        result = docctl.validate(self.root)
        self.assertTrue(any("重复 ID FEAT-900" in e for e in result["errors"]))

    def test_active_placeholder_and_missing_approval_caught(self):
        p = self.new()
        p.write_text(p.read_text().replace('status: "draft"', 'status: "active"'))
        result = docctl.validate(self.root)
        self.assertTrue(any("active 文档仍包含" in e for e in result["errors"]))
        self.assertTrue(any("缺少批准依据" in e for e in result["errors"]))

    def test_verification_requires_evidence_pair(self):
        p = self.new()
        p.write_text(p.read_text().replace("verified_at: null", 'verified_at: "2026-10-01"'))
        result = docctl.validate(self.root)
        self.assertTrue(any("必须同时填写" in e for e in result["errors"]))

    def test_routes_resolve_existing_compact_and_expanded_targets(self):
        self.new()
        self.assertIn("docs/product/features.md", docctl.show_routes(self.root, "billing")[0]["must_read"])
        self.new(901)
        self.new(902)
        targets = docctl.show_routes(self.root, "billing")[0]["must_read"]
        self.assertTrue(any(p.startswith("docs/product/features/") or p == "docs/product/features" for p in targets))
        self.assertNotIn("docs/product/features.md", targets)

    def test_route_missing_content_does_not_create_shells(self):
        before = sorted(p.relative_to(self.root).as_posix() for p in self.root.rglob("*"))
        result = docctl.show_routes(self.root, "billing")
        self.assertEqual(result[0]["id"], "billing")
        after = sorted(p.relative_to(self.root).as_posix() for p in self.root.rglob("*"))
        self.assertEqual(before, after)
        self.assertFalse((self.root / "docs/product").exists())

    def test_compact_indexes_have_individual_anchors(self):
        self.new()
        self.new(901)
        result = docctl.generate_indexes(self.root)
        self.assertEqual(result["records"], 2)
        page = self.root / "docs/_generated/indexes/feature/page-001.md"
        self.assertIn("features.md#feat-900", page.read_text())
        self.assertIn("features.md#feat-901", page.read_text())
        self.assertTrue(docctl.validate(self.root)["ok"])

    def test_pagination_and_determinism(self):
        template = (self.root / "docs/_templates/feature.md").read_text()
        directory = self.root / "docs/product/features"
        directory.mkdir(parents=True)
        for n in range(1, 44):
            text = template.replace('id: "{{ID}}"', f'id: "FEAT-{n:04d}"').replace('status: "template"', 'status: "draft"')
            text = text.replace('slug: "{{SLUG}}"', 'slug: "sample"').replace("# {{TITLE}}", f"# 功能 {n}")
            (directory / f"FEAT-{n:04d}-sample.md").write_text(text)
        result = docctl.generate_indexes(self.root)
        self.assertEqual(result["page_size"], 40)
        pages = sorted((self.root / "docs/_generated/catalog/feature").glob("page-*.json"))
        self.assertEqual([len(json.loads(p.read_text())["records"]) for p in pages], [40, 3])
        before = {p.relative_to(self.root): p.read_bytes() for p in (self.root / "docs/_generated").rglob("*") if p.is_file()}
        docctl.generate_indexes(self.root)
        after = {p.relative_to(self.root): p.read_bytes() for p in (self.root / "docs/_generated").rglob("*") if p.is_file()}
        self.assertEqual(before, after)
        self.assertTrue(docctl.validate(self.root)["ok"])

    def test_check_never_executes_registered_commands(self):
        p = self.root / "docs/_system/commands.json"
        data = json.loads(p.read_text())
        marker = self.root / "MUST_NOT_EXIST"
        data["commands"][0]["argv"] = [sys.executable, "-c", f"open({str(marker)!r},'w').write('bad')"]
        data["commands"][0]["cwd"] = "."
        p.write_text(json.dumps(data))
        docctl.validate(self.root)
        self.assertFalse(marker.exists())

    def test_cli_exit_codes(self):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(docctl.cli(["--root", str(self.root), "check"]), 0)
            self.assertEqual(docctl.cli(["--root", str(self.root), "check", "--strict"]), 1)
            self.assertEqual(docctl.cli(["--root", str(self.root), "route", "does-not-exist"]), 2)


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="docs-install-test-")
        self.root = (Path(self.tmp.name) / "repo").resolve()

    def tearDown(self):
        self.tmp.cleanup()

    def test_default_install_creates_only_system_and_reference_sources(self):
        result = init_docs.install(KIT_ROOT, self.root)
        self.assertEqual(result["business_documents"], [])
        self.assertEqual(sorted(p.name for p in (self.root / "docs").iterdir()),
                         ["AGENTS.md", "README.md", "_system", "_templates", "_tools"])
        self.assertTrue((self.root / "AGENTS.md").is_file())
        self.assertFalse((self.root / "_AGENTS.md").exists())

    def test_dry_run_never_writes(self):
        result = init_docs.install(KIT_ROOT, self.root, dry_run=True)
        self.assertTrue(result["dry_run"])
        self.assertFalse(self.root.exists())

    def test_existing_entry_is_preserved_without_partial_install(self):
        self.root.mkdir()
        (self.root / "README.md").write_text("existing project facts")
        with self.assertRaises(init_docs.InstallError):
            init_docs.install(KIT_ROOT, self.root)
        self.assertEqual((self.root / "README.md").read_text(), "existing project facts")
        self.assertFalse((self.root / "docs").exists())

    def test_explicit_overview_has_only_user_supplied_facts(self):
        init_docs.install(KIT_ROOT, self.root, overview_title="项目", overview_summary="用户提供的项目目的")
        p = self.root / "docs/project/overview.md"
        self.assertIn("用户提供的项目目的", p.read_text())
        self.assertEqual(docctl.parse_frontmatter(p.read_text())["status"], "draft")
        self.assertTrue(docctl.validate(self.root)["ok"])

    def test_incomplete_overview_request_is_rejected(self):
        with self.assertRaises(init_docs.InstallError):
            init_docs.install(KIT_ROOT, self.root, overview_title="项目")
        self.assertFalse(self.root.exists())

    def test_whitespace_overview_is_rejected_without_writing(self):
        with self.assertRaises(init_docs.InstallError):
            init_docs.install(KIT_ROOT, self.root, overview_title="   ", overview_summary="   ")
        self.assertFalse(self.root.exists())

    def test_symlink_destination_is_rejected(self):
        self.root.mkdir()
        outside = Path(self.tmp.name) / "outside"
        outside.mkdir()
        (self.root / "docs").symlink_to(outside, target_is_directory=True)
        with self.assertRaises(init_docs.InstallError):
            init_docs.install(KIT_ROOT, self.root)
        self.assertEqual(list(outside.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
