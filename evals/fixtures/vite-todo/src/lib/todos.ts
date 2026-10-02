export type Todo = {
  id: string
  text: string
  completed: boolean
}

export type TodoFilter = 'all' | 'active' | 'completed'

export function addTodo(todos: Todo[], text: string, id: string): Todo[] {
  const trimmed = text.trim()
  if (!trimmed || !id || todos.some((todo) => todo.id === id)) return todos
  return [...todos, { id, text: trimmed, completed: false }]
}

export function toggleTodo(todos: Todo[], id: string): Todo[] {
  return todos.map((todo) => todo.id === id ? { ...todo, completed: !todo.completed } : todo)
}

export function removeTodo(todos: Todo[], id: string): Todo[] {
  return todos.filter((todo) => todo.id !== id)
}

export function filterTodos(todos: Todo[], filter: TodoFilter): Todo[] {
  if (filter === 'all') return todos
  return todos.filter((todo) => filter === 'completed' ? todo.completed : !todo.completed)
}

export function clearCompleted(todos: Todo[]): Todo[] {
  return todos.filter((todo) => !todo.completed)
}
