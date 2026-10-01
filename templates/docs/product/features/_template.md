---
id: "{{ID}}"
type: "feature"
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

> 模板用途：一个可独立讨论的功能的目标、规则、异常与验收。 复制成新条目后填写；本模板不代表项目已实现或已批准任何内容。

## 问题与用户
{{目标用户、触发情境、当前问题和研究依据。}}

## 目标与非目标
目标：{{OUTCOMES}}。不包含：{{NON_GOALS}}。说明它是目标规范还是对已发布行为的描述，关联适用版本。

## 用户故事
作为 {{ROLE}}，在 {{CONTEXT}} 下，希望 {{ACTION}}，从而 {{VALUE}}。

## 业务规则
| 规则 ID | 条件 | 必须发生的行为 | 例外 / 优先级 | 权威来源 |
|---|---|---|---|---|
| BR-01 | {{CONDITION}} | {{BEHAVIOR}} | {{EXCEPTION}} | {{SOURCE}} |

## 状态与主流程
{{状态、允许的转换、输入、权限检查、数据读写和成功结果；跨功能流程引用 journey。}}

## 异常与边界
逐项判断无权限、空数据、重复提交、并发、超时、外部依赖失败、取消和恢复是否适用，写出预期行为，而不只列出异常名称。

## 验收标准
| AC ID | 前提 Given | 动作 When | 可观察结果 Then | 验证入口 |
|---|---|---|---|---|
| AC-01 | {{PRECONDITION}} | {{ACTION}} | {{OBSERVABLE_RESULT}} | {{TEST_ID_OR_MANUAL_CHECK}} |

## 接口、数据、设计与指标影响
关联 API / 事件 / 实体 / 页面 / 指标 ID。敏感功能补充权限、隐私、退款和定价影响；不要复制这些规则的正文。

## 上线与回退考虑
{{兼容策略、功能开关、迁移、灰度、观测及安全恢复条件。}} 此处不代表发布已获授权。

## 实现关系
{{对应任务、代码映射和发布记录。}} `status: active` 只表示规范生效，不意味着实现或上线。

## 关联与未知项
记录必要的规范 ID、任务 ID、相对文件链接、源系统定位信息和版本；不复制其他权威文档的完整正文。

| 尚未确定的事项 | 影响范围 | 需要的证据或决定 | 是否阻塞执行 |
|---|---|---|---|
| {{UNKNOWN}} | {{IMPACT}} | {{REQUIRED_EVIDENCE}} | {{YES_OR_NO}} |

## 维护与退出条件
相关规范、实现、证据或适用条件变化时，检查本条目是否仍适用。确实不适用的章节写 `不适用：原因`，不要为了填满模板编造信息。被替代时记录替代文档 ID 与路径，并更新 `status`；不要改写历史以假装一直正确。
