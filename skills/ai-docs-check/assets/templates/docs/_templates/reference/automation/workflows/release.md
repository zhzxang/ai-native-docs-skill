---
id: "WF-RELEASE"
type: "workflow"
status: "template"
summary: "项目中立的可复用流程；启用前核验适用性与授权。"
owner: null
applies_to: "{{VERSION_OR_SCOPE}}"
verified_at: null
verification_ref: null
authority: "procedure"
approved_by: null
approval_ref: null
---

# 执行发布

## 触发与授权
只有当前任务明确包含发布且授权有效时使用。先确认目标环境、工件版本、操作范围、预算、允许窗口与恢复方式。文档里写有部署步骤不代表允许执行。

## 准备
读取适用部署程序、发布检查、迁移计划和相关用户承诺。确认测试证据与即将发布的版本一致，检查未满足门禁和不可逆操作。

## 执行
按获准流程逐步操作，记录实际时间、版本、结果和副作用。关键门禁失败或恢复前提不成立时停止，不擅自扩大动作。

## 验证与恢复
完成版本与健康确认、关键用户路径和必要观察。触发恢复条件时使用已核验且获准的恢复或前向修复方案。

## 记录
创建独立 release 条目，只有真实事件发生才更新 release_state。用户 Changelog 从这一记录提取，不维护根目录无限增长的日志。

## 所有文档写入

写入前从匹配版本的 Skill 读取 `docs/_system/writing-policy.md` 和分类注册表，先查同主题条目。已有对象更新原条目；新对象分配独立 ID。1–2 条保留在 `<base_path>.md`，第 3 条才展开为集合目录；已展开后不自动收拢。使用类型专属的最小充分内容，不预建空壳。迁移保留 ID、状态、范围和证据，修复入出链、锚点与索引，最终运行结构检查并明确未完成核验。
