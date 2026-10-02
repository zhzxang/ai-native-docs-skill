---
id: "SEC-ACCESS"
type: "access-policy"
status: "template"
summary: "角色、资源、动作、租户隔离和敏感操作边界。"
owner: null
applies_to: "{{VERSION_OR_SCOPE}}"
verified_at: null
verification_ref: null
authority: "normative"
approved_by: null
approval_ref: null
---

# 鉴权与权限模型

## 主体与资源
{{用户、系统身份、管理员和 Agent；资源及所有权。}}

## 权限矩阵
| 主体 / 角色 | 资源范围 | 允许动作 | 条件与拒绝情况 | 实现 / 测试依据 |
|---|---|---|---|---|
| {{ROLE}} | {{RESOURCE_SCOPE}} | {{ACTIONS}} | {{CONDITIONS}} | {{EVIDENCE}} |

## 身份生命周期
{{注册、认证、会话刷新、撤销、禁用与删除；外部身份提供商关系。}}

## 多租户与对象级检查
{{在哪里验证租户、对象归属和字段访问；如何防止跨边界读取与写入。}}

## 敏感动作
{{重新认证、审批、审计和异常处理规则；与 AI 执行授权的衔接。}}

## 验证
{{允许与拒绝场景、水平与垂直权限测试、会话失效和异常输入。}}
