"""Prove the external Todo oracles accept valid candidates and reject regressions."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


EVAL_ROOT = Path(__file__).resolve().parent
FIXTURE = EVAL_ROOT / "fixtures/vite-todo"
VERIFIERS = EVAL_ROOT / "verifiers"
CORRECT_RENAME = """
export function renameTodo(todos: Todo[], id: string, text: string): Todo[] {
  const trimmed = text.trim()
  if (!trimmed || !todos.some((todo) => todo.id === id)) return todos
  return todos.map((todo) => todo.id === id ? { ...todo, text: trimmed } : todo)
}
"""


def add_correct_edit_ui(project):
    """Inject a valid temporary candidate, leaving the golden fixture untouched."""
    source = project / "src/App.tsx"
    text = source.read_text(encoding="utf-8")
    text = text.replace("removeTodo, toggleTodo }", "removeTodo, toggleTodo, renameTodo }")
    text = text.replace("  const [draft, setDraft] = useState('')", """  const [draft, setDraft] = useState('')
  const [editing, setEditing] = useState<string | null>(null)
  const [editDraft, setEditDraft] = useState('')
  function saveEdit(id: string) {
    if (!editDraft.trim()) return
    setTodos((current) => renameTodo(current, id, editDraft))
    setEditing(null)
  }""")
    original = """                <label className="todo-label">
                  <input type="checkbox" checked={todo.completed} onChange={() => setTodos((current) => toggleTodo(current, todo.id))} />
                  <span>{todo.text}</span>
                </label>"""
    replacement = """                {editing === todo.id ? <>
                  <input aria-label="编辑待办内容" value={editDraft} onChange={(event) => setEditDraft(event.target.value)} onKeyDown={(event) => {
                    if (event.key === 'Enter') { event.preventDefault(); saveEdit(todo.id) }
                    if (event.key === 'Escape') { event.preventDefault(); setEditing(null) }
                  }} />
                  <button type="button" onClick={() => saveEdit(todo.id)}>保存</button>
                  <button type="button" onClick={() => setEditing(null)}>取消</button>
                </> : <>
                  <label className="todo-label">
                    <input type="checkbox" checked={todo.completed} onChange={() => setTodos((current) => toggleTodo(current, todo.id))} />
                    <span>{todo.text}</span>
                  </label>
                  <button type="button" onClick={() => { setEditing(todo.id); setEditDraft(todo.text) }}>编辑</button>
                </>}"""
    if original not in text:
        raise AssertionError("Fixture changed: review the temporary UI candidate injection")
    source.write_text(text.replace(original, replacement), encoding="utf-8")


@unittest.skipUnless(shutil.which("node"), "Node >=22.18 required for Todo external oracles")
class TodoVerifierTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="todo-oracle-test-")
        self.project = Path(self.temp.name).resolve() / "project"
        shutil.copytree(FIXTURE, self.project, ignore=shutil.ignore_patterns("node_modules", "dist"))

    def tearDown(self):
        self.temp.cleanup()

    def run_verifier(self, name, expected_exit, env=None):
        environment = os.environ.copy()
        if env is not None:
            environment.update(env)
        completed = subprocess.run(["node", str(VERIFIERS / (name + ".mjs")), str(self.project)],
                                   text=True, capture_output=True, env=environment, timeout=90)
        self.assertEqual(completed.returncode, expected_exit, completed.stdout + completed.stderr)
        evidence = json.loads(completed.stdout)
        self.assertEqual(evidence["status"], {0: "passed", 1: "failed", 2: "infrastructure_error"}[expected_exit])
        self.assertTrue(evidence["checks"])
        self.assertTrue(all(isinstance(item["name"], str) and isinstance(item["passed"], bool)
                            for item in evidence["checks"]))
        if expected_exit == 0:
            self.assertTrue(all(item["passed"] for item in evidence["checks"]))
            self.assertIn("_PASS", evidence["marker"])
        else:
            self.assertTrue(any(not item["passed"] for item in evidence["checks"]))
            self.assertNotIn("marker", evidence)
        return evidence

    def change_logic(self, before, after):
        source = self.project / "src/lib/todos.ts"
        text = source.read_text(encoding="utf-8")
        self.assertIn(before, text)
        source.write_text(text.replace(before, after), encoding="utf-8")

    def add_rename(self, candidate=CORRECT_RENAME):
        source = self.project / "src/lib/todos.ts"
        with source.open("a", encoding="utf-8") as handle:
            handle.write(candidate)

    def test_baseline_passes_behavior_oracle(self):
        evidence = self.run_verifier("todo-behavior", 0)
        self.assertEqual(len(evidence["checks"]), 7)

    def test_toggle_all_regression_fails(self):
        self.change_logic("todo.id === id ? { ...todo, completed: !todo.completed } : todo",
                          "{ ...todo, completed: !todo.completed }")
        self.run_verifier("todo-behavior", 1)

    def test_unknown_id_regression_fails(self):
        self.change_logic("export function toggleTodo(todos: Todo[], id: string): Todo[] {",
                          "export function toggleTodo(todos: Todo[], id: string): Todo[] {\n"
                          "  if (!todos.some((todo) => todo.id === id)) id = todos[0]?.id ?? ''")
        self.run_verifier("todo-behavior", 1)

    def test_storage_key_regression_fails(self):
        source = self.project / "src/lib/todo-storage.ts"
        source.write_text(source.read_text().replace("vite-todo.items.v1", "changed.key"), encoding="utf-8")
        self.run_verifier("todo-behavior", 1)

    def test_storage_roundtrip_regression_fails(self):
        source = self.project / "src/lib/todo-storage.ts"
        source.write_text(source.read_text().replace("JSON.stringify(todos)",
                          "JSON.stringify(todos.map((todo) => ({ ...todo, completed: false })))"), encoding="utf-8")
        self.run_verifier("todo-behavior", 1)

    def test_unmodified_fixture_fails_feature_oracle(self):
        self.run_verifier("todo-edit", 1)

    def test_valid_temporary_rename_candidate_passes(self):
        self.add_rename()
        self.run_verifier("todo-edit", 0)
        self.run_verifier("todo-behavior", 0)

    def test_rename_all_rows_regression_fails(self):
        self.add_rename(CORRECT_RENAME.replace("todo.id === id ? { ...todo, text: trimmed } : todo",
                                             "{ ...todo, text: trimmed }"))
        self.run_verifier("todo-edit", 1)

    def test_rename_resets_completion_regression_fails(self):
        self.add_rename(CORRECT_RENAME.replace("{ ...todo, text: trimmed }",
                                             "{ ...todo, text: trimmed, completed: false }"))
        self.run_verifier("todo-edit", 1)

    def test_rename_accepts_blank_title_regression_fails(self):
        self.add_rename(CORRECT_RENAME.replace("!trimmed || ", ""))
        self.run_verifier("todo-edit", 1)

    def test_invalid_submitted_source_is_behavior_failure(self):
        (self.project / "src/lib/todos.ts").write_text("this is invalid TypeScript", encoding="utf-8")
        self.run_verifier("todo-behavior", 1)

    def test_ui_missing_trusted_dependencies_is_infrastructure_failure(self):
        self.run_verifier("todo-edit-ui", 2, {"EVAL_TODO_NODE_MODULES": ""})

    @unittest.skipUnless(os.environ.get("EVAL_RUN_BROWSER_TESTS") == "1",
                         "Set EVAL_RUN_BROWSER_TESTS=1 with trusted dependencies and an available browser")
    def test_browser_rejects_domain_only_feature_and_accepts_working_ui(self):
        dependencies = os.environ.get("EVAL_TODO_NODE_MODULES", str(FIXTURE / "node_modules"))
        self.add_rename()
        self.run_verifier("todo-edit-ui", 1, {"EVAL_TODO_NODE_MODULES": dependencies})
        add_correct_edit_ui(self.project)
        self.run_verifier("todo-edit-ui", 0, {"EVAL_TODO_NODE_MODULES": dependencies})

    @unittest.skipUnless(os.environ.get("EVAL_RUN_BROWSER_TESTS") == "1",
                         "Set EVAL_RUN_BROWSER_TESTS=1 with trusted dependencies and an available browser")
    def test_browser_rejects_edit_input_without_required_accessible_name(self):
        dependencies = os.environ.get("EVAL_TODO_NODE_MODULES", str(FIXTURE / "node_modules"))
        self.add_rename()
        add_correct_edit_ui(self.project)
        source = self.project / "src/App.tsx"
        source.write_text(source.read_text(encoding="utf-8").replace('aria-label="编辑待办内容" ', ''),
                          encoding="utf-8")
        evidence = self.run_verifier("todo-edit-ui", 1, {"EVAL_TODO_NODE_MODULES": dependencies})
        self.assertIn("编辑待办内容", evidence["error"])


if __name__ == "__main__":
    unittest.main()
