# 文档系统说明

本目录说明如何维护文档体系，不默认作为每个任务的完整上下文。按初始化、变更或配置的需要读取。

| 入口 | 内容 |
|---|---|
| [初始化与迁移](bootstrap.md) | 初始化与迁移 |
| [完整写入协议](writing-policy.md) | 所有文档写入的条目边界、最小内容、按需路径与第三条迁移 |
| [35 类原文档迁移对照](original-document-map.md) | 35 类原文档迁移对照 |
| [60 类条目模板](template-catalog.md) | 60 类条目模板 |
| [映射与命令字段说明](configuration-guide.md) | 映射与命令字段说明 |
| [命名、元数据与状态](conventions.md) | 命名、元数据与状态 |
| [权威来源与冲突](authority.md) | 权威来源与冲突 |
| [增长、迁移与归档](lifecycle.md) | 紧凑集合、第三条展开、按需分页与历史保留 |
| [变更影响检查](change-impact.md) | 变更影响检查 |
| [完成与交付判定](definition-of-done.md) | 完成与交付判定 |
| [执行授权策略提案](execution-policy.md) | 执行授权策略提案 |
| [无历史会话交接演练](handover-test.md) | 无历史会话交接演练 |
| [客户端适配](tool-adapters.md) | 客户端适配 |
| [公开规范来源](sources.md) | 公开规范来源 |
| [位置字段参考](project-map.json) | 位置字段与默认就绪约定；真实登记在目标配置 |
| [命令字段参考](commands.json) | 命令字段参考；真实登记在目标配置 |
| [任务路由源](routes.json) | 任务路由源 |
| [集合与模板登记](collections.json) | 集合与模板登记 |
| [系统包版本](package.json) | 来源系统版本与集合 schema 版本 |

本目录属于 Skill 通用资源，不复制到目标项目。初始化仅合并四个 README/AGENTS 入口和保存 `docs/.ai-docs.json`，业务内容按需创建。通用资源直接在 `ai-docs-check/assets/templates/` 维护；Skill与协议回归测试集中在仓库 `tests/`，验证记录在 `docs/validation.md`，不随 Skill 分发；派生索引由目标项目按需生成。

位置和命令 JSON 在这里保留字段参考及默认就绪约定，目标实际位置、命令与定制仅在 `docs/.ai-docs.json` 登记。该配置的 installation 字段记录入口托管区块和基线哈希，服务于重复执行与升级，不登记业务条目数量，也不能代替结构检查或严格就绪检查。
