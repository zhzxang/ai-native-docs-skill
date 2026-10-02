---
id: "TEST-STRATEGY"
type: "test-strategy"
status: "template"
summary: "按风险分层的测试范围、环境、数据和验收证据。"
owner: null
applies_to: "{{VERSION_OR_SCOPE}}"
verified_at: null
verification_ref: null
authority: "normative"
approved_by: null
approval_ref: null
---

# 测试策略

## 测试目标与风险
{{最重要的用户路径、不可接受的失败和需优先覆盖的边界。}}

## 分层与入口
| 层级 | 覆盖内容 | 实际位置映射 | 命令 ID | 外部副作用 |
|---|---|---|---|---|
| 单元 | {{SCOPE}} | tests.unit | test-unit | {{NONE_OR_DEFINED}} |
| 集成 | {{SCOPE}} | tests.integration | test-integration | {{SANDBOX_ONLY}} |
| 端到端 | {{SCOPE}} | tests.e2e | test-e2e | {{SANDBOX_ONLY}} |

## 验收映射
功能规范的 AC 编号关联测试用例与实际自动化断言。手工检查要有可复现步骤、观察对象、通过条件和证据；用例存在不表示执行通过。

## 数据与环境
使用合成、脱敏且获准的数据。说明隔离、清理、外部服务 sandbox、时钟/随机性控制和真实费用限制。

## 变更选择
按影响面选择检查，必要时执行回归集合。不强制每个错字修改都跑全部 E2E，也不因时间紧直接跳过关键门禁。

## 失败、波动与例外
{{失败分类、已知不稳定测试、隔离依据和修复任务。}} 不把重试后一次通过当成稳定性证明，不静默删除断言。

## 证据
测试执行报告按 run 单独记录，至少包含提交、环境、命令、结果、未运行项和输出定位。CI 大体积日志保留在受控来源。
