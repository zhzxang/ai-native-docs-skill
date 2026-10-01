---
id: "WF-FIX-BUG"
type: "workflow"
status: "draft"
summary: "项目中立的可复用流程；启用前核验适用性与授权。"
owner: null
applies_to: "{{VERSION_OR_SCOPE}}"
verified_at: null
verification_ref: null
authority: "procedure"
approved_by: null
approval_ref: null
---

# 修复 Bug

## 触发
用于明确或需要调查的缺陷报告。

## 定位
查找 kind=bug 的任务，确认环境、版本、复现、预期和实际差异。预期依据来自适用规范，不是单凭当前代码。检查相关历史变更和必要证据，不默认读取全部日志。

## 修复
优先建立可复现检查，选择与根因匹配的最小完整修改；无法复现时记录调查事实和剩余假设，不假装找到根因。

## 验证
执行回归测试和影响面检查，区分 passed、failed、not_run。临时绕过需要说明风险、授权与后续任务。

## 交付
更新 Bug 任务、测试和必要的 Runbook/FAQ。任务修复不意味着生产已恢复；上线与线上确认记录在发布或事故条目。
