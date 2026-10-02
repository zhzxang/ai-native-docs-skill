# 小事清单（Vite Todo）

一个可独立运行的 React + TypeScript 前端样本，用于本地 AI 文档场景评测。项目由官方 `create-vite@9.2.1` 的 `react-ts` 模板生成，随后加入 Todo 功能。依赖版本由 `package-lock.json` 固定。

## 运行

要求 Node.js 22.18.0 或更高版本（推荐 Node.js 24 LTS）与 npm。Node 内置 TypeScript 类型擦除用于运行领域测试，不另装测试框架。

```bash
npm ci
npm run dev
```

Vite 开发服务器默认使用 `http://localhost:5173`；端口被占用时以终端输出为准。

```bash
npm test          # Node 内置测试，验证 Todo 规则与持久化
npm run lint     # Oxlint 静态检查
npm run build    # tsc -b 类型检查，然后 Vite 构建到 dist/
npm run preview  # 预览已生成的 dist/
```

## 功能与数据

- 新增 Todo：去除首尾空白；拒绝空白文本；输入最多 200 个字符；ID 由浏览器 `crypto.randomUUID()` 生成。
- 勾选完成状态、删除条目、按全部 / 待完成 / 已完成筛选、清空已完成条目。
- 首次打开为空清单；修改后将全部 Todo 保存到当前浏览器的 `localStorage`，键为 `vite-todo.items.v1`。
- 单条 Todo 的数据结构为 `{ id: string, text: string, completed: boolean }`。
- 遇到损坏的 JSON 或非数组存储时恢复为空清单；跳过字段无效和 ID 重复的条目。浏览器存储不可用时页面仍可操作，并显示持久化失败提示。

## 模块与数据流

| 路径 | 职责 |
| --- | --- |
| `index.html` | HTML 入口，加载 `src/main.tsx` |
| `src/main.tsx` | 在 React `StrictMode` 中将 `App` 挂载到 `#root` |
| `src/App.tsx` | 表单、列表、筛选、计数和状态；调用领域与存储模块 |
| `src/lib/todos.ts` | 不依赖 React / 浏览器的纯函数：`addTodo`、`toggleTodo`、`removeTodo`、`filterTodos`、`clearCompleted` |
| `src/lib/todo-storage.ts` | `STORAGE_KEY`、`loadTodos`、`saveTodos`；通过传入的 Storage 接口读写与验证 Todo |
| `src/App.css`、`src/index.css` | 组件样式、全局字体和基础样式 |
| `tests/todos.test.mjs` | Node 内置测试，直接导入 TypeScript 领域与存储模块 |
| `vite.config.ts` | Vite 的 React 插件配置 |

`App` 的 `useState` 初始化器通过 `loadTodos(window.localStorage)` 读取数据；用户事件通过领域纯函数更新状态；`useEffect` 在 Todo 状态变化时调用 `saveTodos`。筛选状态只影响显示，不写入存储。

这是单页面本地 Todo：没有后端服务、数据库、登录、路由或应用运行时网络请求。构建输出与依赖目录不属于评测输入快照。
