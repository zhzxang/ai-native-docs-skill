---
id: "{{ID}}"
type: "task"
status: "template"
summary: "{{ONE_LINE_SUMMARY}}"
owner: null
applies_to: "{{VERSION_OR_SCOPE}}"
verified_at: null
verification_ref: null
authority: "descriptive"
kind: "feature"
state: "queued"
priority: null
handover_ref: null
---

# {{TITLE}}

> 模板用途：一个工作项的目标、范围、验收、唯一状态与交接定位。 复制成新条目后填写；本模板不代表项目已实现或已批准任何内容。

## 目标与依据
{{需要完成什么、为什么现在做，关联已批准规范和 AC 编号。}} 没有需求依据时先做调查或草拟规范，不自行扩展产品范围。

## 范围与非目标
{{允许修改的功能、模块映射、文档和环境；明确不改什么、不包含哪些外部动作。}}

## 验收与完成条件
| 条件 | 规范依据 | 验证方式 | 证据位置 |
|---|---|---|---|
| {{ACCEPTANCE}} | {{SPEC_AC_REF}} | {{CHECK}} | {{EVIDENCE_OR_NOT_RUN}} |

## Bug 补充（仅 kind=bug）
严重程度与影响：{{SEVERITY_AND_IMPACT}}。受影响版本：{{VERSION}}。复现步骤：{{STEPS}}。预期：{{EXPECTED}}。实际：{{ACTUAL}}。频率与证据：{{FREQUENCY_AND_EVIDENCE}}。临时方案：{{WORKAROUND_OR_NONE}}。

## 依赖、风险与授权
{{前置任务、权限或批准引用、费用与重试边界、破坏性风险和停止条件。}}

## 状态迁移
`state` 是此工作项唯一状态。ready 需要范围与验收清晰且具备对应执行授权；doing 表示已认领；blocked 说明缺什么；done 需要完成证据；deferred/cancelled 记录原因。任务完成不代表已发布。

## 计划与进度记录
简单任务直接在这里保留当前交接摘要。需要复杂计划时创建 plan，并把元数据 `handover_ref` 设为该计划的仓库相对路径；此处不再重复维护计划的下一步。会话经过放独立日志。

## 当前交接（handover_ref 为空时使用）
已确认事实：{{FACTS_AND_REFS}}。
已完成：{{COMPLETED}}。
下一步：{{ONE_CONCRETE_NEXT_ACTION}}。
阻塞：{{BLOCKER_OR_NONE}}。
待运行检查：{{NOT_RUN_CHECKS}}。

## 交付关联
{{提交 / PR、测试报告、文档变更和发布记录。}} 未合并、未部署、未核验的事件必须分别标记。

## 关联与未知项
记录必要的规范 ID、任务 ID、相对文件链接、源系统定位信息和版本；不复制其他权威文档的完整正文。

| 尚未确定的事项 | 影响范围 | 需要的证据或决定 | 是否阻塞执行 |
|---|---|---|---|
| {{UNKNOWN}} | {{IMPACT}} | {{REQUIRED_EVIDENCE}} | {{YES_OR_NO}} |

## 维护与退出条件
相关规范、实现、证据或适用条件变化时，检查本条目是否仍适用。确实不适用的章节写 `不适用：原因`，不要为了填满模板编造信息。被替代时记录替代文档 ID 与路径，并更新 `status`；不要改写历史以假装一直正确。
