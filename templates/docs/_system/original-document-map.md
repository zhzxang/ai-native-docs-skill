# 原始 35 类文档迁移对照

除根 README 外，以下路径相对 `docs/`。所有集合均提供 README 与完整条目模板。

| 原文档 | 新位置 | 拆分与权威原则 |
|---|---|---|
| 项目概述 / README | `README.md；project/overview.md` | 入口与项目总纲分开，保持有界摘要 |
| 产品需求文档 PRD | `product/features/` | 一个功能一份；总体目标在 project/overview.md |
| 产品路线图 Roadmap | `product/roadmap/` | 一个阶段或时间窗口一份 |
| 功能清单 / Backlog | `work/items/` | 一个任务一份，state 是唯一状态 |
| 用户流程文档 | `product/journeys/` | 一个跨功能流程一份 |
| 页面 / 信息架构 | `product/pages/` | 一个页面/导航节点一份 |
| UI / 设计规范 | `design/` | 原则有界；Tokens、组件、资产分别成集合 |
| 技术方案 / Architecture | `engineering/architecture/` | 总览有界，模块各一份 |
| 技术决策记录 ADR | `engineering/adrs/` | 一个决策一份，不改写历史理由 |
| 数据库设计文档 | `db/` | 实体、迁移说明、生命周期分别成集合 |
| API 文档 | `contracts/api/；contracts/events/；contracts/errors/` | 说明在 docs；实际机器契约由映射定位 |
| 环境配置文档 | `operations/environments/；operations/configuration/` | 一个环境或配置组一份，不存密钥 |
| 开发指南 | `engineering/development/` | 启动入口有界，专题指南成集合 |
| 测试文档 | `tests/` | 策略有界，用例/集合/夹具/报告各自成集合 |
| Bug / Known Issues | `work/items/` | kind=bug；Known Issues 从任务筛选，不另写状态 |
| 部署文档 | `operations/deployment/` | 一种部署目标/方式一份 |
| 发布 Checklist | `releases/checklists/` | 程序按类型，执行结果在 release 条目 |
| Changelog | `releases/entries/` | 一个版本/发布事件一份，不设长根 CHANGELOG |
| 运维 Runbook | `operations/runbooks/` | 一种可独立处理的故障场景一份 |
| 第三方服务清单 | `operations/services/` | 一个服务一份，列表由检索/索引生成 |
| 成本记录 | `operations/costs/` | 一个结算周期一份，可按年份分区 |
| Analytics / 指标定义 | `product/metrics/` | 一个指标一份，埋点契约放 contracts/events/ |
| 用户反馈记录 | `research/feedback/；research/interviews/` | 每条反馈/每次访谈一份，保留来源与脱敏边界 |
| 竞品 / 市场研究 | `research/competitors/；research/studies/` | 按对象和采集窗口拆分 |
| 定价文档 | `business/pricing/` | 按适用范围和生效版本拆分 |
| 商业模式说明 | `business/model.md；business/assumptions/` | 当前模型有界，假设独立成集合 |
| 营销文档 | `marketing/` | 定位有界，活动/文案/SEO 独立成集合 |
| 内容计划 | `marketing/content/` | 一篇内容或独立发布一份 |
| 客服 FAQ | `support/faq/` | 一个问题一份，引用有效产品规则 |
| 隐私政策 | `legal/privacy/` | 一个适用范围和生效版本一份 |
| 服务条款 | `legal/terms/` | 一个适用范围和生效版本一份 |
| 退款 / 取消订阅规则 | `legal/refunds/` | 一个规则版本一份，操作权限另外验证 |
| 安全文档 | `security/` | 基线有界；威胁模型/控制/发现独立成集合 |
| 项目日志 / Dev Log | `work/logs/` | 一次会话或明确工作窗口一份 |
| 复盘文档 | `work/reviews/` | 一次版本/事故/实验/周期复盘一份 |
