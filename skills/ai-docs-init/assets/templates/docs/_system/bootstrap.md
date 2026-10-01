# 初始化与迁移指南

## 先理解交付物
这是一套技术栈无关的分类规则和集中模板源，不包含你的业务事实，也不假设源码、测试、迁移或部署脚本位于某个目录。完整分类是内容归属词典，不是要实例化的目录清单；先读 [writing-policy.md](writing-policy.md) 与 [collections.json](collections.json)。根目录保留人和 AI 的入口，项目说明按需放在 `docs/`。

## 第一步：选择安装方式
新老项目都可使用来源仓库的 `skills/ai-docs-init/SKILL.md`。Skill 携带模板与安装脚本，复制整个 Skill 后也可独立使用；先盘点，再生成计划，最后应用已审阅的计划：

```bash
python3 /Skill目录/scripts/bootstrap.py --target /目标仓库 --scan
python3 /Skill目录/scripts/bootstrap.py --target /目标仓库 --mode auto --summary --plan-file /tmp/ai-docs-plan.json
python3 /Skill目录/scripts/bootstrap.py --target /目标仓库 --apply --summary --plan-file /tmp/ai-docs-plan.json
```

`auto` 选择 `init`（新项目）、`adopt`（已有项目接入）或 `upgrade`（有安装清单的项目升级）。README 和 AGENTS 通过托管区块合并，原文保留；项目配置、业务文档和同名非托管资产保留。只有安装清单记录且未被本地修改的系统资产或区块可自动升级，其他冲突列入报告。旧 schema 不兼容时阻断安装，先完成配置迁移，不混装工具和注册表。

`--summary` 返回计数、更新路径和完整冲突，完整内容仍保存在计划文件。先核对摘要，再按需审阅计划和原文件；省略该选项可输出全部变更列表。

`docs/_system/package.json` 标识来源系统版本；目标的 `installation.json` 保存托管范围与基线哈希。相同版本重复执行跳过无变化项，保存计划应用前会检查目标是否变化。清单存在不能单独证明安装成功，仍须检查冲突与实际结构。安装不会自动迁移历史正文，也不会运行登记的项目命令。

也可以从参考包直接使用增量接口：

```bash
python3 templates/docs/_tools/init_docs.py --target /目标仓库 --mode auto
python3 templates/docs/_tools/init_docs.py --target /目标仓库 --mode auto --apply
```

不带 `--mode` 的旧接口保留严格最小部署行为：

```bash
python3 templates/docs/_tools/init_docs.py --target /目标仓库 --dry-run
python3 templates/docs/_tools/init_docs.py --target /目标仓库
```

如果参考包不在默认位置，用 `--source /参考包目录` 指定源目录。默认仅复制根 `AGENTS.md`、根 `README.md`、`docs/AGENTS.md`、`docs/README.md`、`docs/_system/` 的维护规则配置、`docs/_tools/` 和 `docs/_templates/`，不复制业务树、派生索引或参考包交付附件。源中的 `_AGENTS.md` / `_README.md` 由工具在部署时重命名。目标没有业务记录和项目总纲是预期结果，不是缺失待填的空壳。

旧接口在目标存在任一同名文件时拒绝覆盖。已有项目使用增量接入，逐项检查合并后的 README、AGENTS.md 与原有约定是否兼容；托管标记不能解决语义冲突。保留原有事实与约束，核验根执行入口及权限提案。

## 第二步：建立定位能力
填写 `project-map.json`：仓库入口、前后端、机器契约、数据库 Schema、迁移、测试、环境配置、观测、发布来源和外部设计来源。不适用的位置标记 disabled 并说明原因。可以映射多个仓库，不要求移动代码。

填写 `commands.json`：真实可执行程序与参数、工作目录、环境、副作用、验证时间和证据。工具不会执行这些命令；不要从文件名猜测它们的安全性。

## 第三步：初始化当前事实
有已确认的项目名称和概况时，可以在部署命令增加 `--overview-title "项目名称" --overview-summary "已确认的项目概况"` 创建最小 draft 总纲；工具不会由此把草稿改为 active。也可以部署后按需创建 `docs/project/overview.md`。

只创建当前任务需要且已有信息的项目总纲、架构总览、启动指南、测试策略、安全基线或权限边界；对应单篇参考在 `docs/_templates/reference/`，不用一次性补齐。保留关键未知；适用范围、依据和批准条件满足后才改为 active，模板安装不代表批准、部署或核验。

## 第四步：迁移原文档
依据 `original-document-map.md` 选择逻辑类别。先查已有同主题条目，解决重复事实和冲突，再分配稳定 ID。需求按独立功能、Backlog/Bug 按任务、发布按版本或事件、成本按结算周期、日志按必要工作窗口、反馈按独立可处理观察形成条目，而不是立即各建文件。

各集合的第 1–2 条存于 `<base_path>.md`，第 3 条迁移为 `<base_path>/`，已展开不自动收拢。迁移在同一可审查变更内保留身份、状态、范围和证据，修复旧路径入链、搬迁后的相对出链与锚点；必要时仅保留明确的薄跳转，不留第二份正文。

## 第五步：形成一个闭环
选一个已批准的小任务，创建任务条目，关联规范、代码映射和测试；让一个没有历史聊天的新 AI 按入口完成定位与验证。其结果用于修补文档缺口，不靠一次性补齐所有模板。

## 工具操作
以下命令在仓库根目录执行，需要 Python 3.10 或更高版本，不安装第三方依赖。

```bash
python3 docs/_tools/docctl.py check
python3 docs/_tools/docctl.py find --type feature --query "订阅" --limit 20
python3 docs/_tools/docctl.py new feature FEAT-001 subscription --title "订阅功能"
python3 docs/_tools/docctl.py new task TASK-001 implement-subscription --title "实现订阅功能"
python3 docs/_tools/docctl.py index
python3 docs/_tools/docctl.py find --type task --state ready --limit 20
python3 docs/_tools/docctl.py route billing
```

`find` 用于写入前查找；确认新对象后才使用 `new`，随后按类型最低内容完成草稿并删除不适用空章节。`new` 根据逻辑类别和实际条目数选择布局，必要时执行第三条迁移；工具不批准内容，也不核验业务事实。`index` 仅在需要分页检索时生成派生索引，不是每次创建集合的强制动作。

`check` 检查声明、元数据、引用和按需结构；`check --strict` 额外检查核心文档、必需路径和命令是否达到已声明的就绪条件。未配置的新部署在 strict 模式下应失败，不能把它误报成项目已可自治。

交付分别报告系统安装、项目配置和严格就绪。部分兼容资产已写入但仍有冲突时，报告部分应用；保留旧格式未检查或未迁移的范围，不宣称历史维护完整完成。

## 不要做的事情
不要把所有模板改成 active；不要自动填写核验日期；不要一次性导入全部文档到 Agent 上下文；不要为了适配本套件移动实际代码；不要把未配置的测试写为通过。不要预建空业务文件、空集合目录或三份同义导航，不按标题数、修改次数或文档长度触发展开。
