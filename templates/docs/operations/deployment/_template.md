---
id: "{{ID}}"
type: "deployment"
status: "template"
summary: "{{ONE_LINE_SUMMARY}}"
owner: null
applies_to: "{{VERSION_OR_SCOPE}}"
verified_at: null
verification_ref: null
authority: "procedure"
approved_by: null
approval_ref: null
---

# {{TITLE}}

> 模板用途：一种目标环境或部署方式的步骤、门禁与恢复方法。 复制成新条目后填写；本模板不代表项目已实现或已批准任何内容。

## 适用范围
{{环境、应用或部署方式、预期起始版本、支持的发布类型。}}

## 前置条件与授权
{{审批、构建来源、检查结果、账户权限、预算和发布窗口。}}

## 发布顺序
| 步骤 | 命令 ID / 操作入口 | 成功判据 | 失败处理 |
|---|---|---|---|
| 构建 / 获取工件 | {{ACTION}} | {{ARTIFACT_ID}} | {{STOP}} |
| 配置与迁移 | {{ACTION_OR_NA}} | {{VALIDATION}} | {{RECOVERY}} |
| 发布 | {{ACTION}} | {{VERSION_AND_HEALTH}} | {{RECOVERY}} |
| 流量切换 | {{ACTION_OR_NA}} | {{SIGNAL}} | {{RECOVERY}} |

## 运行要素
{{域名、证书、CDN、缓存、环境配置、数据库迁移顺序；引用对应服务和配置，不复制密钥。}}

## 发布后验证
{{关键路径、指标、日志、版本确认、观察窗口与故障升级。}}

## 恢复策略
{{回滚工件、数据兼容性、前向修复、缓存恢复和不可逆部分。}} 明确恢复成功判据，不承诺未经演练的恢复能力。

## 记录
每次执行进入独立发布记录；本程序只维护可复用步骤，不持续追加所有版本结果。

## 关联与未知项
记录必要的规范 ID、任务 ID、相对文件链接、源系统定位信息和版本；不复制其他权威文档的完整正文。

| 尚未确定的事项 | 影响范围 | 需要的证据或决定 | 是否阻塞执行 |
|---|---|---|---|
| {{UNKNOWN}} | {{IMPACT}} | {{REQUIRED_EVIDENCE}} | {{YES_OR_NO}} |

## 维护与退出条件
相关规范、实现、证据或适用条件变化时，检查本条目是否仍适用。确实不适用的章节写 `不适用：原因`，不要为了填满模板编造信息。被替代时记录替代文档 ID 与路径，并更新 `status`；不要改写历史以假装一直正确。
