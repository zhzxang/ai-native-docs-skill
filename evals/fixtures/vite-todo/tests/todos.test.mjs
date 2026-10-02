import assert from 'node:assert/strict'
import test from 'node:test'
import { addTodo, clearCompleted, filterTodos, removeTodo, toggleTodo } from '../src/lib/todos.ts'
import { loadTodos, saveTodos, STORAGE_KEY } from '../src/lib/todo-storage.ts'

test('adding trims text and rejects blank titles or duplicate IDs', () => {
  const empty = []
  const todos = addTodo(empty, '  Read a chapter  ', 'one')
  assert.deepEqual(todos, [{ id: 'one', text: 'Read a chapter', completed: false }])
  assert.deepEqual(empty, [])
  assert.equal(addTodo(todos, '   ', 'two'), todos)
  assert.equal(addTodo(todos, 'Duplicate', 'one'), todos)
  assert.equal(addTodo(todos, 'No ID', ''), todos)
})

test('toggle, filters, remove, and clear preserve the other todos', () => {
  const original = addTodo(addTodo([], 'First task', 'one'), 'Second task', 'two')
  const changed = toggleTodo(original, 'one')
  assert.equal(original[0].completed, false)
  assert.equal(changed[0].completed, true)
  assert.deepEqual(filterTodos(changed, 'all'), changed)
  assert.deepEqual(filterTodos(changed, 'active'), [changed[1]])
  assert.deepEqual(filterTodos(changed, 'completed'), [changed[0]])
  assert.deepEqual(clearCompleted(changed), [changed[1]])
  assert.deepEqual(removeTodo(changed, 'two'), [changed[0]])
  assert.deepEqual(toggleTodo(changed, 'missing'), changed)
})

test('storage round-trips todos using the versioned localStorage key', () => {
  const values = new Map()
  const storage = {
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, value),
  }
  assert.deepEqual(loadTodos(storage), [])
  const todos = toggleTodo(addTodo([], 'Persist me', 'one'), 'one')
  saveTodos(storage, todos)
  assert.equal(values.get(STORAGE_KEY), JSON.stringify(todos))
  assert.deepEqual(loadTodos(storage), todos)
})

test('invalid storage returns an empty list and invalid or duplicate rows are skipped', () => {
  const load = (value) => loadTodos({ getItem: () => value })
  assert.deepEqual(load('{broken'), [])
  assert.deepEqual(load('{}'), [])
  const valid = { id: 'one', text: 'Keep this', completed: false }
  assert.deepEqual(load(JSON.stringify([
    valid,
    { ...valid, text: 'Duplicate ID' },
    { id: 'two', text: '', completed: false },
    { id: 'three', text: 'Wrong type', completed: 'true' },
    null,
  ])), [valid])
})

test('storage access errors propagate so the UI can report persistence failure', () => {
  const error = new Error('Storage unavailable')
  assert.throws(() => loadTodos({ getItem: () => { throw error } }), error)
  assert.throws(() => saveTodos({ setItem: () => { throw error } }, []), error)
})
