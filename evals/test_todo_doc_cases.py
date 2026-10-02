"""Check the Todo document criteria against correct and misleading candidates."""
import json
from pathlib import Path
import tempfile
import unittest

try:
    from .graders import grade_case, snapshot_files, validate_assertions
except ImportError:
    from graders import grade_case, snapshot_files, validate_assertions


EVAL_ROOT = Path(__file__).resolve().parent
SKILLS = EVAL_ROOT.parent / "skills"
FEATURE_PATH = "docs/product/features.md"
FACT_IDS = {
    "todo-load-timing", "todo-save-effect", "todo-save-on-change",
    "todo-corrupt-empty", "todo-storage-error-feedback",
}
CHINESE_FACTS = [
    "初次渲染时，useState 使用 initialTodos 初始化待办列表；它通过 loadTodos 从 localStorage 读取。",
    "useEffect 会调用 saveTodos，使用既有存储键写入数据。",
    "依赖为 [todos]；todos 变化后触发保存，因此首次挂载及每次待办状态变化都同步到本地。",
    "loadTodos 用 JSON.parse 解析存储数据；解析失败、损坏 JSON 或非数组数据返回 [] 空列表。",
    "App 捕获 localStorage 读写异常。保存失败时显示浏览器存储不可用的提示，当前操作仍有效，刷新后可能丢失。",
]
ENGLISH_FACTS = [
    "On initial render useState invokes initialTodos, which reads localStorage through loadTodos.",
    "The useEffect callback invokes saveTodos with the current list.",
    "The effect depends on [todos], so todos changes trigger persistence.",
    "JSON.parse failures and invalid stored values return an empty array rather than crashing the app.",
    "App catches localStorage access errors and shows a warning message when saving fails; reload can lose this session's changes.",
]


def load_case(identifier):
    return json.loads((EVAL_ROOT / "cases" / (identifier + ".json")).read_text(encoding="utf-8"))


class TodoDocumentCaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="todo-doc-criteria-")
        self.root = Path(self.temp.name).resolve()
        self.project = self.root / "project"
        self.project.mkdir()
        self.artifacts = self.root / "artifacts"
        self.baseline = snapshot_files(self.project)
        case = load_case("vite-doc-write")
        self.facts = [assertion for assertion in case["assertions"] if assertion.get("id") in FACT_IDS]
        self.assertEqual({item["id"] for item in self.facts}, FACT_IDS)

    def tearDown(self):
        self.temp.cleanup()

    def write(self, relative, text):
        target = self.project / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")

    def grade(self, assertions):
        return grade_case({"assertions": assertions}, self.project, self.baseline,
                          self.artifacts, SKILLS)

    def write_facts(self, facts):
        self.write(FEATURE_PATH, "# Todo 功能说明\n\n" + "\n\n".join(facts) + "\n")

    def test_case_configuration_is_valid(self):
        for identifier in ("vite-doc-write", "vite-feature-edit", "vite-bug-toggle"):
            with self.subTest(case=identifier):
                validate_assertions(load_case(identifier)["assertions"])

    def test_correct_natural_language_facts_pass_in_chinese_and_english(self):
        for facts in (CHINESE_FACTS, ENGLISH_FACTS):
            self.write_facts(facts)
            with self.subTest(facts=facts):
                results = self.grade(self.facts)
                self.assertTrue(all(item["passed"] for item in results), results)

    def test_missing_fact_does_not_pass_from_function_names_alone(self):
        for missing, identifier in enumerate([
            "todo-load-timing", "todo-save-effect", "todo-save-on-change",
            "todo-corrupt-empty", "todo-storage-error-feedback",
        ]):
            facts = [fact for index, fact in enumerate(CHINESE_FACTS) if index != missing]
            # Names alone are insufficient to describe timing and failure behavior.
            facts.append("领域函数索引：loadTodos、saveTodos。")
            self.write_facts(facts)
            result = next(item for item in self.grade(self.facts) if item["id"] == identifier)
            with self.subTest(missing=identifier):
                self.assertFalse(result["passed"], result)

    def test_incorrect_timing_and_storage_claims_fail(self):
        replacements = [
            (0, "loadTodos 在用户每次点击筛选按钮时读取存储。", "todo-load-timing"),
            (1, "saveTodos 只在用户提交新增表单时执行。", "todo-save-effect"),
            (2, "保存只在用户手动点击持久化按钮时进行。", "todo-save-on-change"),
            (3, "JSON.parse 解析失败会直接抛出异常并停止页面渲染。", "todo-corrupt-empty"),
            (4, "App 不支持存储失败反馈，localStorage 异常直接抛给用户。", "todo-storage-error-feedback"),
        ]
        for position, wrong_fact, identifier in replacements:
            facts = CHINESE_FACTS.copy()
            facts[position] = wrong_fact
            self.write_facts(facts)
            result = next(item for item in self.grade(self.facts) if item["id"] == identifier)
            with self.subTest(incorrect=identifier):
                self.assertFalse(result["passed"], result)

    def existing_metadata_assertions(self, case):
        return [assertion for assertion in load_case(case)["assertions"]
                if assertion["kind"] == "doc_meta"
                and assertion["path"].startswith("docs/engineering/")]

    def write_metadata(self, assertion, **overrides):
        fields = {**assertion["fields"], **overrides}
        metadata = "\n".join(f"{key}: {json.dumps(value, ensure_ascii=False)}" for key, value in fields.items())
        self.write(assertion["path"], f"---\n{metadata}\n---\n\n# Existing document\n")

    def test_existing_documents_require_draft_with_unknown_approval(self):
        for case in ("vite-feature-edit", "vite-bug-toggle"):
            assertions = self.existing_metadata_assertions(case)
            self.assertEqual(len(assertions), 2)
            for assertion in assertions:
                self.assertEqual(assertion["fields"]["status"], "draft")
                self.assertEqual(assertion["optional_null_fields"], ["approved_by", "approval_ref"])
                self.write_metadata(assertion)
            with self.subTest(case=case):
                self.assertTrue(all(item["passed"] for item in self.grade(assertions)))
            for assertion in assertions:
                self.write_metadata(assertion, approved_by=None, approval_ref=None)
            with self.subTest(case=case, explicit_null=True):
                self.assertTrue(all(item["passed"] for item in self.grade(assertions)))

    def test_fabricated_approval_or_active_status_fails_for_each_existing_document(self):
        mutations = [
            {"status": "active"},
            {"approved_by": "Codex", "approval_ref": "self-reported approval"},
        ]
        for case in ("vite-feature-edit", "vite-bug-toggle"):
            for assertion in self.existing_metadata_assertions(case):
                for mutation in mutations:
                    self.write_metadata(assertion, **mutation)
                    with self.subTest(case=case, path=assertion["path"], mutation=mutation):
                        self.assertFalse(self.grade([assertion])[0]["passed"])


if __name__ == "__main__":
    unittest.main()
