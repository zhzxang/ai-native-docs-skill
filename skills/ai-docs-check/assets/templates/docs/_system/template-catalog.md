# 逻辑集合与集中条目参考

60 类集合是分类词典，不是初始化清单。先读取[写入协议](writing-policy.md)，查找已有同主题条目；没有真实内容就不实例化。参考源按需读取，不复制整套占位与空章节。

每类前 1–2 条位于 `<base_path>.md`，每条有独立 ID、元数据与锚点；第 3 条首次展开为 `<base_path>/<ID>-<slug>.md`，已展开后不自动收拢。标题、段落、验收条件和编辑次数不计条目。

| 类型键 | 最小条目参考 | 独立计数单位 | 最低内容 |
|---|---|---|---|
| `term` | [业务术语](../_templates/term.md) | 一个有独立定义与使用边界的业务术语 | 定义与边界、对应表示、依据与变更 |
| `roadmap` | [阶段路线图](../_templates/roadmap.md) | 一个阶段或时间窗口的目标与取舍 | 阶段与范围、退出条件、依据与决策 |
| `feature` | [功能需求 / PRD](../_templates/feature.md) | 一个可以独立讨论和验收的功能 | 范围与规则、验收、依据与关联 |
| `journey` | [用户流程](../_templates/journey.md) | 一条具有独立入口、目标和终点的用户流程 | 场景与边界、流程与恢复、验证与依据 |
| `page` | [页面与信息架构](../_templates/page.md) | 一个有独立职责和交互边界的页面 | 职责与内容、状态与交互、验证与依据 |
| `metric` | [Analytics / 指标定义](../_templates/metric.md) | 一个有独立计算口径的业务指标 | 含义与口径、来源与计算、核验与限制 |
| `experiment` | [产品实验](../_templates/experiment.md) | 一次有独立假设和判定条件的实验 | 假设与设计、指标与授权、结果与结论 |
| `token` | [设计 Tokens](../_templates/token.md) | 一组具有共同语义和来源的设计 Tokens | 范围与语义、来源与消费、变更与验证 |
| `component` | [组件规范](../_templates/component.md) | 一个有独立职责和交互契约的组件 | 职责与契约、状态与交互、来源与验证 |
| `design-asset` | [设计资产登记](../_templates/design-asset.md) | 一个能够独立定位和核验的设计资产 | 资产与范围、来源与定位、核验与限制 |
| `module` | [模块设计](../_templates/module.md) | 一个具有独立职责和边界的模块 | 职责与定位、契约与约束、证据与变更 |
| `adr` | [技术决策记录 ADR](../_templates/adr.md) | 一个可以独立批准或替代的技术决策 | 背景与方案、决策与理由、后果与核验 |
| `dev-guide` | [开发专题指南](../_templates/dev-guide.md) | 一个有独立使用场景的开发专题指南 | 适用条件与权限、步骤、验证与失败处理 |
| `dependency` | [关键技术依赖](../_templates/dependency.md) | 一个能够独立升级或退出的关键技术依赖 | 用途与版本、接入与风险、核验与退出 |
| `api` | [API 契约说明](../_templates/api.md) | 一个操作或不能合理拆开的内聚接口组 | 操作与契约、权限与失败、验证与依据 |
| `event` | [事件 / Webhook 契约](../_templates/event.md) | 一个有独立语义和投递契约的事件 | 含义与参与者、数据与投递、演进与验证 |
| `error` | [错误语义](../_templates/error.md) | 一个有独立业务含义和恢复规则的错误 | 定义与范围、恢复与表达、验证与依据 |
| `entity` | [实体 / 表设计](../_templates/entity.md) | 一个有独立业务语义和约束的数据实体 | 语义与结构来源、字段与约束、验证与影响 |
| `migration` | [数据迁移方案](../_templates/migration.md) | 一次有独立目标和恢复边界的数据迁移 | 范围与授权、执行与恢复、验证与证据 |
| `data-lifecycle` | [数据生命周期](../_templates/data-lifecycle.md) | 一类具有独立保存与删除规则的数据 | 数据与用途、保存与流转、验证与批准 |
| `test-case` | [测试用例](../_templates/test-case.md) | 一个有独立前提和断言的测试场景 | 要求与前提、步骤与断言、执行关联 |
| `test-suite` | [测试 / 回归集合](../_templates/test-suite.md) | 一组有共同触发和通过条件的回归用例 | 触发与覆盖、执行与边界、通过与报告 |
| `fixture` | [测试数据说明](../_templates/fixture.md) | 一组有共同语义和生命周期的测试数据 | 用途与来源、生成与隔离、验证与限制 |
| `test-report` | [测试执行报告](../_templates/test-report.md) | 一次可以独立核验的实际测试运行 | 对象与环境、实际结果与证据、未验证与结论 |
| `environment` | [环境配置](../_templates/environment.md) | 一个可以独立配置和核验的环境 | 职责与定位、配置与隔离、核验与差异 |
| `config` | [配置项 / 配置组](../_templates/config.md) | 一组具有共同职责和修改边界的配置 | 职责与来源、语义与环境、修改与验证 |
| `service` | [第三方服务](../_templates/service.md) | 一个可以独立接入和退出的外部服务 | 职责与定位、接入与约束、核验与退出 |
| `deployment` | [部署程序](../_templates/deployment.md) | 一个内聚的部署目标或部署方式 | 范围与授权、发布与恢复、验证与记录 |
| `runbook` | [运维 Runbook](../_templates/runbook.md) | 一种可以独立诊断和处置的故障场景 | 触发与权限、诊断与处置、验证与失败处理 |
| `incident` | [事故记录](../_templates/incident.md) | 一次有独立影响和时间线的真实事故 | 概要与事实、处置与恢复、原因与后续 |
| `signal` | [监测与告警](../_templates/signal.md) | 一个有独立观测或告警语义的信号 | 目的与定义、阈值与响应、验证与依据 |
| `cost-period` | [成本记录](../_templates/cost-period.md) | 一个独立结算周期的成本记录 | 周期与口径、账目与汇总、差异与结论 |
| `backup-plan` | [备份与恢复方案](../_templates/backup-plan.md) | 一类需要独立恢复的数据资产或系统 | 范围与目标、恢复与权限、验证与演练 |
| `release-checklist` | [发布检查程序](../_templates/release-checklist.md) | 一种有独立风险模型的发布类型 | 使用条件与权限、检查与停止条件、记录与证据 |
| `release` | [发布记录 / Changelog](../_templates/release.md) | 一个版本或独立部署事件 | 版本与变化、执行与证据、状态与未解决项 |
| `assumption` | [商业假设](../_templates/assumption.md) | 一个能够独立验证的商业假设 | 假设与重要性、依据与验证、结果与决定 |
| `pricing` | [定价与套餐版本](../_templates/pricing.md) | 一个适用范围和生效区间明确的定价版本 | 版本与范围、定价与权益、批准与验证 |
| `campaign` | [营销活动](../_templates/campaign.md) | 一次有独立目标和预算的营销活动 | 目标与计划、预算与发布条件、执行与结果 |
| `copy` | [营销文案](../_templates/copy.md) | 一组有共同使用位置和批准边界的文案 | 位置与正文、承诺与依据、审查与发布 |
| `seo` | [SEO 主题与策略](../_templates/seo.md) | 一个有独立搜索意图和页面映射的主题 | 意图与映射、要求与指标、核验与依据 |
| `content` | [内容计划 / 发布条目](../_templates/content.md) | 一篇内容或可独立发布的条目 | 选题与正文、事实与发布条件、实际发布与结果 |
| `faq` | [客服 FAQ](../_templates/faq.md) | 一个能够独立回答的用户问题 | 问题与回答、依据与处理、核验与未知 |
| `support-case` | [客服处理记录](../_templates/support-case.md) | 一次独立工单或内聚的客服问题 | 来源与问题、诊断与动作、证据与后续 |
| `privacy` | [隐私政策版本](../_templates/privacy.md) | 一个范围和生效区间明确的隐私政策版本 | 版本与适用范围、数据处理规则、核验与发布 |
| `terms` | [服务条款版本](../_templates/terms.md) | 一个范围和生效区间明确的服务条款版本 | 主体与范围、服务与权利义务、审核与发布 |
| `refund-policy` | [退款 / 取消订阅规则](../_templates/refund-policy.md) | 一个范围和生效版本明确的退款或取消规则 | 范围与版本、取消与退款规则、核验与授权 |
| `threat-model` | [威胁模型](../_templates/threat-model.md) | 一个有独立资产和信任边界的威胁模型 | 范围与边界、威胁与处置、验证与限制 |
| `security-control` | [安全控制](../_templates/security-control.md) | 一个有独立安全目标和核验条件的控制 | 目标与范围、要求与实施、批准与验证 |
| `security-finding` | [安全发现](../_templates/security-finding.md) | 一个能够独立复现和处理的安全发现 | 发现与范围、证据与风险、处置与核验 |
| `feedback` | [用户反馈](../_templates/feedback.md) | 一条可以独立处理的用户反馈 | 来源与时间、原始观察、结论与关联 |
| `interview` | [用户访谈](../_templates/interview.md) | 一次能够独立定位和核验的访谈 | 目的与样本、观察与证据、结论与局限 |
| `competitor` | [竞品快照](../_templates/competitor.md) | 一个竞品在一次采集窗口的快照 | 采集边界、事实与分析、意义与局限 |
| `study` | [市场 / 专题研究](../_templates/study.md) | 一个独立研究问题及其采集版本 | 问题与方法、发现与分析、结论与后续 |
| `task` | [Backlog / Bug / 工作项](../_templates/task.md) | 一个有独立目标和验收的功能、Bug、技术债或研究工作项 | 目标与范围、验收与证据、唯一状态与交接 |
| `plan` | [复杂任务执行计划](../_templates/plan.md) | 一个需要跨步骤交接的复杂任务执行计划 | 任务与边界、方案与验证、唯一交接 |
| `worklog` | [项目日志 / Dev Log](../_templates/worklog.md) | 一次会话、一天或明确工作窗口的实际日志 | 范围与事实、发现与验证、交接与关联 |
| `review` | [复盘](../_templates/review.md) | 一次有独立对象和改进目标的复盘 | 对象与结果、原因与局限、行动与回写 |
| `approval` | [授权 / 批准记录](../_templates/approval.md) | 一次批准或有明确范围和期限的预授权 | 批准来源、范围与期限、前提与执行关联 |
| `workflow` | [可复用执行流程](../_templates/workflow.md) | 一个有独立触发和输出的可复用流程 | 触发与前提、步骤、输出与交接 |
| `archive-record` | [归档迁移记录](../_templates/archive-record.md) | 一次内聚的归档迁移 | 原因与范围、位置与权限、验证与证据 |

singleton、客户端适配和未安装 Skill 位于[集中参考包](../_templates/README.md)。它们是按需采用的源材料，不是有效项目知识或执行授权。分类规则和实际集合路径只在注册表维护。
