---
id: "SEC-SECRETS"
type: "secret-policy"
status: "template"
summary: "凭据存储、注入、轮换、撤销和暴露响应。"
owner: null
applies_to: "{{VERSION_OR_SCOPE}}"
verified_at: null
verification_ref: null
authority: "normative"
approved_by: null
approval_ref: null
---

# 密钥与凭据管理

## 管理原则
这里只记录凭据类别、用途、所在受控系统和访问方式，不记录真实值、恢复码或可直接访问敏感资源的临时链接。

## 凭据登记
| 凭据类别 | 使用主体 | 受控存储位置 | 权限范围 | 轮换 / 撤销程序 |
|---|---|---|---|---|
| {{SECRET_TYPE}} | {{PRINCIPAL}} | {{VAULT_REFERENCE}} | {{SCOPE}} | {{PROCEDURE_REF}} |

## 环境隔离
{{本地、测试、生产凭据如何分离与注入，最小权限和短期凭据的使用。}}

## 开发与 CI
{{安全占位样例、日志脱敏、扫描、构建过程与输出处理。}} 不以提交 .env 或复制生产密钥来简化启动。

## 轮换与暴露
{{有效授权、切换顺序、验证、撤销、审计和事故升级。}} 凭据泄漏后的处置必须按真实系统能力执行，不保证删除 Git 文件就消除泄漏。
