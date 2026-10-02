import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { addTodo, clearCompleted, filterTodos, removeTodo, toggleTodo } from './lib/todos.ts'
import type { Todo, TodoFilter } from './lib/todos.ts'
import { loadTodos, saveTodos } from './lib/todo-storage.ts'
import './App.css'

const filters: { value: TodoFilter; label: string }[] = [
  { value: 'all', label: '全部' },
  { value: 'active', label: '待完成' },
  { value: 'completed', label: '已完成' },
]

function initialTodos(): Todo[] {
  try {
    return loadTodos(window.localStorage)
  } catch {
    return []
  }
}

function App() {
  const [todos, setTodos] = useState<Todo[]>(initialTodos)
  const [draft, setDraft] = useState('')
  const [filter, setFilter] = useState<TodoFilter>('all')
  const [storageError, setStorageError] = useState(false)
  const activeCount = todos.filter((todo) => !todo.completed).length
  const completedCount = todos.length - activeCount
  const visibleTodos = filterTodos(todos, filter)

  useEffect(() => {
    try {
      saveTodos(window.localStorage, todos)
      // oxlint-disable-next-line react/set-state-in-effect -- Reflect the result of syncing with external browser storage.
      setStorageError(false)
    } catch {
      // oxlint-disable-next-line react/set-state-in-effect -- Report a failure from the external Storage API.
      setStorageError(true)
    }
  }, [todos])

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!draft.trim()) return
    setTodos((current) => addTodo(current, draft, crypto.randomUUID()))
    setDraft('')
  }

  return (
    <main className="page">
      <header className="page-header">
        <span className="brand"><span className="brand-mark" aria-hidden="true">✓</span> 小事清单</span>
        <span className="local-note"><span className="status-dot" /> 保存在此浏览器</span>
      </header>

      <section className="intro" aria-labelledby="page-title">
        <p className="eyebrow">ONE THING AT A TIME</p>
        <h1 id="page-title">把今天，<br /><span>一件件做好。</span></h1>
        <p className="intro-copy">腾出一点空间，留给真正想完成的事。</p>
      </section>

      <section className="todo-card" aria-labelledby="list-title">
        <div className="card-heading">
          <div><p className="eyebrow">YOUR DAILY LIST</p><h2 id="list-title">今天的待办</h2></div>
          <span className="remaining-count" aria-live="polite">{activeCount}<small>件待完成</small></span>
        </div>

        <form className="add-form" onSubmit={handleSubmit}>
          <label className="sr-only" htmlFor="todo-input">新待办内容</label>
          <input id="todo-input" value={draft} onChange={(event) => setDraft(event.target.value)} placeholder="接下来，想完成什么？" maxLength={200} autoComplete="off" />
          <button className="add-button" type="submit" disabled={!draft.trim()}><span aria-hidden="true">＋</span> 添加</button>
        </form>

        <div className="list-toolbar">
          <div className="filters" aria-label="筛选待办">
            {filters.map((item) => (
              <button key={item.value} type="button" aria-pressed={filter === item.value} onClick={() => setFilter(item.value)}>{item.label}</button>
            ))}
          </div>
          <span className="total-count">共 {todos.length} 件</span>
        </div>

        {visibleTodos.length > 0 ? (
          <ul className="todo-list">
            {visibleTodos.map((todo) => (
              <li key={todo.id} className={todo.completed ? 'todo-item completed' : 'todo-item'}>
                <label className="todo-label">
                  <input type="checkbox" checked={todo.completed} onChange={() => setTodos((current) => toggleTodo(current, todo.id))} />
                  <span>{todo.text}</span>
                </label>
                <button className="delete-button" type="button" aria-label={'删除：' + todo.text} onClick={() => setTodos((current) => removeTodo(current, todo.id))}>×</button>
              </li>
            ))}
          </ul>
        ) : (
          <div className="empty-state">
            <span className="empty-symbol" aria-hidden="true">✓</span>
            <h3>{filter === 'completed' ? '完成的事，会出现在这里' : filter === 'active' ? '待办已清空，享受这一刻' : '从一件小事开始'}</h3>
            <p>{filter === 'all' ? '写下一个想法，让今天有个轻盈的开始。' : '切换筛选，查看其他待办。'}</p>
          </div>
        )}

        <footer className="card-footer">
          <span>已完成 {completedCount} 件</span>
          <button type="button" disabled={completedCount === 0} onClick={() => setTodos(clearCompleted)}>清空已完成</button>
        </footer>
        {storageError && <p className="storage-error" role="status">浏览器存储不可用；本次操作仍然有效，刷新后可能丢失。</p>}
      </section>

      <footer className="page-footer">小步向前，也是一种进展。<span aria-hidden="true">✳</span></footer>
    </main>
  )
}

export default App
