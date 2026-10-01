---
id: "SEC-BASELINE"
type: "security-baseline"
status: "draft"
summary: "项目需要保护的资产、信任边界和验证要求。"
owner: null
applies_to: "{{VERSION_OR_SCOPE}}"
verified_at: null
verification_ref: null
authority: "normative"
approved_by: null
approval_ref: null
---

# 安全基线

## 资产与边界
{{账户、租户、业务数据、密钥、资金路径、供应链和备份资产。}}

## 主要威胁与控制
{{按项目实际风险列出控制原则，关联 threat-models 和 controls 条目。}} 不把通用模板当作已通过安全审计。

## 身份与权限
引用 access-control 文档；说明默认拒绝、最小授权、对象级访问判断和敏感操作检查的实际实现与测试入口。

## 数据与密钥
引用数据生命周期和 secrets 文档；不得将真实密钥或用户数据放进例子、测试夹具和 AI 上下文。

## Agent 环境
{{允许访问的仓库、网络、凭据、工具与预算。}} 文档规则需要沙箱、凭据范围、CI 和批准机制落实。

## 备份与事故
关联恢复方案、恢复演练、事故 Runbook。未做恢复演练不得将“有备份”写成“可恢复已验证”。

## 验证与例外
{{检查、证据、批准例外、到期与撤回办法。}}
