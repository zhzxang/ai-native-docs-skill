# AI Native Docs

**简体中文** | [English](README.en.md)

**让 AI 编程助手能够找到、理解并持续维护项目知识。**

AI Native Docs 是一套由四个独立 Skill、Markdown 协议、类型模板和 Python 工具组成的文档系统。它为项目知识提供稳定入口、文档身份、来源与校验方式，帮助团队在代码变更、文档积累和 AI 协作过程中保持上下文可用。

从五个文件开始，按实际内容逐步扩展。

## 为什么需要它

项目知识通常散落在 README、需求说明、架构笔记和历史记录中。AI 能读到这些文件，却未必知道哪份是当前依据、哪些结论已核验，以及新内容应该放在哪里。

AI Native Docs 为这些问题提供一套可执行的约定：

- **轻量接入**：初始化只合并项目与文档的 README/AGENTS 入口和一份配置，不预建空分类树。
- **按内容生长**：集合的前两条文档保存在一个紧凑文件中，第三条出现时展开为独立文件并修复引用。
- **可追踪的知识**：文档使用稳定 ID，记录类型、状态、适用范围、来源与核验证据。
- **预览后应用**：初始化、同步和迁移均可先保存计划；应用时复验来源哈希、保护本地修改，并在可恢复的失败中回滚本次写入。
- **明确事实边界**：代码观察生成草案；业务含义、批准和命令核验仍需 AI 或人确认。
- **本地运行**：Python 3.10+，仅依赖标准库；工具不联网，也不执行目标项目的命令。

## 四个独立 Skill

| Skill | 用途 | 主要结果 |
| --- | --- | --- |
| [ai-docs-init](skills/ai-docs-init/SKILL.md) | 初始化新项目、接入已有项目或升级系统 | 合并四个入口，保存配置、资源版本与安装基线 |
| [ai-docs-sync](skills/ai-docs-sync/SKILL.md) | 从代码与构建清单补齐必要文档 | 生成架构总览和开发指南草案，安全刷新未被人工修改的工具草案 |
| [ai-docs-migrate](skills/ai-docs-migrate/SKILL.md) | 整理指定范围内的历史 Markdown | 根据显式映射迁移完整正文与元数据，修复引用，保留旧路径跳转入口 |
| [ai-docs-check](skills/ai-docs-check/SKILL.md) | 校验、检索和创建文档 | 检查类型 meta、ID、布局、配置与本地引用，并提供公共规则和模板 |

初始化、同步、迁移和校验分别执行。已有文档的项目可在初始化后迁移；只有代码的项目可在初始化后同步；空项目保持最小结构。

## 安装

需要 **Node.js（包含 npm/npx）** 和 Git。运行 Skill 中的工具需要 **Python 3.10+**；推荐 Python 3.11+，以便同步工具解析 `pyproject.toml` 和 `Cargo.toml` 的字段。

使用 [Skills CLI](https://github.com/vercel-labs/skills) 一次安装四个 Skill：

```bash
npx skills add zhzxang/ai-native-docs-skill \
  --skill ai-docs-init ai-docs-sync ai-docs-migrate ai-docs-check \
  --global
```

按提示选择使用的 AI 客户端。`--global` 将 Skill 安装到用户目录，便于多个项目复用，并让共享资源位于目标项目之外，满足迁移工具的要求。安装 Skill 后，再在目标项目中调用相应能力来创建文档入口。

如果只需要初始化，可安装最小组合；`ai-docs-check` 提供共享规则、模板和工具，必须一起安装：

```bash
npx skills add zhzxang/ai-native-docs-skill \
  --skill ai-docs-init ai-docs-check --global
```

查看可安装与已安装的 Skill：

```bash
npx skills add zhzxang/ai-native-docs-skill --list
npx skills list --global
```

更多安装选项见 [Skills CLI 官方说明](https://github.com/vercel-labs/skills#options)。

## 快速开始

安装完成后，在目标项目中向 AI 助手提出以下请求。

### 1. 初始化最小文档系统

```text
使用 ai-docs-init 为当前项目初始化最小文档系统，先给我看变更计划。
```

新项目的最小安装结构：

```text
your-project/
├── README.md          # 项目入口
├── AGENTS.md          # AI 执行约定
└── docs/
    ├── README.md      # 文档入口
    ├── AGENTS.md      # 文档写入约定
    └── .ai-docs.json  # 项目配置、资源版本与安装基线
```

已有入口通过托管区块合并，冲突会报告。规则、工具和模板留在 Skill 资源包中；业务文档在有实际内容时创建。旧完整安装的升级流程见 [已有项目接入说明](skills/ai-docs-init/references/existing-project.md)。

### 2. 按项目情况补齐文档（可选）

已有代码的项目，可同步架构总览与开发指南草案：

```text
使用 ai-docs-sync 阅读代码并补齐架构总览与开发指南草案。
```

有历史 Markdown 的项目，可明确范围后迁移：

```text
使用 ai-docs-migrate 迁移 legacy/ 内的 Markdown，保留全文并修复引用。
```

同步生成的草案记录可观察的代码路径和清单声明。模块职责、业务边界、数据流和命令含义需要进一步阅读代码确认；清单中的命令不会自动运行，也不会自动标记为已核验。

### 3. 校验文档

```text
使用 ai-docs-check 校验本次修改的文档，报告结构问题与待核验事实。
```

最小安装完成后，严格检查仍可能报告配置或核验证据待补充。安装完成、结构正确和严格就绪是三个不同结果。校验失败返回非零退出码，可用于自动化门禁。

## 手动运行脚本（可选）

也可以直接运行安装后的 Python 工具。以下命令在同一个 shell 会话中执行；将 `AI_DOCS_SKILLS` 替换为安装输出中包含四个 Skill 的实际父目录，`AI_DOCS_PROJECT` 替换为目标项目的绝对路径。计划目录须位于目标项目之外。

```bash
AI_DOCS_SKILLS="/absolute/path/to/installed/skills"
AI_DOCS_PROJECT="/absolute/path/to/your-project"
AI_DOCS_PLAN_DIR="$(mktemp -d)"
```

也可将 `AI_DOCS_SKILLS` 指向本源码仓库中 `skills/` 的绝对路径。

### 预览并初始化

```bash
# 只读盘点目标项目
python3 "$AI_DOCS_SKILLS/ai-docs-init/scripts/bootstrap.py" --target "$AI_DOCS_PROJECT" --scan

# 预览变更，保存完整计划
python3 "$AI_DOCS_SKILLS/ai-docs-init/scripts/bootstrap.py" \
  --target "$AI_DOCS_PROJECT" --summary \
  --plan-file "$AI_DOCS_PLAN_DIR/init.json"

# 查看计划中的具体变更
cat "$AI_DOCS_PLAN_DIR/init.json"

# 审阅后应用同一计划
python3 "$AI_DOCS_SKILLS/ai-docs-init/scripts/bootstrap.py" \
  --target "$AI_DOCS_PROJECT" --apply --summary \
  --plan-file "$AI_DOCS_PLAN_DIR/init.json"
```

### 初始化后从代码同步草案

```bash
python3 "$AI_DOCS_SKILLS/ai-docs-sync/scripts/sync.py" \
  --target "$AI_DOCS_PROJECT" \
  --plan-file "$AI_DOCS_PLAN_DIR/sync.json"

cat "$AI_DOCS_PLAN_DIR/sync.json"

python3 "$AI_DOCS_SKILLS/ai-docs-sync/scripts/sync.py" \
  --target "$AI_DOCS_PROJECT" --apply \
  --plan-file "$AI_DOCS_PLAN_DIR/sync.json"
```

### 校验文档

```bash
# 类型、结构、ID 与本地引用检查
python3 "$AI_DOCS_SKILLS/ai-docs-check/scripts/check.py" --root "$AI_DOCS_PROJECT" check

# 进一步检查项目配置和核验就绪情况
python3 "$AI_DOCS_SKILLS/ai-docs-check/scripts/check.py" --root "$AI_DOCS_PROJECT" check --strict
```

### 共享资源定位

四个 Skill 的实际目录应保持相邻，`ai-docs-check` 需包含完整资源：

```text
<skills-directory>/
├── ai-docs-init/
├── ai-docs-sync/
├── ai-docs-migrate/
└── ai-docs-check/
    └── assets/templates/
```

默认资源来自相邻的 `ai-docs-check/assets/templates/`。不同目录布局下，初始化、同步和迁移脚本可用 `--source` 指定资源根，校验工具可用 `--resources`。资源版本必须与目标配置中的 `system.version` 匹配。

客户端入口适配示例见 [工具入口适配](skills/ai-docs-check/assets/templates/docs/_system/tool-adapters.md)。

## 日常维护与历史迁移

先检索已有对象，再补充或创建文档：

```bash
python3 "$AI_DOCS_SKILLS/ai-docs-check/scripts/check.py" --root "$AI_DOCS_PROJECT" find --type feature
python3 "$AI_DOCS_SKILLS/ai-docs-check/scripts/check.py" --root "$AI_DOCS_PROJECT" route feature
python3 "$AI_DOCS_SKILLS/ai-docs-check/scripts/check.py" --root "$AI_DOCS_PROJECT" \
  new feature FEAT-001 login --title "Login"
```

新建文档仍需补充实际内容和证据。候选文件可在写入前独立校验，无需先初始化其所在目录：

```bash
python3 "$AI_DOCS_SKILLS/ai-docs-check/scripts/check.py" check-meta /absolute/path/to/candidate.md
```

历史迁移先盘点，再确定旧路径到文档类型、ID 和 slug 的映射，预览后应用同一计划：

```bash
python3 "$AI_DOCS_SKILLS/ai-docs-migrate/scripts/migrate.py" --target "$AI_DOCS_PROJECT" --scan
```

完整映射格式、预览与应用命令、支持的 Markdown 格式见 [迁移指南](skills/ai-docs-migrate/references/migration.md)。迁移范围必须明确，脚本不自动判断业务分类。

计划文件不会覆盖已有文件；目标或来源变化后，应使用新文件名重新生成计划。同步和迁移的 `--apply` 必须读取已保存计划。

## 文档如何组织

文档协议覆盖项目、产品、设计、工程、接口、数据、测试、发布、运维、安全等知识领域，当前提供 **72 种文档类型**。类型定义见 [meta schema](skills/ai-docs-check/assets/templates/docs/_system/meta-schemas.json)，集合路由见 [collections.json](skills/ai-docs-check/assets/templates/docs/_system/collections.json)。

| 集合内容 | 实际布局 |
| --- | --- |
| 没有条目 | 不创建业务文件或目录 |
| 1–2 条 | `<base_path>.md`，每条有独立 ID、meta 和正文 |
| 第 3 条起 | `<base_path>/ID-slug.md`，展开原条目并修复引用 |
| 已展开 | 保持目录，不自动收拢 |

项目总纲、架构总览和开发指南使用独立单篇路径。文档状态包括 `draft`、`active`、`deprecated`、`archived`；未知事实保留为 `null`，格式通过不代表内容已批准或业务行为已验证。

详细设计见 [自适应文档架构](docs/architecture.md)。

## 仓库结构与开发

### 本地真实场景评测

本地评测框架与项目样本位于 [`evals/`](evals/README.md)。包含 Vite Todo、Python CLI、历史 Markdown 和空项目，共 14 条场景；Todo 新增产品文档写入、编辑功能和切换 bug 修复，使用独立业务与浏览器验收。每次在独立副本运行 Codex CLI，并对文件、元数据、事实与修改范围进行独立验收。默认使用当前 CLI 模型，项目和报告保存在本地；模型执行需要正常服务连接并消耗相应额度。

```bash
python3 evals/run.py list
python3 evals/run.py run --engine tools       # 不调用模型的脚本冒烟检查
python3 evals/run.py run --case vite-init     # 真实 Codex 场景
python3 evals/run.py run --tag vite --repeat 3
# 准备本地依赖，再运行三个 Todo 开发场景
npm ci --prefix evals/fixtures/vite-todo
python3 evals/run.py run --tag todo-development --timeout 1200
```

运行报告、事件日志、项目最终文件和差异保存在 `evals/results/`。更多命令、项目导入和验收规则见 [本地场景评测说明](evals/README.md)。

```text
.
├── README.md                    # 简体中文（默认）
├── README.en.md                 # English
├── docs/architecture.md          # 设计说明
├── evals/                       # 本地项目样本、场景评测与运行器
├── tests/                       # Skill 和协议回归测试
└── skills/
    ├── ai-docs-init/
    ├── ai-docs-sync/
    ├── ai-docs-migrate/
    └── ai-docs-check/            # 校验入口与共享资源
        └── assets/templates/    # 协议、入口、类型模板与工具的唯一源码
```

公共规则、模板和运行工具直接维护在 `skills/ai-docs-check/assets/templates/`。该目录是四个 Skill 共用的唯一源码，随 `ai-docs-check` 一同分发，无需复制或构建。Skill 和协议回归测试集中在 `tests/`，与 Skill 运行资源分开。

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p 'test_*.py'
python3 skills/ai-docs-check/scripts/check.py --root skills/ai-docs-check/assets/templates check
```

评测框架测试仍保存在 `evals/`，按 [本地场景评测说明](evals/README.md) 中的命令执行。

欢迎通过 Issue 或 Pull Request 反馈问题和改进建议。修改文档时请同步更新中英文 README；修改系统时请运行相关测试与资源结构检查。上述测试验证文档系统自身，目标项目的业务测试需另行执行。
