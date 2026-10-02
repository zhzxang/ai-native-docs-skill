#!/usr/bin/env node
// External acceptance oracle: never import the submitted project's tests.
import assert from 'node:assert/strict'
import path from 'node:path'
import { pathToFileURL } from 'node:url'

const checks = []
let currentCheck = 'load submitted Todo source'
function check(name, fn) {
  currentCheck = name
  fn()
  checks.push({ name, passed: true })
}
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
  for (const name of ['addTodo', 'toggleTodo', 'removeTodo', 'filterTodos', 'clearCompleted']) {
    assert.equal(typeof todos[name], 'function', `Missing export ${name}`)
  }
  for (const name of ['loadTodos', 'saveTodos']) assert.equal(typeof storage[name], 'function', `Missing export ${name}`)
  check('add trims text, preserves existing rows and rejects invalid input', () => {
    const original = frozenTodos()
    const added = todos.addTodo(original, '  New task  ', 'four')
    assert.deepEqual(added, [...original, { id: 'four', text: 'New task', completed: false }])
    original.forEach((row, index) => assert.equal(added[index], row))
    assert.deepEqual(todos.addTodo(original, ' \t\n ', 'four'), original)
    assert.deepEqual(todos.addTodo(original, 'Duplicate', 'two'), original)
    assert.deepEqual(todos.addTodo(original, 'Missing ID', ''), original)
  })
  check('toggle changes only the requested row in either direction', () => {
    const original = frozenTodos()
    const changed = todos.toggleTodo(original, 'one')
    assert.deepEqual(changed, [{ ...original[0], completed: true }, original[1], original[2]])
    assert.equal(changed[1], original[1])
    assert.equal(changed[2], original[2])
    assert.deepEqual(todos.toggleTodo(original, 'two'), [original[0], { ...original[1], completed: false }, original[2]])
    assert.deepEqual(todos.toggleTodo(changed, 'one'), original)
  })
  check('unknown and empty toggle IDs leave all rows untouched', () => {
    const original = frozenTodos()
    for (const id of ['missing', '']) {
      const result = todos.toggleTodo(original, id)
      assert.deepEqual(result, original)
      original.forEach((row, index) => assert.equal(result[index], row))
    }
    assert.deepEqual(todos.toggleTodo([], 'missing'), [])
  })
  check('remove, filter and clear preserve IDs, order and surviving rows', () => {
    const original = frozenTodos()
    const removed = todos.removeTodo(original, 'two')
    assert.deepEqual(removed, [original[0], original[2]])
    assert.equal(removed[0], original[0])
    assert.equal(removed[1], original[2])
    assert.deepEqual(todos.removeTodo(original, 'missing'), original)
    assert.deepEqual(todos.filterTodos(original, 'all'), original)
    assert.deepEqual(todos.filterTodos(original, 'active'), [original[0], original[2]])
    assert.deepEqual(todos.filterTodos(original, 'completed'), [original[1]])
    assert.deepEqual(todos.clearCompleted(original), [original[0], original[2]])
    assert.deepEqual(todos.clearCompleted([]), [])
  })
  check('storage writes the unchanged versioned key and round-trips toggled data', () => {
    assert.equal(storage.STORAGE_KEY, 'vite-todo.items.v1')
    const values = new Map()
    const backend = {
      getItem: (key) => values.get(key) ?? null,
      setItem: (key, value) => values.set(key, value),
    }
    assert.deepEqual(storage.loadTodos(backend), [])
    const changed = todos.toggleTodo(frozenTodos(), 'one')
    storage.saveTodos(backend, changed)
    assert.deepEqual([...values.keys()], ['vite-todo.items.v1'])
    assert.equal(values.get('vite-todo.items.v1'), JSON.stringify(changed))
    assert.deepEqual(storage.loadTodos(backend), changed)
  })
  check('malformed storage is safe and duplicate/invalid rows are ignored', () => {
    const load = (value) => storage.loadTodos({ getItem: () => value })
    for (const value of [null, '{bad', '{}', 'null', '42']) assert.deepEqual(load(value), [])
    const good = { id: 'one', text: 'Keep', completed: false }
    assert.deepEqual(load(JSON.stringify([
      good, { ...good, text: 'Duplicate' }, null,
      { id: '', text: 'No ID', completed: false },
      { id: 'two', text: ' \t ', completed: false },
      { id: 'three', text: 'Wrong flag', completed: 'true' },
    ])), [good])
  })
  check('storage access failures propagate to the caller', () => {
    const failure = new Error('Storage unavailable')
    assert.throws(() => storage.loadTodos({ getItem: () => { throw failure } }), (error) => error === failure)
    assert.throws(() => storage.saveTodos({ setItem: () => { throw failure } }, []), (error) => error === failure)
  })
  console.log(JSON.stringify({ status: 'passed', checks, marker: 'TODO_BEHAVIOR_PASS' }))
}

try {
  await main()
} catch (error) {
  checks.push({ name: currentCheck, passed: false, detail: error.message })
  console.log(JSON.stringify({ status: error.infrastructure ? 'infrastructure_error' : 'failed', checks, error: error.message }))
  process.exitCode = error.infrastructure ? 2 : 1
}
