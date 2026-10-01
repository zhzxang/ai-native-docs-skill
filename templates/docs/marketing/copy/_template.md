---
id: "{{ID}}"
type: "copy"
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

> 模板用途：一个页面、渠道或用途的文案及其事实依据。 复制成新条目后填写；本模板不代表项目已实现或已批准任何内容。

## 使用位置
{{Landing Page、广告、应用商店或邮件等用途，目标受众和版本。}}

## 文案正文
标题：{{HEADLINE}}。副标题：{{SUBTITLE}}。主体：{{BODY}}。行动按钮：{{CTA}}。必要限制说明：{{DISCLOSURE}}。

## 承诺与依据
| 文案主张 | 支持的当前事实 | 适用范围 / 限制 |
|---|---|---|
| {{CLAIM}} | {{SPEC_RELEASE_OR_EVIDENCE}} | {{LIMITATION}} |

## 变体与语言
{{必要的 A/B 变体或语言策略，关联实验；避免在一个文件无限累积无关历史版本。}}

## 审查与发布
{{批准、实际发布位置、版本和撤回/更正入口。}} 未批准草案不能成为自动外发材料。

## 关联与未知项
记录必要的规范 ID、任务 ID、相对文件链接、源系统定位信息和版本；不复制其他权威文档的完整正文。

| 尚未确定的事项 | 影响范围 | 需要的证据或决定 | 是否阻塞执行 |
|---|---|---|---|
| {{UNKNOWN}} | {{IMPACT}} | {{REQUIRED_EVIDENCE}} | {{YES_OR_NO}} |

## 维护与退出条件
相关规范、实现、证据或适用条件变化时，检查本条目是否仍适用。确实不适用的章节写 `不适用：原因`，不要为了填满模板编造信息。被替代时记录替代文档 ID 与路径，并更新 `status`；不要改写历史以假装一直正确。
