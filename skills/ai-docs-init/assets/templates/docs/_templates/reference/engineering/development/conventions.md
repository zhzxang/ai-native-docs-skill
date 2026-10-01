---
id: "DEV-CONVENTIONS"
type: "development-conventions"
status: "template"
summary: "项目特有的组织、命名、错误处理和变更边界。"
owner: null
applies_to: "{{VERSION_OR_SCOPE}}"
verified_at: null
verification_ref: null
authority: "normative"
approved_by: null
approval_ref: null
---

# 开发约定

## 适用范围
{{语言、模块或子项目。}} 能被格式化器、lint 和类型系统强制的规则由配置拥有，不在文档中重复成大段通用常识。

## 模块与依赖
{{项目特有的依赖方向、共享代码边界、公共接口和禁止跨越的层。}}

## 命名和错误处理
{{必须约定的业务术语、错误分类、日志字段和敏感字段处理。}}

## 状态、并发和外部调用
{{适用的幂等、事务、取消、重试和超时规则。}} 引用契约与架构依据，不能凭模板设定业务数值。

## 提交和评审
{{分支、提交、变更范围与评审要求。}} 测试和权限保护变更走保护性流程；不为通过 CI 删除有效断言。

## 例外
{{已批准例外及原因、范围、期限和回收任务。}}
