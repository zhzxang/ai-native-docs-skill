---
id: "{{ID}}"
type: "roadmap"
status: "template"
summary: "{{ONE_LINE_SUMMARY}}"
owner: null
applies_to: "{{VERSION_OR_SCOPE}}"
verified_at: null
verification_ref: null
authority: "normative"
approved_by: null
approval_ref: null
---

# {{TITLE}}

> 模板用途：一个阶段或时间窗口的目标、取舍和退出条件。 复制成新条目后填写；本模板不代表项目已实现或已批准任何内容。

## 时间与阶段
阶段：{{MVP_OR_PHASE}}。窗口：{{START_END_OR_UNSCHEDULED}}。这里的时间是规划，不是已承诺发布事实。

## 目标与证据
{{该阶段要验证的用户价值、商业假设和支持优先级的证据。}}

## 纳入与排除
| 能力 / 结果 | 关联功能或任务 ID | 优先级理由 | 不做的边界 |
|---|---|---|---|
| {{OUTCOME}} | {{REFERENCES}} | {{WHY_NOW}} | {{NON_GOALS}} |

## 完成与退出条件
{{可度量成果、观察窗口、质量要求；何时应调整或取消阶段。}}

## 依赖与资源
{{前置能力、外部依赖、开发者时间与成本限制；不重复任务执行状态。}}

## 变更决策
{{重大调整的批准依据和原因。}} 任务状态查询任务集合，实际发布查询发布集合。

## 关联与未知项
记录必要的规范 ID、任务 ID、相对文件链接、源系统定位信息和版本；不复制其他权威文档的完整正文。

| 尚未确定的事项 | 影响范围 | 需要的证据或决定 | 是否阻塞执行 |
|---|---|---|---|
| {{UNKNOWN}} | {{IMPACT}} | {{REQUIRED_EVIDENCE}} | {{YES_OR_NO}} |

## 维护与退出条件
相关规范、实现、证据或适用条件变化时，检查本条目是否仍适用。确实不适用的章节写 `不适用：原因`，不要为了填满模板编造信息。被替代时记录替代文档 ID 与路径，并更新 `status`；不要改写历史以假装一直正确。
