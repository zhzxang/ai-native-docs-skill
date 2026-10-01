# 命名、元数据与状态规则

## 文件与 ID
目录采用英文小写短名，文件采用稳定 ID 加短语，如 `FEAT-001-subscription.md`。正文使用中文。ID 全库唯一，重命名不换 ID。日期记录可按年份分目录；日期必须是实际事件日期，不用生成日期冒充。

所有持续增长的内容都进入集合目录；集合的 README 只保留职责、查找方式和稳定入口。`_template.md` 不可当实例使用。没有对应业务时，保留或删除未使用模板均可，不必制造虚假条目。

## 元数据
本套件使用 YAML front matter 的受限子集：顶层 `key: JSON标量`，字符串双引号，未知值为 `null`。不使用嵌套、折叠文本、多行值、数组或 YAML 标签。这样内置工具可以只依赖 Python 标准库；这属于本项目约定，不是 AGENTS.md 或 Agent Skills 的统一要求。

```yaml
---
id: "FEAT-001"
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
任务以 `state` 表示 `queued / ready / doing / blocked / done / deferred / cancelled`；任务类别使用 `kind: feature / bug / chore / docs / research`。任务文件是状态唯一来源，计划、日志和生成视图只引用它。

发布以 `release_state` 表示 `planned / built / deployed / verified / rolled_back`。文档状态、任务状态和发布状态不得混用。

## 内容约定
每份记录都需要范围、可核验依据与未知项。模板中的 `{{...}}` 是待填写位置，不能机械替换成自信的结论。确实不适用的部分写出原因；缺资料时保留未知并说明阻塞影响。

## 关系与适用范围
在正文使用相对 Markdown 链接，并写明关联 ID。代码路径只通过映射定位。规范允许按产品、环境、法域或版本共存，必须避免有效区间重叠造成无法判定的冲突。被替代的文档使用 `superseded_by` 字符串记录替代 ID，并在正文提供实际链接。
