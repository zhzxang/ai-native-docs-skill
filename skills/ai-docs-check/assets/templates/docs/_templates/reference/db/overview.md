---
id: "DB-OVERVIEW"
type: "database-overview"
status: "template"
summary: "数据域、真实结构来源、关系和生命周期边界。"
owner: null
applies_to: "{{VERSION_OR_SCOPE}}"
verified_at: null
verification_ref: null
authority: "descriptive"
---

# 数据设计总览

## 数据域与语义
{{核心实体、所有权、租户边界以及系统间的数据责任。}}

## 真实结构来源
通过项目映射登记数据库类型、Schema 或迁移链、实际环境和生成文档方向。此处不假定任何 ORM 或迁移目录，也不手写复制整份字段列表。

## 关系与一致性
{{实体关系、唯一性、事务边界、最终一致性和删除传播规则。}}

## 数据生命周期
引用 lifecycle 条目，覆盖收集、用途、保存、备份、归档、删除、导出和第三方传播；未确认的保留时间不得自行设定。

## 读写与性能
{{关键读写模式、索引依据、容量假设与测量方法。}}

## 迁移安全
迁移方案放 migrations 集合，实际迁移代码位置由映射指定。破坏性迁移必须说明兼容窗口、数据验证、备份与恢复；不可逆时写补偿或前向修复，不承诺不存在的 rollback。

## 当前限制
{{已发现的问题、证据和关联任务。}}
