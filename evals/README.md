# 本地场景评测

项目样本、用户请求、预期结果和运行产物全部保存在本地。评测通过 Codex CLI 在项目副本执行任务，再由独立 Python 程序检查文件、内容、元数据和操作范围。支持 macOS / Linux，要求 Python 3.10+，框架仅使用标准库。

Codex 引擎使用本机已经登录的 CLI，默认沿用当前模型与用户配置。模型执行仍需要正常的 Codex 服务连接并消耗相应额度；“本地”指输入、项目和报告的存储位置。`tools` 引擎不调用模型、不需要登录或联网，用于检查脚本和验收规则，不计为 Codex 行为评测。

## 开始运行

以下命令在本仓库根目录执行：

```bash
# 列出所有场景，或只看 Vite 样本
python3 evals/run.py list
python3 evals/run.py list --tag vite

# 校验配置并查看选择结果；不写文件、不调用 Codex
python3 evals/run.py run --tag vite --dry-run

# 不消耗模型额度的脚本冒烟检查
python3 evals/run.py run --engine tools

# Codex：只跑一次 Vite 初始化
python3 evals/run.py run --case vite-init

# Codex：运行 Vite 的所有场景，每条独立执行三次
python3 evals/run.py run --tag vite --repeat 3 --timeout 600

# Todo：文档写入、新增编辑功能、修复切换 bug
# 提前安装样本依赖可离线准备功能与修复场景
npm ci --prefix evals/fixtures/vite-todo
python3 evals/run.py run --tag todo-development --timeout 1200

# 运行完整 Codex 评测集
python3 evals/run.py run

# 可选：指定模型、Codex 可执行文件或结果目录
python3 evals/run.py run --case vite-init --model YOUR_MODEL \
  --codex-bin /absolute/path/to/codex --results-dir /absolute/path/to/results
```

`--case` 可重复，也支持用引号包住的通配符，例如 `--case 'python-*'`。多个 `--tag` 要求用例同时具有这些标签。`--ignore-user-config` 可忽略用户 `config.toml`；默认关闭，确保沿用你当前 CLI 的模型配置。若需要比较版本，显式固定模型和配置。不同 CLI 版本支持的参数可能不同，本框架使用 `--json`、`--ephemeral`、`--sandbox workspace-write` 和 `--add-dir`。

退出码：`0` 所有验收通过；`1` 至少一项任务或验收失败；`2` 配置、登录、连接、超时、准备环境或 grader 运行故障。报告区分任务失败与基础设施错误；失败不会自动重试或被后续通过覆盖。

## 内置样本与场景

| 项目 | 场景 | 验收重点 |
| --- | --- | --- |
| `empty-project` | 初始化、只预览、重复初始化 | 五个最小文件；预览不写项目；重复执行不改变字节 |
| `vite-todo` | 初始化、来源同步、阅读代码补充事实、产品文档写入、新增编辑功能、修复切换 bug | 文档事实与改动范围；领域逻辑、真实浏览器交互与持久化；回归测试和构建 |
| `python-cli` | 初始化同步、重复同步、保留人工内容 | 来源草案；唯一对象；元数据；库存 CLI 行为不变 |
| `legacy-docs` | 只初始化、授权迁移 | 不隐式迁移；完整正文与附件；双向链接和薄跳转；范围边界 |

共 14 条场景。`vite-code-facts` 与以下三条 Todo 开发场景只支持 `codex` 引擎；`tools` 模式会说明并跳过它们，其余 10 条执行真实文档工具。

| 用例 | 真实请求 | 独立验收 |
| --- | --- | --- |
| `vite-doc-write` | 阅读源码，写入 `FEAT-TODO-001` 产品功能草案 | 六种操作、数据字段、存储键与异常处理；元数据保持未核验、未批准；仅新增功能文档 |
| `vite-feature-edit` | 增加待办编辑，补充文档和回归测试 | 编辑领域逻辑、浏览器保存/取消和 Enter/Escape、刷新持久化、原功能保持；测试和 TypeScript 构建 |
| `vite-bug-toggle` | 根据用户复现步骤修复勾选一条却切换全部的问题 | 准备阶段在副本注入 bug；检查仅目标 ID 切换、未知 ID 与输入不变、原功能与存储；测试和 TypeScript 构建 |

三条场景均先初始化并同步文档，再记录各自基线。它们不共享上一条的修改；新增功能与 bug 修复要求实际修改回归测试并维护文档。评测控制侧冻结的外部验收脚本保存在项目副本之外，业务自身 `npm test` 通过不能替代独立验收。添加用例不代表已通过真实 Codex 实跑，通过状态以结果报告为准。

[Vite Todo](fixtures/vite-todo/README.md) 使用官方 create-vite React + TypeScript 脚手架生成，包含新增、切换完成、删除、筛选、清空已完成和浏览器持久化。要求 Node.js 22.18+；通过 `npm ci` 安装依赖后可运行 `npm run dev`、`npm test`、`npm run lint`、`npm run build`。样本快照省略依赖和构建输出。文档场景不安装或构建业务项目；编辑和 bug 修复场景用 `node_dependencies` 准备动作核对 npm 已安装元数据与项目锁文件，再把依赖复制到独立副本运行测试和构建；依赖内容和符号链接另有完整哈希，复用与重评时会检查完整性。建议提前执行 `npm ci --prefix evals/fixtures/vite-todo`，便于离线准备；没有本地依赖或安装元数据不匹配时，runner 会在冻结输入副本中执行 `npm ci --ignore-scripts --no-audit --no-fund`，需要 npm 服务连接。浏览器交互验收自动发现 Codex 捆绑的 Playwright 与本机 Chrome；也可用 `EVAL_PLAYWRIGHT_MODULE`、`EVAL_BROWSER_EXECUTABLE` 指定运行时。缺少运行时会报告基础设施错误，不能跳过后计为通过。

## 目录与结果

```text
evals/
├── fixtures/          # 内置样本源码，不在原目录运行文档任务
├── projects/          # 项目清单；source 相对于 evals/，也支持绝对目录
├── cases/             # 场景：真实请求、初始状态、独立验收规则
├── graders.py         # 确定性验收
├── verifiers/         # 冻结在控制侧的业务与浏览器验收脚本
├── run.py             # 命令入口
├── local-projects/    # 用户导入的冻结样本，Git 忽略
└── results/           # 每次运行的独立目录，Git 忽略
```

每次运行先冻结当前工作区的四个 Skill 和资源包、项目样本、场景和 grader 源码，并保存 SHA-256；包括未提交的 Skill 修改，不仅使用 Git HEAD。每次尝试再创建独立项目和 Skill 副本，准备指定初始状态后记录基线，以新 Codex 会话执行。项目工作区与计划目录允许写入，原样本不加入 CLI 的可写目录。入口提示显式提供待测 Skill 路径，因此当前评测验证执行能力，尚未验证 Skill 自动发现。

一次运行会保存：

- `report.md`、`report.json`：逐项验收、状态、耗时、各场景通过次数与运行次数。
- `inputs/`：冻结的样本、Skill、场景、grader、哈希与版本信息。
- `<case>/attempt-N/project/`：任务执行后的项目。
- `<case>/attempt-N/before/`：准备好初始状态的项目副本。
- `<case>/attempt-N/plans/`：工具计划、映射和执行证据。
- `<case>/attempt-N/artifacts/`：请求、JSONL 事件、stderr、最终回复、执行信息、基线、文件差异和验收结果。

`--timeout` 限制每个准备或目标进程；超时会终止进程组。命令断言的超时上限是 60 秒。重复运行不会共享项目状态；报告保留所有尝试，Codex 事件中有用量时一并记录。

文件哈希、ID、状态、命令和迁移正文有确定性规则；文档措辞允许差异。`vite-code-facts` 检查一组关键事实和名称，不等价于对完整架构解释的语义审查。Todo 开发场景另外执行外部业务验收；编辑功能还在真实浏览器中检查交互与刷新后持久化。当前版本没有模型 judge。`check` 普通检查与 strict 就绪分别配置，不统一要求初始化后的 strict 检查通过。

此框架用于可控的本地回归测试；预期规则不会传给目标提示。普通 CLI 文件读取权限并不形成“隐藏答案”安全隔离，若以后需要严格盲测，应在容器或独立环境限制可见文件系统。

## 不重新调用 Codex，重评已保存产物

```bash
python3 evals/run.py grade /absolute/path/to/evals/results/RUN_ID
```

使用该次运行保存的场景、grader 和公共资源重新检查最终项目，更新同一报告。目标未完成的登录、连接或超时故障保留；任务已完成但验收命令暂时故障的记录可重新验收。修改结果项目用于诊断后可以重评，但这不代表模型重新执行后已经通过。冻结资源被修改时拒绝重评。

## 导入你的本地项目

```bash
python3 evals/run.py import-project --id my-frontend \
  --source /absolute/path/to/project \
  --description "现有前端的固定评测快照"
```

创建 `local-projects/my-frontend/` 和 `projects/local/my-frontend.json`，不修改原项目，也不覆盖同名样本。快照省略 `.git`、依赖、缓存、构建产物、`.env` 与 `.env.*`，并拒绝符号链接；这不是完整的凭据扫描，导入前检查其他凭据文件和生产数据。源目录不能包含快照目标目录，以避免递归复制。

然后复制一条相近场景到 `cases/local/`，改成自己的项目 ID、用户请求和预期事实。项目清单的 `source` 相对于 `evals/`，与清单放在哪个子目录无关；`--cases-dir`、`--projects-dir` 支持使用其他本地清单目录。

真实样本通常需要：项目目录、技术栈与启动/测试命令、用户会提出的任务、必须保留的文件，以及至少几项人工确认的业务或架构事实。内置 Todo 已可作为第一份样本，后续真实项目可以逐个加入。

## 添加场景

场景 JSON 示例：

```json
{
  "version": 1,
  "id": "my-frontend-init",
  "title": "已有前端只接入最小文档系统",
  "project": "my-frontend",
  "tags": ["frontend", "init"],
  "prompt": "请使用 ai-docs-init 初始化当前项目。我授权预览并应用同一计划，计划放在 {plans}。保留原 README 和源码，本次只初始化。",
  "steps": [{"action": "init", "plan": "init.json"}],
  "assertions": [
    {"kind": "exists", "paths": ["AGENTS.md", "docs/README.md", "docs/AGENTS.md", "docs/.ai-docs.json"]},
    {"kind": "unchanged", "patterns": ["src/**", "package.json"]},
    {"kind": "only_changes", "allowed": ["README.md", "AGENTS.md", "docs/README.md", "docs/AGENTS.md", "docs/.ai-docs.json"]},
    {"kind": "doc_check", "expected_exit": 0}
  ]
}
```

提示支持 `{project}`、`{skills}`、`{plans}`。`setup` 是任务开始前的状态准备，完成后记录基线；`steps` 只用于 `tools` 冒烟引擎，从不传给 Codex。可用动作：`init`、`sync`、带 `mapping.documents` 的 `migrate`、`write`、`append`、`replace` 和 `node_dependencies`。`replace` 用 `path`、`old`、`new` 精确替换唯一文本，适合在副本注入 bug；`node_dependencies` 冻结项目依赖并复制到每个尝试副本；本地没有依赖时在冻结输入副本安装，不修改原样本。工具动作先保存计划再应用，`preview: true` 只预览；计划文件名应在同一次尝试中唯一。仅支持 Codex 的场景设置 `"engines": ["codex"]` 并省略 `steps`。

| 断言 kind | 字段 | 含义 |
| --- | --- | --- |
| `exists` / `absent` | `paths` | 路径存在 / 不存在 |
| `unchanged` | 可选 `paths`、`patterns` | 选中的基线文件内容不变；均省略时检查全部基线文件 |
| `only_changes` | `allowed` | 新增、修改、删除必须属于这些 glob；空数组要求无变化 |
| `changed` | 可选 `paths`、`patterns`、`min_count` | 至少指定数量的匹配文件发生变化；默认一份 |
| `contains` / `not_contains` | `path`，`text` 或 `texts` | 必要正文或禁止正文 |
| `regex` | `path`、`pattern` | 正文满足正则 |
| `json_value` | `path`、`pointer`、`value` | RFC 6901 指针指向的 JSON 值匹配 |
| `doc_meta` | `path`、`fields`、可选 `record_id`、`optional_null_fields` | 指定文档对象的元数据匹配；可选 null 字段允许缺省或 null，拒绝非空值 |
| `record_count` | `type`、`count` | 某类型对象数量 |
| `doc_check` | 可选 `strict`、`expected_exit` | 用冻结的公共工具验证文档结构 |
| `redirect` | `path`、可选 `target` | 旧文档是薄跳转，可核对目标文本 |
| `command` | `argv`、可选 `expected_exit`、`stdout_contains`、`timeout` | 在最终项目执行 argv，不使用 shell |
| `external_verifier` | `script`、可选 `expected_exit`、`timeout` | 运行控制侧冻结的独立 Node 验收脚本，以项目副本为输入 |

每条断言可设置唯一 `id`。断言路径必须在项目内；不允许绝对路径或 `..`。`command` 的 `{python}` 使用评测 Python 解释器。命令断言会执行用例作者提供的程序，仅应运行你信任的本地评测集；命令应只读或将临时状态写到项目副本，不触碰原项目。命令日志保存到 artifacts。目录与 glob 的改动检测忽略依赖、缓存和构建产物。

## 开发验证

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s evals -p 'test_*.py'
python3 evals/run.py run --engine tools
```

测试覆盖正确/错误验收、输入路径、CLI 协议与故障、重复状态隔离、重评和超时清理。`tools` 和假 CLI 的框架测试都不计为真实 Codex 评测。
