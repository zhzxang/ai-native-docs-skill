# 项目配置：docs/.ai-docs.json

项目只维护这一份 JSON 配置，不拆成位置、命令、分类与安装清单等多个文件。它是项目约定，不会被所有 Agent 客户端自动识别；根入口要求执行者显式查阅。通用协议、工具、分类默认值和模板从匹配版本的 Skill 读取，工具不执行登记命令。

## 字段与维护边界

| 字段 | 职责 |
|---|---|
| schema_version | 本配置文件的格式版本，当前为 1 |
| system | Skill 资源包名称与固定版本，不存某台机器绝对路径 |
| project | 真实项目名称、责任主体及 bootstrap / maintenance 状态 |
| work_tracking | 本地任务状态来源或外部工作项定位 |
| locations | 按已知内容登记代码、契约、数据、测试及外部来源 |
| commands | 按已知内容登记真实运行与验证命令 |
| readiness | 可选的项目就绪约定；省略时使用 Skill 的默认要求 |
| overrides | 可选的分类和路由定制；省略时使用 Skill 默认值 |
| installation | 工具管理的安装状态与四个入口托管区块基线 |

新项目的 locations 和 commands 是空数组，不复制所有空登记项。只在实际发现或确认内容后添加对应记录；必需内容尚未登记时，严格检查保留缺口。未知不以猜测填充。

项目身份、位置、命令和覆盖由项目维护；installation 由安装器维护，两者在一个文件中以字段区分。升级保留项目字段与未知扩展字段，不把用户编辑误当作整个系统文件的冲突。不要人工伪造安装基线来覆盖本地入口修改。

当前无需拆分。未来只有真实出现独立维护责任或难以审阅的配置规模时，才经明确格式迁移考虑拆分；初始化不预建分文件或空目录。

## project、work_tracking 与 locations

`project.name` 和 `project.owner` 填实际项目与责任主体；`operating_mode` 初始为 `bootstrap`。核心事实、命令、权限及交接演练经确认后才改为 `maintenance`；这个标记不增加任何访问权限。

`work_tracking.mode` 默认 `repository`，状态由 `task` 条目元数据拥有；当前可能位于 `docs/work/items.md` 或已展开的 `docs/work/items/`，使用定位工具解析。改为 `external` 时记录真实系统定位，并停止维护第二套本地状态。内置 new 会拒绝在外部模式下创建本地任务，但工具不负责外部同步。

每条 `locations` 的字段：

| 字段 | 含义 |
|---|---|
| id | 稳定定位标识，供文档引用 |
| kind / description | 内容类别与职责 |
| enabled | null 表示尚未确认；true 表示使用；false 表示明确不适用 |
| repository | `.` 表示当前仓库；跨仓库来源必须附明确可访问的 external_ref |
| paths | 当前仓库中的精确相对路径，不使用猜测路径或 glob |
| external_ref | 受控外部来源定位，不含凭据 |
| verified_at / verification_ref | 实际核验时间及提交、记录或受控证据 |
| not_applicable_reason | enabled=false 时说明原因 |

无需具备每一种技术组件。项目没有后端、数据库或 E2E 时，说明不适用或当前缺口；不要为填满模板编造代码位置。

`readiness` 声明核心文档、必需位置和最低验证命令。可以根据项目性质确认调整，但不能为了绕过失败擅自降低门禁。

## commands

每条命令用稳定 ID 关联说明，具体可执行项只在这里登记，不到处复制命令文本。

| 字段 | 含义 |
|---|---|
| argv | 可执行程序与每个参数组成的数组；未知为 null，不保存密钥 |
| cwd | 当前仓库的相对工作目录，例如 `.`；不推断默认值 |
| environment | 明确的目标环境或环境条目 ID |
| side_effect | 可能的本地、sandbox 或外部写入，用于风险判断 |
| timeout_seconds | 经确认的单次时间限制 |
| verified_at / verification_ref | 实际执行核验的时间与证据 |
| authorization_ref | 涉及相应动作时的有效授权引用 |
| cleanup_ref | 临时资源清理或恢复入口 |

不假定 shell 展开、通配符、管道或环境变量插值。需要 shell 时应明确登记程序与参数，并核验其行为。argv 看起来存在不代表运行安全，也不代表已获授权。

最小 `verify` 应能检查实际项目的关键完成条件，不能仅因文档工具 check 通过就把项目业务验证标为完成。

## 默认资源与 overrides

默认 routes.json 和 collections.json 保存在 Skill 资源根的 `docs/_system/`，项目不复制。项目确需定制时，在 `overrides.collections` 或 `overrides.routes` 保存对应完整 JSON 配置；未定制部分仍读取 Skill 默认值，不能维护第二份本地计数或状态。

`collections.json` 采用 schema_version 2。`defaults` 声明 `compact_max_items: 2`、禁止空业务文件和空集合目录、`auto_collapse: false`；`page_size` 默认 40。各集合登记以下内容，不手工保存 `item_count`：

| 字段 | 含义 |
|---|---|
| key | 稳定逻辑类别，如 feature、task、feedback |
| base_path | 仓库相对基础路径，不含 `.md`；未展开使用 `<base_path>.md`，展开使用 `<base_path>/<ID>-<slug>.md` |
| prefix | ID 前缀；全库检查 ID 唯一性 |
| unit | 一个可独立命名、检索、维护对象的语义边界，不按标题和编辑次数计数 |
| minimum_content | 该类型的最低充分内容，不能用空占位符代替事实 |
| template | Skill 资源根中的 `docs/_templates/<key>.md`，不是目标项目路径或业务实例 |
| title / summary / authority | 分类职责、检索摘要与信息角色 |

routes 中的 `must_read`、`read_when` 和 `write_back` 使用 `{"collection":"feature"}` 引用目标集合，由工具解析现有紧凑文件或展开目录；尚无内容时显示按需位置，不为路由预建空壳。按需单篇文档使用 `optional_path`。`docs/_system/` 的固定规则引用由工具解析到匹配 Skill 资源，旧位置和命令配置引用解析到本项目的 `docs/.ai-docs.json`，不要求目标拥有系统目录。先定位具体相关条目，不读取整个集合。条件资料在任务满足条件时仍需核验，缺失时记录缺口。

物理路径转换不改变类别、最低内容、状态语义或授权要求。修改配置须同步适配工具、路由和示例，不能只用新 JSON 覆盖旧工具并期待兼容；该 schema 是本项目格式，不是客户端自动发现规范。

新增规则或类型后运行 check，再根据真实变更重建索引。人工导航、机器路由和源记录发生矛盾时先修正唯一可编辑来源。
