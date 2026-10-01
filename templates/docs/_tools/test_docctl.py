"""Tests for the documentation helper, not the user's application."""
from __future__ import annotations

import contextlib
import io
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import docctl

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
        self.root = Path(self.tmp.name) / "repo"
        shutil.copytree(KIT_ROOT, self.root, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))

    def tearDown(self):
        self.tmp.cleanup()

    def test_pristine_structure_passes(self):
        result = docctl.validate(self.root)
        self.assertTrue(result["ok"], result["errors"])

    def test_uninitialized_strict_readiness_fails(self):
        result = docctl.validate(self.root, strict=True)
        self.assertFalse(result["ok"])
        self.assertTrue(any("bootstrap" in e for e in result["errors"]))

    def test_templates_are_not_records(self):
        records = docctl.collect_records(self.root)
        self.assertTrue(records)
        self.assertTrue(all(r["status"] != "template" for r in records))
        self.assertTrue(all("_template" not in r["path"] for r in records))

    def test_new_feature_is_draft_with_title(self):
        p = docctl.make_new(self.root, "feature", "FEAT-900", "subscription", "订阅功能")
        data = docctl.parse_frontmatter(p.read_text())
        self.assertEqual(data["status"], "draft")
        self.assertIsNone(data["verified_at"])
        self.assertIn("# 订阅功能", p.read_text())
        self.assertEqual(docctl.find_records(self.root, query="订阅功能")["total_matches"], 1)

    def test_duplicate_id_and_overwrite_rejected(self):
        p = docctl.make_new(self.root, "feature", "FEAT-900", "one", "原记录")
        original = p.read_bytes()
        with self.assertRaises(docctl.DocError):
            docctl.make_new(self.root, "feature", "FEAT-900", "two", "新记录")
        self.assertEqual(p.read_bytes(), original)

    def test_invalid_slug_and_wrong_prefix_rejected(self):
        with self.assertRaises(docctl.DocError):
            docctl.make_new(self.root, "feature", "FEAT-900", "../escape", "标题")
        with self.assertRaises(docctl.DocError):
            docctl.make_new(self.root, "feature", "TASK-900", "valid", "标题")

    def test_path_escape_rejected(self):
        with self.assertRaises(docctl.DocError):
            docctl.safe_path(self.root, "../outside")
        with self.assertRaises(docctl.DocError):
            docctl.safe_path(self.root, "/tmp/outside")

    def test_bug_task_and_state_query(self):
        docctl.make_new(self.root, "task", "TASK-900", "bug", "订阅问题", kind="bug")
        result = docctl.find_records(self.root, typ="task", state="queued", kind="bug")
        self.assertEqual(result["total_matches"], 1)

    def test_external_tracker_rejects_duplicate_local_source(self):
        p = self.root / "docs/_system/project-map.json"
        data = json.loads(p.read_text())
        data["work_tracking"]["mode"] = "external"
        p.write_text(json.dumps(data))
        with self.assertRaises(docctl.DocError):
            docctl.make_new(self.root, "task", "TASK-900", "bug", "问题", kind="bug")

    def test_broken_link_is_caught(self):
        p = self.root / "docs/project/overview.md"
        p.write_text(p.read_text() + "\n[broken](missing-file.md)\n")
        result = docctl.validate(self.root)
        self.assertTrue(any("missing-file.md" in e for e in result["errors"]))

    def test_duplicate_record_id_is_caught(self):
        p = docctl.make_new(self.root, "feature", "FEAT-900", "one", "原记录")
        shutil.copyfile(p, p.with_name("FEAT-901-copy.md"))
        result = docctl.validate(self.root)
        self.assertTrue(any("重复 ID FEAT-900" in e for e in result["errors"]))

    def test_active_placeholder_and_missing_approval_caught(self):
        p = docctl.make_new(self.root, "feature", "FEAT-900", "one", "功能")
        p.write_text(p.read_text().replace('status: "draft"', 'status: "active"'))
        result = docctl.validate(self.root)
        self.assertTrue(any("active 文档仍包含" in e for e in result["errors"]))
        self.assertTrue(any("缺少批准依据" in e for e in result["errors"]))

    def test_verification_requires_evidence_pair(self):
        p = self.root / "docs/project/overview.md"
        p.write_text(p.read_text().replace('verified_at: null', 'verified_at: "2026-10-01"'))
        result = docctl.validate(self.root)
        self.assertTrue(any("必须同时填写" in e for e in result["errors"]))

    def test_routes_resolve_and_have_existing_targets(self):
        routes = docctl.show_routes(self.root, "billing")
        self.assertEqual(routes[0]["id"], "billing")
        for ref in routes[0]["must_read"]:
            self.assertTrue(docctl.safe_path(self.root, ref).exists())

    def test_pagination_and_determinism(self):
        template = (self.root / "docs/product/features/_template.md").read_text()
        for n in range(1, 44):
            text = template.replace('id: "{{ID}}"', f'id: "FEAT-{n:04d}"').replace('status: "template"', 'status: "draft"')
            (self.root / f"docs/product/features/FEAT-{n:04d}-sample.md").write_text(text)
        result = docctl.generate_indexes(self.root)
        self.assertEqual(result["page_size"], 40)
        path = self.root / "docs/_generated/catalog/feature"
        pages = sorted(path.glob("page-*.json"))
        self.assertEqual(len(pages), 2)
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


if __name__ == "__main__":
    unittest.main()
