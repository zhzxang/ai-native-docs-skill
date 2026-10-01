# 原始 35 类文档迁移对照

下表保存逻辑归属与独立条目边界，不是待创建目录清单。集合 key 的真实基础路径以 [collections.json](collections.json) 为准：无内容不建壳，1–2 个独立条目在 `<base_path>.md`，第 3 个才展开为 `<base_path>/<ID>-<slug>.md`；已展开不自动收拢。模板集中于 `docs/_templates/`，单篇参考在 `docs/_templates/reference/`，导航按实际需要建立。

| 原文档 | 逻辑归属 / 按需单篇 | 条目边界与权威原则 |
|---|---|---|
| 项目概述 / README | 根 `README.md`；按需 `docs/project/overview.md` | 入口与项目总纲分开，保持有界摘要 |
| 产品需求文档 PRD | `feature` | 一个可以独立讨论和验收的功能；总体目标在总纲 |
| 产品路线图 Roadmap | `roadmap` | 一个独立阶段或时间窗口的目标和取舍 |
| 功能清单 / Backlog | `task` | 一个工作项；state 是唯一执行状态 |
| 用户流程文档 | `journey` | 一个有独立入口、目标和终点的跨功能流程 |
| 页面 / 信息架构 | `page` | 一个有独立职责和边界的页面 / 导航节点 |
| UI / 设计规范 | 按需设计原则；`token`、`component`、`design-asset` | 原则有界，语义 Token 组、组件和资产各自独立 |
| 技术方案 / Architecture | 按需架构总览；`module` | 总览有界，一个独立模块一个条目 |
| 技术决策记录 ADR | `adr` | 一个可以独立批准或替代的决策，不改写历史理由 |
| 数据库设计文档 | `entity`、`migration`、`data-lifecycle` | 实体、迁移和数据保存规则按各自边界记录 |
| API 文档 | `api`、`event`、`error` | 说明在 docs；真实机器契约由映射定位 |
| 环境配置文档 | `environment`、`config` | 一个环境或内聚配置组，不存密钥 |
| 开发指南 | 按需启动指南；`dev-guide` | 启动入口有界，专题指南按独立使用场景记录 |
| 测试文档 | 按需策略；`test-case`、`test-suite`、`fixture`、`test-report` | 用例、集合、数据和实际运行报告分开 |
| Bug / Known Issues | `task` | kind=bug；Known Issues 从任务筛选，不另写状态 |
| 部署文档 | `deployment` | 一个内聚部署目标或方式；权限和恢复边界明确 |
| 发布 Checklist | `release-checklist` | 一种发布风险模型的程序，执行结果在 release |
| Changelog | `release` | 一个版本或独立发布事件，不设长根 CHANGELOG |
| 运维 Runbook | `runbook` | 一种可以独立诊断和处置的故障场景 |
| 第三方服务清单 | `service` | 一个可独立接入和退出的服务，清单由检索生成 |
| 成本记录 | `cost-period` | 一个独立结算周期，区分币种、口径、实际和预算 |
| Analytics / 指标定义 | `metric`、`event` | 一个独立指标口径；埋点投递语义在 event |
| 用户反馈记录 | `feedback`、`interview` | 一条可处理反馈或一次访谈，来源、时间和脱敏边界可追溯 |
| 竞品 / 市场研究 | `competitor`、`study` | 一个对象的采集快照或独立研究问题 |
| 定价文档 | `pricing` | 一个范围和生效区间明确的定价版本 |
| 商业模式说明 | 按需商业模型；`assumption` | 当前模型有界，每个可独立验证的假设一个条目 |
| 营销文档 | 按需定位；`campaign`、`copy`、`seo` | 活动、内聚文案和搜索意图分别记录 |
| 内容计划 | `content` | 一篇内容或可独立发布的条目 |
| 客服 FAQ | `faq` | 一个可独立回答的问题，引用有效产品规则 |
| 隐私政策 | `privacy` | 一个适用范围和生效区间明确的政策版本 |
| 服务条款 | `terms` | 一个适用范围和生效区间明确的条款版本 |
| 退款 / 取消订阅规则 | `refund-policy` | 一个规则版本，操作权限另外验证 |
| 安全文档 | 按需基线；`threat-model`、`security-control`、`security-finding` | 资产边界、控制和可复现发现各自独立 |
| 项目日志 / Dev Log | `worklog` | 一个需持久化的会话或工作窗口，不强制归档所有聊天 |
| 复盘文档 | `review` | 一次版本、事故、实验或周期的独立复盘 |
