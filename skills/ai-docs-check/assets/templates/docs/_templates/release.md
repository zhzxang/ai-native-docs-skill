---
id: "{{ID}}"
slug: "{{SLUG}}"
type: "release"
status: "template"
summary: "{{ONE_LINE_SUMMARY}}"
owner: null
applies_to: "{{VERSION_OR_SCOPE}}"
verified_at: null
verification_ref: null
authority: "evidence"
release_state: "planned"
---

# {{TITLE}}

> 集中参考源；只在存在真实条目时按写入协议实例化。可省略不适用的可选内容；影响正确性、授权或验收的未知项必须明确保留。

## 版本与变化
记录目标及实际版本、范围、用户变化与关联规范。

## 执行与证据
引用批准、检查、部署和测试证据，记录数据兼容与恢复安排。

## 状态与未解决项
release_state 唯一表示 planned/released/rolled-back 等发布状态，status 表示文档有效性；记录未解决问题，未部署不能写已上线。
