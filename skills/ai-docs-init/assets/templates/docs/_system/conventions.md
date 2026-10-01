# 命名、元数据与状态规则

## 文件与 ID
目录采用英文小写短名，正文使用中文。ID 全库唯一，重命名、聚合和展开不换 ID。展开后的文件采用稳定 ID 加短语，如 `FEAT-001-subscription.md`；`slug` 使用英文小写和连字符。日期必须是实际事件日期，不用生成日期冒充。

持续增长的内容按 [collections.json](collections.json) 的逻辑集合归属：无内容不创建业务壳，1–2 个独立条目存于 `<base_path>.md`，第 3 个条目展开为 `<base_path>/<ID>-<slug>.md`。已展开不自动收拢；标题、段落、字段、验收条件和修改次数不计数。业务父目录按需创建，不受集合阈值限制。详细规则见 [writing-policy.md](writing-policy.md)。

集合 README 非默认必建；确有导航需要时只保留职责、查找方式和稳定入口，不增加第二份正文。集中模板 `docs/_templates/<key>.md` 不可当实例，未使用模板保留在参考源，不为分类齐全而制造空业务目录。

## 元数据
独立条目文件使用 YAML front matter；紧凑文件内每个条目使用 `yaml doc-meta` 代码块。两种形式字段相同，均为受限子集：顶层 `key: JSON标量`，字符串双引号，未知值为 `null`。不使用嵌套、折叠文本、多行值、数组或 YAML 标签。这样内置工具可以只依赖 Python 标准库；这属于本项目约定，不是 AGENTS.md 或 Agent Skills 的统一要求。

```yaml
---
id: "FEAT-001"
slug: "subscription"
type: "feature"
status: "draft"
summary: "用一句话说明内容、适用任务和边界。"
owner: null
applies_to: "待确认的目标版本或环境"
verified_at: null
verification_ref: null
authority: "normative"
approved_by: null
approval_ref: null
---
```

`owner` 是对内容负责的主体，不是最后一次编辑的 AI。`verified_at` 记录核验时间，必须搭配可定位的 `verification_ref`，如提交、CI run、发布编号或受控证据引用。编辑日期由 Git 提供，不与核验日期混用。

每个紧凑条目依次写 `<a id="feat-001"></a>`、`## FEAT-001 · 标题`、完整 `yaml doc-meta` 块与 `###` 内容章节；锚点使用 ID 的小写形式，代码块内 `id` 必须与标题和锚点一致。`slug` 是英文小写连字符短名，供展开形成 `<ID>-<slug>.md`；创建后不要为了标题变化随意改路径。单文件中的多个条目各自维护完整元数据，不使用公共 front matter 代替各条字段。展开时将同一元数据转换为 front matter，保留显式 ID 锚点和原事实。实例格式见写入协议。

## 文档状态
| status | 意义 | 是否可当有效规则 |
|---|---|---|
| template | 仅供复制的结构 | 否 |
| draft | 待补充或待批准的草案 | 否 |
| active | 在声明的范围内有效 | 需结合 authority、适用版本和批准依据 |
| deprecated | 已有替代或即将退出 | 只用于仍适用的旧版本或迁移判断 |
| archived | 历史资料 | 不作为当前目标规则 |

规范的 `active` 不表示功能已实现；测试用例有效不表示测试执行通过；部署程序有效不表示已部署。

## 信息角色
`normative` 定义应该怎样；`descriptive` 描述实际事实；`evidence` 保存来源与观察；`procedure` 描述操作步骤。导航和生成索引不增加源文档的权威性。启用 normative/procedure 记录需填写批准者与批准依据，权限允许时可引用明确的预授权规则。

## 专属状态
任务以 `state` 表示 `queued / ready / doing / blocked / done / deferred / cancelled`；任务类别使用 `kind: feature / bug / chore / docs / research`。`task` 条目元数据是状态唯一来源，既可能位于紧凑文件，也可能位于展开文件；计划、日志和生成视图只引用它，不复制另一套状态表。

发布以 `release_state` 表示 `planned / built / deployed / verified / rolled_back`。文档状态、任务状态和发布状态不得混用。

## 内容约定
每条记录满足该类型 `minimum_content`，保留范围、可核验依据及影响正确性、授权或验收的未知项。模板中的 `{{...}}` 是待填写位置，不能机械替换成自信的结论。确实不适用的可选章节可以省略，必要时说明原因；缺资料时保留未知并说明阻塞影响，不复制无内容的大量空章节。

## 关系与适用范围
在正文使用相对 Markdown 链接，并写明关联 ID。代码路径只通过映射定位。规范允许按产品、环境、法域或版本共存，必须避免有效区间重叠造成无法判定的冲突。被替代的文档使用 `superseded_by` 字符串记录替代 ID，并在正文提供实际链接。

`handover_ref` 是仓库相对定位，指向唯一计划条目。紧凑布局使用 `docs/work/plans.md#plan-001`，展开后使用 `docs/work/plans/PLAN-001-slug.md#plan-001`；不能用含多个计划的聚合文件路径代替具体条目定位。首次展开时同步修复这个字段。
