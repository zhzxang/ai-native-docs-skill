import type { Todo } from './todos.ts'

export const STORAGE_KEY = 'vite-todo.items.v1'

export function loadTodos(storage: Pick<Storage, 'getItem'>): Todo[] {
  const serialized = storage.getItem(STORAGE_KEY)
  if (serialized === null) return []
  try {
    const value: unknown = JSON.parse(serialized)
    if (!Array.isArray(value)) return []
    const ids = new Set<string>()
    return value.filter((item): item is Todo => {
      if (typeof item !== 'object' || item === null) return false
      const todo = item as Partial<Todo>
      if (typeof todo.id !== 'string' || !todo.id || ids.has(todo.id)) return false
      if (typeof todo.text !== 'string' || !todo.text.trim() || typeof todo.completed !== 'boolean') return false
      ids.add(todo.id)
      return true
    })
  } catch {
    return []
  }
}

export function saveTodos(storage: Pick<Storage, 'setItem'>, todos: Todo[]): void {
  storage.setItem(STORAGE_KEY, JSON.stringify(todos))
}
