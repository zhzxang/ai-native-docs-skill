

```
project/
├── README.md                           # 面向人的项目入口
├── AGENTS.md                           # 面向 AI 的薄执行入口
│
└── docs/
    ├── README.md                       # 任务路由与领域入口
    ├── AGENTS.md                       # 文档编辑规则
    │
    ├── _system/                        # 文档体系本身的规则与配置
    │   ├── README.md
    │   ├── bootstrap.md                # 初始化与迁移步骤
    │   ├── original-document-map.md    # 原始 35 类文档迁移对照
    │   ├── template-catalog.md         # 60 种条目模板目录
    │   ├── configuration-guide.md      # 映射、命令、路由的字段说明
    │   ├── conventions.md             # 命名、元数据、状态、ID
    │   ├── authority.md               # 权威来源与冲突处理
    │   ├── lifecycle.md               # 增长、分页、替代、归档
    │   ├── change-impact.md           # 变更影响检查
    │   ├── definition-of-done.md      # 完成与交付判定
    │   ├── execution-policy.md        # AI 执行授权与停止条件
    │   ├── handover-test.md           # 无历史会话交接演练
    │   ├── tool-adapters.md           # 不同 Agent 客户端的适配
    │   ├── sources.md                 # 公开规范来源
    │   ├── project-map.json           # 实际代码与外部系统位置
    │   ├── commands.json              # 实际命令、环境、副作用与证据
    │   ├── routes.json                # 按任务读取与回写的路由
    │   ├── collections.json           # 集合、模板、ID 前缀与分页配置
    │   ├── directory-tree.txt         # 本次交付的实际目录快照
    │   ├── validation-report.md       # 本次交付的验证记录
    │   └── checksums.sha256            # 文件完整性校验
    │
    ├── _tools/                         # 文档工具，不是项目业务代码
    │   ├── README.md
    │   ├── docctl.py                   # 创建、检索、检查、生成索引
    │   └── test_docctl.py              # 文档工具自身的测试
    │
    ├── _generated/                     # 可重建的派生物
    │   ├── README.md
    │   ├── indexes/
    │   │   ├── README.md
    │   │   └── <type>/page-NNN.md      # 人可读分页索引
    │   └── catalog/
    │       ├── README.md
    │       └── <type>/page-NNN.json    # 机器分页索引
    │
    ├── project/                        # 项目级知识
    │   ├── overview.md                 # 项目总纲：用户、目标、边界
    │   └── glossary/          〔集合〕 # 一个业务术语一份
    │
    ├── product/                        # 产品目标行为
    │   ├── roadmap/           〔集合〕 # 一个阶段或规划窗口一份
    │   ├── features/          〔集合〕 # 一个功能 PRD 一份
    │   ├── journeys/          〔集合〕 # 一个用户流程一份
    │   ├── pages/             〔集合〕 # 一个页面或导航节点一份
    │   ├── metrics/           〔集合〕 # 一个指标定义一份
    │   └── experiments/       〔集合〕 # 一次产品实验一份
    │
    ├── design/                         # 设计意图与资产
    │   ├── principles.md               # 有界的设计原则与来源说明
    │   ├── tokens/            〔集合〕 # 一组语义化 Tokens 一份
    │   ├── components/        〔集合〕 # 一个组件规范一份
    │   └── assets/            〔集合〕 # 一个 Figma 等设计资产一份
    │
    ├── engineering/                    # 工程知识
    │   ├── architecture/
    │   │   ├── overview.md             # 有界的系统架构总览
    │   │   └── modules/       〔集合〕 # 一个逻辑模块一份
    │   ├── adrs/              〔集合〕 # 一个重要技术决策一份
    │   ├── dependencies/      〔集合〕 # 一个关键技术依赖一份
    │   └── development/
    │       ├── quickstart.md           # 环境准备、启动与验证入口
    │       ├── conventions.md         # 项目特有开发约定
    │       └── guides/        〔集合〕 # 一个开发专题指南一份
    │
    ├── contracts/                      # 全部是契约说明，不约束代码布局
    │   ├── api/               〔集合〕 # 一个 API 操作或内聚接口组一份
    │   ├── events/            〔集合〕 # 一个事件、埋点或 Webhook 一份
    │   └── errors/            〔集合〕 # 一个错误码或错误类别一份
    │
    ├── db/                             # 全部是数据设计与迁移说明
    │   ├── overview.md                 # 数据域、来源与关系总览
    │   ├── entities/          〔集合〕 # 一个实体或表一份
    │   ├── migrations/        〔集合〕 # 一次迁移方案一份
    │   └── lifecycle/         〔集合〕 # 一类数据的生命周期一份
    │
    ├── tests/                          # 全部是测试知识与执行证据
    │   ├── strategy.md                 # 有界的测试策略
    │   ├── cases/             〔集合〕 # 一个测试用例一份
    │   ├── suites/            〔集合〕 # 一个测试或回归集合一份
    │   ├── fixtures/          〔集合〕 # 一组测试数据说明一份
    │   └── reports/           〔集合〕 # 一次实际测试运行一份
    │
    ├── operations/                     # 环境与运行维护
    │   ├── environments/      〔集合〕 # 一个运行环境一份
    │   ├── configuration/     〔集合〕 # 一个内聚配置组一份
    │   ├── services/          〔集合〕 # 一个第三方服务一份
    │   ├── deployment/        〔集合〕 # 一种部署目标或方式一份
    │   ├── runbooks/          〔集合〕 # 一种可独立处置的故障一份
    │   ├── incidents/         〔集合〕 # 一次真实事故一份
    │   ├── observability/     〔集合〕 # 一个监测信号或告警一份
    │   ├── costs/             〔集合〕 # 一个结算周期一份
    │   └── backup/            〔集合〕 # 一类资产的备份恢复方案一份
    │
    ├── releases/                       # 发布程序与实际版本历史
    │   ├── checklists/        〔集合〕 # 一种发布类型的检查程序一份
    │   └── entries/           〔集合〕 # 一个版本或发布事件一份
    │
    ├── business/                       # 商业知识
    │   ├── model.md                    # 有界的当前商业模式
    │   ├── assumptions/       〔集合〕 # 一个商业假设一份
    │   └── pricing/           〔集合〕 # 一个定价生效版本一份
    │
    ├── marketing/                      # 营销知识与内容
    │   ├── positioning.md              # 有界的定位与表达原则
    │   ├── campaigns/         〔集合〕 # 一次营销活动一份
    │   ├── copy/              〔集合〕 # 一个用途的文案一份
    │   ├── seo/               〔集合〕 # 一个搜索主题或页面群一份
    │   └── content/           〔集合〕 # 一篇内容或独立发布条目一份
    │
    ├── support/                        # 用户支持
    │   ├── faq/               〔集合〕 # 一个问题及标准回答一份
    │   └── cases/             〔集合〕 # 一个脱敏客服问题一份
    │
    ├── legal/                          # 对外政策与条款版本
    │   ├── privacy/           〔集合〕 # 一个隐私政策版本一份
    │   ├── terms/             〔集合〕 # 一个服务条款版本一份
    │   └── refunds/           〔集合〕 # 一个退款/取消规则版本一份
    │
    ├── security/                       # 安全知识
    │   ├── baseline.md                 # 有界的安全基线
    │   ├── access-control.md           # 有界的鉴权与权限模型
    │   ├── secrets.md                  # 有界的密钥管理规则
    │   ├── threat-models/     〔集合〕 # 一个系统或流程的威胁模型一份
    │   ├── controls/          〔集合〕 # 一个安全控制一份
    │   └── findings/          〔集合〕 # 一个安全发现一份
    │
    ├── research/                       # 证据，不是执行指令
    │   ├── feedback/          〔集合〕 # 一条内聚反馈一份
    │   ├── interviews/        〔集合〕 # 一次用户访谈一份
    │   ├── competitors/       〔集合〕 # 一个竞品的时间点快照一份
    │   └── studies/           〔集合〕 # 一次专题或市场研究一份
    │
    ├── work/                           # 执行与跨会话交接
    │   ├── items/             〔集合〕 # 任务、Bug、技术债的唯一状态源
    │   ├── plans/             〔集合〕 # 一个复杂任务的执行计划一份
    │   ├── logs/              〔集合〕 # 一次会话或工作窗口一份
    │   ├── reviews/           〔集合〕 # 一次复盘一份
    │   └── approvals/         〔集合〕 # 一次批准或限定预授权一份
    │
    ├── automation/                     # 可复用流程与未安装的工具适配
    │   ├── workflows/         〔集合〕
    │   │   ├── implement-feature.md    # 功能实现流程
    │   │   ├── fix-bug.md              # Bug 修复流程
    │   │   ├── release.md              # 发布流程
    │   │   ├── incident.md             # 事故处置流程
    │   │   └── docs-audit.md           # 文档检查流程
    │   ├── adapters/
    │   │   ├── README.md
    │   │   ├── _claude.template.md
    │   │   ├── _copilot.template.md
    │   │   └── _local-agents.template.md
    │   └── skills/
    │       ├── README.md
    │       └── _template/
    │           └── SKILL.md
    │
    └── archive/                        # 不进入默认任务上下文
        ├── README.md
        └── records/           〔集合〕 # 一次归档迁移及路径映射一份
```
