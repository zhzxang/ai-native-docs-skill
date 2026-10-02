#!/usr/bin/env node
// External rename acceptance oracle; the baseline intentionally lacks this export.
import assert from 'node:assert/strict'
import path from 'node:path'
import { pathToFileURL } from 'node:url'

const checks = []
let currentCheck = 'load submitted source and renameTodo export'
function check(name, fn) { currentCheck = name; fn(); checks.push({ name, passed: true }) }
function frozenTodos() {
  return Object.freeze([
    Object.freeze({ id: 'one', text: 'Read', completed: false }),
    Object.freeze({ id: 'two', text: 'Walk', completed: true }),
    Object.freeze({ id: 'three', text: 'Write', completed: false }),
  ])
}

async function main() {
  const project = process.argv[2]
  if (!project || !path.isAbsolute(project)) throw Object.assign(new Error('Expected absolute project path'), { infrastructure: true })
  const [major, minor] = process.versions.node.split('.').map(Number)
  if (major < 22 || (major === 22 && minor < 18)) throw Object.assign(new Error('Node >=22.18 is required for native TypeScript imports'), { infrastructure: true })
  const todos = await import(pathToFileURL(path.join(project, 'src/lib/todos.ts')).href)
  const storage = await import(pathToFileURL(path.join(project, 'src/lib/todo-storage.ts')).href)
  assert.equal(typeof todos.renameTodo, 'function', 'Missing export renameTodo(todos, id, text)')
  check('rename trims the title while preserving ID, completion, order and other objects', () => {
    const original = frozenTodos()
    const renamed = todos.renameTodo(original, 'two', ' \t 散步二十分钟 \n ')
    assert.deepEqual(renamed, [original[0], { id: 'two', text: '散步二十分钟', completed: true }, original[2]])
    assert.equal(renamed[0], original[0])
    assert.equal(renamed[2], original[2])
    assert.deepEqual(todos.renameTodo(original, 'one', 'Updated'), [{ ...original[0], text: 'Updated' }, original[1], original[2]])
  })
  check('blank titles and missing IDs are no-ops without mutating input', () => {
    const original = frozenTodos()
    for (const [id, title] of [['one', ' \t\n '], ['missing', 'Replacement'], ['', 'Replacement']]) {
      const result = todos.renameTodo(original, id, title)
      assert.deepEqual(result, original)
      original.forEach((row, index) => assert.equal(result[index], row))
    }
    assert.deepEqual(todos.renameTodo([], 'missing', 'Replacement'), [])
  })
  check('renaming keeps all five original operations usable', () => {
    const original = frozenTodos()
    const renamed = todos.renameTodo(original, 'two', 'New walk')
    const added = todos.addTodo(renamed, '  Added  ', 'four')
    assert.deepEqual(added, [...renamed, { id: 'four', text: 'Added', completed: false }])
    assert.deepEqual(todos.addTodo(renamed, ' ', 'four'), renamed)
    assert.deepEqual(todos.addTodo(renamed, 'Duplicate', 'two'), renamed)
    assert.deepEqual(todos.addTodo(renamed, 'No ID', ''), renamed)
    const toggled = todos.toggleTodo(renamed, 'one')
    assert.deepEqual(toggled, [{ ...renamed[0], completed: true }, renamed[1], renamed[2]])
    assert.deepEqual(todos.toggleTodo(renamed, 'missing'), renamed)
    assert.deepEqual(todos.removeTodo(renamed, 'two'), [renamed[0], renamed[2]])
    assert.deepEqual(todos.removeTodo(renamed, 'missing'), renamed)
    assert.deepEqual(todos.filterTodos(renamed, 'all'), renamed)
    assert.deepEqual(todos.filterTodos(renamed, 'active'), [renamed[0], renamed[2]])
    assert.deepEqual(todos.filterTodos(renamed, 'completed'), [renamed[1]])
    assert.deepEqual(todos.clearCompleted(renamed), [renamed[0], renamed[2]])
  })
  check('renamed title persists through the original localStorage key', () => {
    assert.equal(storage.STORAGE_KEY, 'vite-todo.items.v1')
    const values = new Map()
    const backend = { getItem: (key) => values.get(key) ?? null, setItem: (key, value) => values.set(key, value) }
    const renamed = todos.renameTodo(frozenTodos(), 'two', 'Renamed permanently')
    storage.saveTodos(backend, renamed)
    assert.deepEqual([...values.keys()], ['vite-todo.items.v1'])
    assert.equal(values.get('vite-todo.items.v1'), JSON.stringify(renamed))
    assert.deepEqual(storage.loadTodos(backend), renamed)
  })
  console.log(JSON.stringify({ status: 'passed', checks, marker: 'TODO_EDIT_PASS' }))
}

try {
  await main()
} catch (error) {
  checks.push({ name: currentCheck, passed: false, detail: error.message })
  console.log(JSON.stringify({ status: error.infrastructure ? 'infrastructure_error' : 'failed', checks, error: error.message }))
  process.exitCode = error.infrastructure ? 2 : 1
}
