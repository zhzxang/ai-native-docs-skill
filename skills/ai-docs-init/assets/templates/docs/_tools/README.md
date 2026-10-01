# 文档工具

需要 Python 3.10 或更高版本，仅使用标准库。工具不联网、不执行登记的项目命令，也不批准文档或改变生产权限。

## 初始化参考包

从这份仓库运行，先查看目标变更，再部署入口、协议、工具和集中参考源：

```bash
python3 templates/docs/_tools/init_docs.py --target /目标仓库 --dry-run
python3 templates/docs/_tools/init_docs.py --target /目标仓库
```

初始化不创建业务分类树、空集合、业务占位文档或生成索引。不带 `--mode` 的旧接口严格拒绝所有同名文件。只有显式提供 `--overview-title` 和 `--overview-summary` 时，才将所给内容保存为 `docs/project/overview.md` 草案；不补写未经核验的事实。

新项目、已有项目接入和升级可使用增量接口；省略 `--apply` 仅预览：

```bash
python3 templates/docs/_tools/init_docs.py --target /目标仓库 --mode auto
python3 templates/docs/_tools/init_docs.py --target /目标仓库 --mode auto --apply
```

`auto` 选择 `init`、`adopt` 或 `upgrade`，也可显式指定。四个 README/AGENTS 入口合并托管区块；项目配置与非托管文件保留，未改动的托管系统资产可升级，本地修改报告冲突。`installation.json` 记录版本与所有权基线，重复执行跳过无变化项。存在不兼容配置时不写入；写入持有安装锁，计划过期则拒绝，失败回滚本次变更。

来源仓库的 `skills/ai-docs-init/` 提供可携带 Skill 和 `bootstrap.py` 包装器，支持 `--scan`、`--plan-file` 保存并应用同一计划，以及安装后的结构与 strict 检查。详细流程见 [初始化与迁移指南](../_system/bootstrap.md)。安装与历史语义迁移分开执行。

## 目标项目中的命令

在目标仓库根目录执行：

```bash
# 结构检查；严格就绪检查还要求项目事实、位置和验证命令已配置。
python3 docs/_tools/docctl.py check
python3 docs/_tools/docctl.py check --strict

# 创建第一个或第二个条目时写入同一紧凑文件，第三个条目触发展开。
python3 docs/_tools/docctl.py new feature FEAT-001 subscription --title "订阅功能"
python3 docs/_tools/docctl.py new task TASK-001 subscription-bug --title "调查订阅问题" --kind bug

# 逐条检索：同一文件内的条目拥有各自元数据和锚点。
python3 docs/_tools/docctl.py find --type task --kind bug --state queued --limit 20
python3 docs/_tools/docctl.py find --type feature --query "订阅"

# 根据集合 key 解析实际文件或目录，未发生的内容只提示缺口。
python3 docs/_tools/docctl.py route billing

# 按需重建索引；每页最多 40 条，源路径带条目锚点。
python3 docs/_tools/docctl.py index
```

也可在子命令前使用 `--root /实际仓库路径`。命令输出 JSON，失败返回非零退出码。在本参考包运行检查用 `python3 templates/docs/_tools/docctl.py check`，工具支持下划线入口源；实际安装后入口使用 `README.md` 和 `AGENTS.md`。

## 新增和更新

所有写入先读取 [写入协议](../_system/writing-policy.md) 和 [集合注册表](../_system/collections.json)，再检索同主题条目。`new` 拒绝重复 ID，以及同类型同标题或同 slug 的新增；这只能发现明确重复，语义上的同一对象仍需审查。补充、纠错或修改既有对象时编辑原条目，保持 ID，不生成“补充版”“最终版”。`new` 对查重、计数、追加和迁移持有写入锁；并发冲突会拒绝本次写入，等待已有操作完成后重试。中断遗留的锁须先确认没有活动写入者，再人工移除，不自动清理。

模板源位于 `docs/_templates/<key>.md`。`new` 将 ID、标题、slug 和文档状态初始化为草案，不填写责任主体、核验日期、批准依据或成功结果。创建后填写摘要与适用范围，用实际内容替换各节写作指令，并移除“集中参考源”用途说明和不适用空章节；关键未知必须保留。1–2 条保存在 `<base_path>.md`，每条使用独立 `yaml doc-meta`；第 3 条将原条目转换为 front matter 文件，保留 ID、状态、适用范围与证据，同时修复普通 Markdown 入链、出链和定位引用。已展开集合保持目录，不自动收拢，不为每条再建一层目录，也不默认增加集合 README。

工具迁移应在同一可审查变更中完成，再运行 `check` 和必要的 `index`。不要同时保留聚合正文和目录正文。确需保留外部旧链接时，依照协议留下带 `doc-redirect` 标记的薄跳转页，不再编辑为集合正文。工具支持普通行内与引用式 Markdown 链接的迁移；HTML 链接、外部引用及其他 Markdown 方言仍需人工检查。

## 检查范围

`check` 检查紧凑条目计数、逐条元数据、ID 唯一性、逻辑归属、空集合、双正文来源、普通相对链接及本套格式中的锚点、状态、批准字段和路由配置。active 内容不能残留占位符，核验时间与证据必须成对。已展开集合只剩 1–2 条仍可通过。

`check --strict` 继续检查项目声明的核心文档、必需真实位置和最低验证命令是否就绪。初始化的参考包故意保留未知，严格检查应失败。检查不访问外部系统、不运行项目测试、不证明业务语义或授权真实性，也不能阻止直接 Shell 写入；需要正式分支门禁时，将结构检查纳入项目实际 CI 与分支保护。

## 索引与任务状态

`find` 和 `index` 从源条目提取摘要，排除集中参考源和模板；一个紧凑文件里的两个条目是两条记录。内容哈希用于发现变化，不证明正确性。索引只重建 `_generated/indexes/` 和 `_generated/catalog/`，空集合不生成页面，不手工维护状态或计数副本。

任务 `state`、文档 `status` 和发布 `release_state` 分开维护。任务默认由逻辑集合 `task` 的元数据拥有状态；切换外部工作项系统后，工具拒绝新增本地任务，不提供外部同步。

## 工具验证

从本参考包仓库运行：

```bash
python3 -m unittest discover -s templates/docs/_tools -p 'test_*.py' -v
```

这是工具自身的测试，覆盖最小安装、增量接入、幂等升级、本地修改保护、阈值展开、逐条状态、引用迁移和结构门禁，不是项目业务测试。
