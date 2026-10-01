---
id: "{{ID}}"
type: "dev-guide"
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

> 模板用途：一个特定开发任务的前提、步骤、验证和故障处理。 复制成新条目后填写；本模板不代表项目已实现或已批准任何内容。

## 使用时机
{{何种任务需要本指南，何种情况不适用。}}

## 前提与权限
{{运行环境、工具版本、已授权访问和副作用；引用有效命令记录。}}

## 操作步骤
| 步骤 | 命令 ID / 明确动作 | 成功信号 | 失败时处理 |
|---|---|---|---|
| 1 | {{ACTION}} | {{SUCCESS_CRITERION}} | {{FAILURE_ACTION}} |

## 验证与清理
{{如何证明结果、如何清理临时资源、不影响其他开发者。}}

## 常见故障
{{症状、排查顺序、明确停止条件和相关 Runbook。}}

## 核验记录
{{实际验证过的环境、版本和证据引用。}}

## 关联与未知项
记录必要的规范 ID、任务 ID、相对文件链接、源系统定位信息和版本；不复制其他权威文档的完整正文。

| 尚未确定的事项 | 影响范围 | 需要的证据或决定 | 是否阻塞执行 |
|---|---|---|---|
| {{UNKNOWN}} | {{IMPACT}} | {{REQUIRED_EVIDENCE}} | {{YES_OR_NO}} |

## 维护与退出条件
相关规范、实现、证据或适用条件变化时，检查本条目是否仍适用。确实不适用的章节写 `不适用：原因`，不要为了填满模板编造信息。被替代时记录替代文档 ID 与路径，并更新 `status`；不要改写历史以假装一直正确。
