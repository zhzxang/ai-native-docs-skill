---
id: "{{ID}}"
type: "plan"
status: "template"
summary: "{{ONE_LINE_SUMMARY}}"
owner: null
applies_to: "{{VERSION_OR_SCOPE}}"
verified_at: null
verification_ref: null
authority: "descriptive"
---

# {{TITLE}}

> 模板用途：一个复杂任务的执行结构、当前进度和唯一交接摘要。 复制成新条目后填写；本模板不代表项目已实现或已批准任何内容。

## 关联任务与使用理由
任务 ID：{{TASK_ID}}。为何需要计划：{{跨模块 / 迁移 / 跨会话 / 风险理由}}。任务状态仍由工作项拥有，本文件不设置第二个任务 state。

## 依据与边界
{{必读的规范 ID、实现定位、验收编号、授权与不可更改的边界。}}

## 分步方案
| 步骤 | 目标与动作 | 验证 / 证据 | 当前步骤结论 |
|---|---|---|---|
| 1 | {{ACTION}} | {{CHECK}} | {{NOT_STARTED_OR_RESULT}} |

## 当前发现与决定
只保留影响后续执行的事实和决定摘要，附来源。重要技术决定形成 ADR；完整会话经过进入日志，不在计划无限追加。

## 唯一交接摘要
起始/当前分支与提交：{{BRANCH_AND_REVISION}}。
已完成：{{COMPLETED_WITH_EVIDENCE}}。
剩余：{{REMAINING}}。
下一步：{{DIRECTLY_EXECUTABLE_NEXT_STEP}}。
未提交与并发改动：{{WORKTREE_NOTES}}。
阻塞与停止原因：{{BLOCKERS}}。
未验证项：{{NOT_VERIFIED}}。

## 验证与恢复
{{检查选择、真实报告引用、失败恢复或前向修复办法、预算与重试限制。}}

## 关闭
确认工作项验收与交接资料齐全后结束计划；是否合并和发布由各自记录确认。

## 关联与未知项
记录必要的规范 ID、任务 ID、相对文件链接、源系统定位信息和版本；不复制其他权威文档的完整正文。

| 尚未确定的事项 | 影响范围 | 需要的证据或决定 | 是否阻塞执行 |
|---|---|---|---|
| {{UNKNOWN}} | {{IMPACT}} | {{REQUIRED_EVIDENCE}} | {{YES_OR_NO}} |

## 维护与退出条件
相关规范、实现、证据或适用条件变化时，检查本条目是否仍适用。确实不适用的章节写 `不适用：原因`，不要为了填满模板编造信息。被替代时记录替代文档 ID 与路径，并更新 `status`；不要改写历史以假装一直正确。
