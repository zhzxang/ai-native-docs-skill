# 定位与命令配置说明

这些 JSON 文件是本项目约定，不会被所有 Agent 客户端自动识别。根入口要求执行者显式查阅；内置工具只做结构检查和路由展示，不执行登记命令。

## project-map.json

`project.name` 和 `project.owner` 填实际项目与责任主体；`operating_mode` 初始为 `bootstrap`。核心事实、命令、权限及交接演练经确认后才改为 `maintenance`；这个标记不增加任何访问权限。

`work_tracking.mode` 默认 `repository`，状态由 `docs/work/items/` 拥有。改为 `external` 时记录真实系统定位，并停止维护第二套本地状态。内置 new 会拒绝在外部模式下创建本地任务，但工具不负责外部同步。

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

## commands.json

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

## routes.json 与 collections.json

routes 中的 must_read、read_when 和 write_back 指向稳定入口。先定位具体相关条目，不读取一个集合下所有文件。collections 登记模板目录、类型键与前缀；page_size 默认 40，生成目录按类型分页。

新增规则或类型后运行 check，再根据真实变更重建索引。人工导航、机器路由和源记录发生矛盾时先修正唯一可编辑来源。
