---
id: "{{ID}}"
type: "release-checklist"
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

> 模板用途：一种发布类型的可复用检查项与阻断规则。 复制成新条目后填写；本模板不代表项目已实现或已批准任何内容。

## 使用条件
{{正常发布、支付变更、数据迁移、紧急修复等具体类型。}}

## 发布前
| 检查 | 何时适用 | 通过依据 / 自动化入口 | 失败处理 |
|---|---|---|---|
| 范围与验收 | 所有发布 | {{SPEC_TASK_AND_TEST_REFS}} | 阻断未完成的关键要求 |
| 数据库 / 迁移 | 影响数据时 | {{MIGRATION_AND_RECOVERY}} | 无安全方案不执行 |
| 支付与权益 | 涉及计费时 | {{SANDBOX_AND_RULE_TESTS}} | 不以真实扣费替代测试 |
| 邮件与外发 | 涉及通知时 | {{SAFE_TEST_AND_AUTH}} | 未授权不得批量发送 |
| 指标与监测 | 影响行为或运行时 | {{METRIC_AND_SIGNAL_CHECKS}} | 明确缺失监测风险 |
| 页面 / SEO / 可访问性 | 影响前台时 | {{CHECK_REFS}} | 按批准门禁处理 |
| 配置 / 密钥 / 权限 | 相关变更时 | {{SECURITY_CHECKS}} | 缺权限或有泄漏时阻断 |
| 用户承诺 | 影响价格、政策或行为时 | {{APPROVED_TEXT_REFS}} | 不发布未经批准的承诺 |

## 发布中与发布后
{{部署顺序、版本确认、健康检查、观察窗口、恢复触发条件。}}

## 执行记录方式
每次发布在 release 条目中逐项记录 passed / failed / skipped / not_applicable / not_run 及依据；不在本检查程序上累积版本历史。`not_applicable` 需要理由，不能用于掩盖未验证。

## 关联与未知项
记录必要的规范 ID、任务 ID、相对文件链接、源系统定位信息和版本；不复制其他权威文档的完整正文。

| 尚未确定的事项 | 影响范围 | 需要的证据或决定 | 是否阻塞执行 |
|---|---|---|---|
| {{UNKNOWN}} | {{IMPACT}} | {{REQUIRED_EVIDENCE}} | {{YES_OR_NO}} |

## 维护与退出条件
相关规范、实现、证据或适用条件变化时，检查本条目是否仍适用。确实不适用的章节写 `不适用：原因`，不要为了填满模板编造信息。被替代时记录替代文档 ID 与路径，并更新 `status`；不要改写历史以假装一直正确。
