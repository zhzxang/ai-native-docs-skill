---
id: "{{ID}}"
slug: "{{SLUG}}"
type: "task"
status: "template"
summary: "{{ONE_LINE_SUMMARY}}"
owner: null
applies_to: "{{VERSION_OR_SCOPE}}"
verified_at: null
verification_ref: null
authority: "descriptive"
kind: "feature"
state: "queued"
priority: null
handover_ref: null
---

# {{TITLE}}

> 集中参考源；只在存在真实条目时按写入协议实例化。可省略不适用的可选内容；影响正确性、授权或验收的未知项必须明确保留。

## 目标与范围
引用需求依据，记录允许修改范围、必要依赖和授权。kind=bug 时补充复现、预期、实际与影响。

## 验收与证据
记录可核验完成条件、检查入口和实际证据；完成不等于已合并、部署或上线。

## 唯一状态与交接
state 是唯一执行状态，status 是文档有效性。handover_ref 有值时交接仅在关联计划维护，否则记录已完成、下一步、阻塞及待检查项；未知验收或权限不可省略。
