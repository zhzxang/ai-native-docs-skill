# 文档工具

需要 Python 3.10 或更高版本，仅使用标准库，无第三方依赖。工具不联网、不执行项目命令、不连接工单系统、不批准规范，不改变生产权限。

## 命令
在仓库根目录运行：

```bash
# 模板结构检查，未初始化的草稿可以保留。
python3 docs/_tools/docctl.py check

# 就绪检查；新模板应失败，直到核心配置与文档确实完成。
python3 docs/_tools/docctl.py check --strict

# 创建草稿，ID 全局唯一且禁止覆盖。
python3 docs/_tools/docctl.py new feature FEAT-001 subscription --title "订阅功能"
python3 docs/_tools/docctl.py new task TASK-001 subscription-bug --title "调查订阅问题" --kind bug

# 查看任务或规范；默认不包含模板、生成物和归档。
python3 docs/_tools/docctl.py find --type task --kind bug --state queued --limit 20
python3 docs/_tools/docctl.py find --type feature --status active --query "订阅"

# 展示任务路由，不会自动读取所有文件或执行操作。
python3 docs/_tools/docctl.py route billing

# 重建分页的人可读 / 机器目录，每页最多 40 条。
python3 docs/_tools/docctl.py index

# 运行工具自身测试；不是项目业务测试。
python3 -m unittest discover -s docs/_tools -p 'test_*.py' -v
```

也可在脚本路径后、子命令前用 `--root /实际仓库路径` 指定根目录。CLI 输出使用 JSON，方便人和 Agent 读取；失败返回非零退出码。

工具会在本地扫描源文件并提取元数据、标题和内容校验值；不会把全库正文输出给 Agent 上下文。规模扩大后可改为增量索引，但不应把扫描过程与模型上下文加载混为一谈。

## 新建记录
类型、模板、目录和 ID 前缀由 `docs/_system/collections.json` 登记。`new` 只把模板的 ID、标题和文档状态初始化；其他占位符仍需填写。不会自行填 owner、核验时间、批准者或通过结果。

并发创建禁止覆盖同一路径，合并分支时仍需校验全库 ID 唯一性。`new` 不负责分配全局分布式序号，不把文件锁当作任务认领系统。

## 检查范围
结构检查涵盖普通相对 Markdown 文件链接、文档 ID、受限元数据、任务状态、发布状态、批准字段、路由和配置引用。active 文档不能残留占位符；核验时间和证据必须成对。

strict 模式额外检查项目声明的核心文档、真实位置和最小验证命令是否填写，以及必需文档是否 active。它只检查声明的一致性，不会访问外部系统或证明核验记录属实。

本工具不是通用 YAML / Markdown 解析器，不检查所有锚点、引用式链接、外链、法律适用性、业务正确性、密钥泄漏或真实权限。所用元数据子集见 conventions。需要这些能力时再按实际技术栈增加专门检查。

## 索引与状态
索引从源文件元数据生成，保持按类型分页；不扫描模板和生成物作为实例。空集合不生成空页面。生成器只重建 `_generated/indexes/` 与 `_generated/catalog/`，这些目录不要放手写资料。

源文件和索引使用内容校验值关联，但哈希只用于发现变化，不证明内容准确。生成器在源记录变化时需要重新运行；它不会自动批准草案或改变任务状态。

## 外部任务系统
切换到外部 Issue 系统时，将项目映射中的 work_tracking 改为外部来源，并停止把本地任务当作另一套状态源。本工具未实现外部同步；需要单独接入具备授权和冲突规则的连接器。
