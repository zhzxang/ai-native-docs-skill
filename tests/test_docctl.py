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

ROOT = Path(__file__).resolve().parents[1]
KIT_ROOT = ROOT / "skills/ai-docs-check/assets/templates"
sys.path.insert(0, str(KIT_ROOT / "docs/_tools"))
import docctl
import init_docs



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


class MetaSchemaTests(unittest.TestCase):
    """Generated and migrated candidates share the same type-aware contract."""

    def meta(self, typ="feature"):
        text = (KIT_ROOT / f"docs/_templates/{typ}.md").read_text()
        data = docctl.parse_frontmatter(text)
        data.update({"id": "TEST-1", "slug": "candidate", "status": "draft",
                     "summary": None, "applies_to": None})
        return data

    def test_all_shared_templates_have_valid_declared_type_rules(self):
        seen = set()
        for path in (KIT_ROOT / "docs/_templates").rglob("*.md"):
            if path.name == "SKILL.md":
                continue
            meta = docctl.parse_frontmatter(path.read_text(), str(path))
            if meta is not None:
                seen.add(meta["type"])
                self.assertEqual(docctl.validate_meta(meta, str(path), allow_template=True), [])
        self.assertEqual(seen, set(docctl.meta_schema()["types"]))

    def test_unknown_facts_are_nullable_and_drafts_need_no_complete_body(self):
        self.assertEqual(docctl.validate_meta(self.meta()), [])

    def test_known_field_types_and_empty_strings_are_rejected(self):
        for field, value in (("owner", True), ("summary", 8), ("type", 4),
                             ("authority", False), ("verified_at", 20261002),
                             ("summary", "  "), ("owner", "")):
            with self.subTest(field=field, value=value):
                meta = self.meta()
                meta[field] = value
                self.assertTrue(any(field in error for error in docctl.validate_meta(meta)))

    def test_schema_required_keys_are_distinct_from_nullable_values(self):
        for typ, field in (("feature", "owner"), ("feature", "approved_by"),
                           ("task", "state"), ("task", "priority"),
                           ("release", "release_state"), ("pricing", "effective_from")):
            with self.subTest(typ=typ, field=field):
                meta = self.meta(typ)
                del meta[field]
                self.assertTrue(any("缺少元数据" in error and field in error
                                    for error in docctl.validate_meta(meta)))

    def test_unknown_type_and_type_specific_authority_are_rejected(self):
        meta = self.meta()
        meta["type"] = "invented-type"
        self.assertTrue(any("未登记文档 type" in error for error in docctl.validate_meta(meta)))
        meta = self.meta()
        meta["authority"] = "descriptive"
        self.assertTrue(any("非法 authority" in error for error in docctl.validate_meta(meta)))

    def test_task_and_release_state_are_enums(self):
        for typ, field in (("task", "state"), ("task", "kind"), ("release", "release_state")):
            with self.subTest(typ=typ, field=field):
                meta = self.meta(typ)
                meta[field] = "unknown"
                self.assertTrue(any("非法 " + field in error for error in docctl.validate_meta(meta)))
                meta[field] = None
                self.assertTrue(any(field in error for error in docctl.validate_meta(meta)))

    def test_type_specific_dates_reject_invalid_or_unzoned_values(self):
        for typ, field, value in (("approval", "valid_until", "2026-02-30"),
                                  ("pricing", "effective_from", "2026-10-02T09:00:00"),
                                  ("privacy", "effective_until", False)):
            with self.subTest(typ=typ, field=field):
                meta = self.meta(typ)
                meta[field] = value
                self.assertTrue(any(field in error for error in docctl.validate_meta(meta)))
        meta = self.meta("approval")
        meta["valid_from"] = "2026-10-02T09:00:00+08:00"
        self.assertEqual(docctl.validate_meta(meta), [])

    def test_verification_pair_and_active_approval_are_checked_independently(self):
        meta = self.meta()
        meta["verified_at"] = "2026-10-02"
        self.assertTrue(any("必须同时填写" in error for error in docctl.validate_meta(meta)))
        meta["verification_ref"] = "source:1"
        meta["status"] = "active"
        self.assertTrue(any("缺少批准依据" in error for error in docctl.validate_meta(meta)))
        meta.update({"approved_by": "Owner", "approval_ref": "approval:1"})
        self.assertEqual(docctl.validate_meta(meta), [])

    def test_known_fields_cannot_be_mixed_between_document_types(self):
        meta = self.meta()
        meta["release_state"] = "planned"
        self.assertTrue(any("release_state 不适用于" in error for error in docctl.validate_meta(meta)))

    def test_unknown_flat_extensions_are_preserved_with_warning(self):
        meta = self.meta()
        meta.update({"vendor_flag": True, "vendor_count": 2, "vendor_note": "Fact", "vendor_null": None})
        self.assertEqual(docctl.validate_meta(meta), [])
        with tempfile.TemporaryDirectory(prefix="doc-meta-staging-") as name:
            path = Path(name) / "candidate.md"
            path.write_text("---\n" + docctl.metadata_text(meta) + "\n---\n# 候选\n待完善\n")
            result = docctl.check_meta([path])
            self.assertTrue(result["ok"], result["errors"])
            self.assertEqual(len(result["warnings"]), 4)
            self.assertEqual(docctl.parse_frontmatter(path.read_text()), meta)
        meta["vendor_note"] = {"nested": "invalid"}
        self.assertTrue(any("平面 JSON 标量" in error for error in docctl.validate_meta(meta)))

    def test_template_candidates_require_explicit_template_mode(self):
        meta = docctl.parse_frontmatter((KIT_ROOT / "docs/_templates/feature.md").read_text())
        self.assertTrue(docctl.validate_meta(meta))
        self.assertEqual(docctl.validate_meta(meta, allow_template=True), [])

    def test_check_meta_supports_frontmatter_and_compact_candidates_outside_a_project(self):
        with tempfile.TemporaryDirectory(prefix="doc-meta-staging-") as name:
            root = Path(name)
            meta = self.meta()
            frontmatter = root / "overview.md"
            frontmatter.write_text("---\n" + docctl.metadata_text(meta) + "\n---\n# 候选\n待完善\n")
            meta2 = self.meta("task")
            meta2["id"] = "TEST-2"
            compact = root / "tasks.md"
            compact.write_text("# 工作项\n\n" + docctl.compact_entry_text(
                {"meta": meta2, "anchor": "test-2", "title": "任务", "body": "### 待完善\n"}))
            result = docctl.check_meta([frontmatter, compact])
            self.assertTrue(result["ok"], result["errors"])
            self.assertEqual(result["records"], 2)
            self.assertEqual(result["files_checked"], 2)
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = docctl.cli(["--root", str(root / "uninitialized"), "check-meta",
                                   str(frontmatter), str(compact)])
            self.assertEqual(code, 0)
            self.assertTrue(json.loads(output.getvalue())["ok"])

    def test_check_meta_reports_missing_metadata_and_bad_scalars_in_json(self):
        with tempfile.TemporaryDirectory(prefix="doc-meta-staging-") as name:
            plain = Path(name) / "plain.md"
            plain.write_text("# 普通文档\n")
            invalid = Path(name) / "invalid.md"
            invalid.write_text('---\nowner: ["nested"]\n---\n# Invalid\n')
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = docctl.cli(["check-meta", str(plain), str(invalid)])
            self.assertEqual(code, 1)
            result = json.loads(output.getvalue())
            self.assertFalse(result["ok"])
            self.assertEqual(result["files_checked"], 2)
            self.assertEqual(len(result["errors"]), 2)

    def test_candidate_ids_are_unique_across_files(self):
        with tempfile.TemporaryDirectory(prefix="doc-meta-staging-") as name:
            paths = [Path(name) / "one.md", Path(name) / "two.md"]
            for path in paths:
                path.write_text("---\n" + docctl.metadata_text(self.meta()) + "\n---\n# Candidate\n")
            result = docctl.check_meta(paths)
            self.assertTrue(any("重复 ID TEST-1" in error for error in result["errors"]))


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

    def test_check_rejects_known_metadata_field_with_wrong_scalar_type(self):
        path = self.new()
        path.write_text(path.read_text().replace("owner: null", "owner: true"))
        result = docctl.validate(self.root)
        self.assertTrue(any("owner 类型须为" in error for error in result["errors"]))

    def test_business_template_status_cannot_hide_a_record_from_check(self):
        path = self.new()
        path.write_text(path.read_text().replace('status: "draft"', 'status: "template"'))
        result = docctl.validate(self.root)
        self.assertFalse(result["ok"])
        self.assertTrue(any("status 不得为 template" in error for error in result["errors"]))
        original = path.read_bytes()
        with self.assertRaisesRegex(docctl.DocError, "status 不得为 template"):
            self.new(slug="other", title="Another topic")
        self.assertEqual(path.read_bytes(), original)

    def test_business_singleton_cannot_claim_shared_template_status(self):
        source = KIT_ROOT / "docs/_templates/reference/engineering/architecture/overview.md"
        path = self.root / "docs/engineering/architecture/overview.md"
        path.parent.mkdir(parents=True)
        path.write_text(source.read_text().replace("{{VERSION_OR_SCOPE}}", "Current source"))
        result = docctl.validate(self.root)
        self.assertFalse(result["ok"])
        self.assertTrue(any("status 不得为 template" in error for error in result["errors"]))

    def test_new_cannot_reemit_invalid_existing_compact_metadata(self):
        for count in (1, 2):
            with self.subTest(existing_records=count):
                path = self.new(key="feedback")
                if count == 2:
                    self.new(901, key="feedback")
                path.write_text(path.read_text().replace("owner: null", "owner: 17", 1))
                before = {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
                with self.assertRaisesRegex(docctl.DocError, "owner 类型须为"):
                    self.new(902, key="feedback")
                self.assertEqual(before, {p.relative_to(self.root): p.read_bytes()
                                          for p in self.root.rglob("*") if p.is_file()})
                self.assertFalse((self.root / "docs/research/feedback").exists())
                path.unlink()

    def test_direct_expansion_checks_every_emitted_metadata_block(self):
        path = self.new()
        self.new(901)
        entries = docctl.parse_compact_entries(path.read_text())
        entries[0]["meta"]["owner"] = False
        item = next(item for item in docctl.registry(self.root)["collections"] if item["key"] == "feature")
        before = path.read_bytes()
        with self.assertRaisesRegex(docctl.DocError, "owner 类型须为"):
            docctl.expand_collection(self.root, item, entries)
        self.assertEqual(path.read_bytes(), before)
        self.assertFalse((self.root / "docs/product/features").exists())

    def test_new_validates_type_metadata_before_creating_business_files(self):
        resources = Path(self.tmp.name).resolve() / "invalid-resources"
        shutil.copytree(KIT_ROOT, resources, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        path = resources / "docs/_templates/feature.md"
        path.write_text(path.read_text().replace("owner: null", "owner: 17"))
        before = {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        with self.assertRaisesRegex(docctl.DocError, "元数据未通过类型校验"):
            docctl.make_new(self.root, "feature", "FEAT-900", "candidate", "候选", resources=resources)
        self.assertEqual(before, {p.relative_to(self.root): p.read_bytes()
                                  for p in self.root.rglob("*") if p.is_file()})
        self.assertFalse((self.root / "docs/product").exists())

    def test_uninitialized_strict_readiness_fails(self):
        result = docctl.validate(self.root, strict=True)
        self.assertFalse(result["ok"])
        self.assertTrue(any("bootstrap" in e for e in result["errors"]))

    def test_reference_sources_are_not_records(self):
        self.assertEqual(docctl.collect_records(self.root), [])
        self.assertFalse((self.root / "docs/product").exists())
        self.assertFalse((self.root / "docs/research").exists())
        self.assertFalse((self.root / "docs/_generated").exists())
        for folder in ("_system", "_tools", "_templates"):
            self.assertFalse((self.root / "docs" / folder).exists())

    def test_fixed_resource_version_mismatch_blocks_writes(self):
        path = self.root / "docs/.ai-docs.json"
        data = json.loads(path.read_text())
        data["system"]["version"] = "99.0.0"
        data["installation"]["system_version"] = "99.0.0"
        path.write_text(json.dumps(data))
        before = {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        with self.assertRaises(docctl.DocError):
            self.new()
        self.assertFalse(docctl.validate(self.root)["ok"])
        self.assertEqual(before, {p.relative_to(self.root): p.read_bytes()
                                  for p in self.root.rglob("*") if p.is_file()})

    def test_invalid_override_cannot_expand_the_threshold_or_create_business_files(self):
        path = self.root / "docs/.ai-docs.json"
        data = json.loads(path.read_text())
        registry = json.loads((KIT_ROOT / "docs/_system/collections.json").read_text())
        registry["defaults"]["compact_max_items"] = 3
        data["overrides"] = {"collections": registry}
        path.write_text(json.dumps(data))
        with self.assertRaises(docctl.DocError):
            self.new()
        self.assertFalse(docctl.validate(self.root)["ok"])
        self.assertFalse((self.root / "docs/product").exists())

    def test_source_template_check_retains_legacy_read_compatibility(self):
        result = docctl.validate(KIT_ROOT)
        self.assertTrue(result["ok"], result["errors"])

    def test_external_resource_path_controls_protocol_and_templates_without_copying_them(self):
        resources = Path(self.tmp.name).resolve() / "external-resources"
        shutil.copytree(KIT_ROOT, resources, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        path = resources / "docs/_templates/feedback.md"
        path.write_text(path.read_text().replace("## 来源与时间", "## 外部模板特有字段"))
        before = {p.relative_to(resources): (p.read_bytes(), p.stat().st_mtime_ns)
                  for p in resources.rglob("*") if p.is_file()}
        record = docctl.make_new(self.root, "feedback", "FB-1", "first", "First feedback", resources=resources)
        self.assertIn("### 外部模板特有字段", record.read_text())
        self.assertTrue(docctl.validate(self.root, resources=resources)["ok"])
        self.assertEqual(before, {p.relative_to(resources): (p.read_bytes(), p.stat().st_mtime_ns)
                                  for p in resources.rglob("*") if p.is_file()})
        self.assertFalse((self.root / "docs/_templates").exists())

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
        lock = self.root / "docs/.docctl.lock"
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
        p = self.root / "docs/.ai-docs.json"
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
        policy = KIT_ROOT / "docs/_system/writing-policy.md"
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
        template = (KIT_ROOT / "docs/_templates/feature.md").read_text()
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
        p = self.root / "docs/.ai-docs.json"
        data = json.loads(p.read_text())
        marker = self.root / "MUST_NOT_EXIST"
        command = json.loads((KIT_ROOT / "docs/_system/commands.json").read_text())["commands"][0]
        command.update({"argv": [sys.executable, "-c", f"open({str(marker)!r},'w').write('bad')"], "cwd": "."})
        data["commands"] = [command]
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

    def test_default_install_creates_only_lightweight_entries_and_configuration(self):
        result = init_docs.install(KIT_ROOT, self.root)
        self.assertEqual(result["business_documents"], [])
        self.assertEqual(sorted(p.name for p in (self.root / "docs").iterdir()),
                         [".ai-docs.json", "AGENTS.md", "README.md"])
        self.assertTrue((self.root / "AGENTS.md").is_file())
        self.assertFalse((self.root / "_AGENTS.md").exists())

    def test_dry_run_never_writes(self):
        result = init_docs.install(KIT_ROOT, self.root, dry_run=True)
        self.assertTrue(result["dry_run"])
        self.assertFalse(self.root.exists())

    def test_existing_entry_is_preserved_without_partial_install(self):
        self.root.mkdir()
        (self.root / "README.md").write_text("existing project facts")
        result = init_docs.install(KIT_ROOT, self.root)
        self.assertEqual(result["status"], "installed")
        self.assertTrue((self.root / "README.md").read_text().startswith("existing project facts"))
        self.assertTrue((self.root / "docs/.ai-docs.json").is_file())
        self.assertFalse((self.root / "docs/project").exists())

    def test_explicit_overview_is_rejected_with_the_independent_sync_entry(self):
        with self.assertRaisesRegex(init_docs.InstallError, "ai-docs-sync/scripts/sync.py"):
            init_docs.install(KIT_ROOT, self.root, overview_title="项目", overview_summary="用户提供的项目目的")
        self.assertFalse(self.root.exists())

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
