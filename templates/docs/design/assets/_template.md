---
id: "{{ID}}"
type: "design-asset"
status: "template"
summary: "{{ONE_LINE_SUMMARY}}"
owner: null
applies_to: "{{VERSION_OR_SCOPE}}"
verified_at: null
verification_ref: null
authority: "descriptive"
---

# {{TITLE}}

> 模板用途：一个外部设计文件或批准快照的定位与可信边界。 复制成新条目后填写；本模板不代表项目已实现或已批准任何内容。

## 资产职责
{{这个设计资产覆盖哪些页面或组件；不覆盖什么。}}

## 来源定位
| 字段 | 内容 |
|---|---|
| 系统 | {{FIGMA_OR_OTHER}} |
| 文件 / 节点标识 | {{FILE_AND_NODE}} |
| 可访问地址 | {{AUTHORIZED_LOCATION}} |
| 版本或采集时间 | {{REVISION_OR_CAPTURE_TIME}} |
| 读取方式 / 权限 | {{ACCESS_METHOD}} |
| 批准依据 | {{APPROVAL_REF}} |

## 仓库快照
{{必要时保存的安全静态快照位置、来源版本和生成方法；快照不是自动最新。}}

## 源不可访问时
{{可继续的工作、需要暂停的设计判断及联系/恢复入口。}}

## 关系
{{页面、组件、Token 和实现映射。}} 不以一个无法打开的链接替代全部设计约束。

## 关联与未知项
记录必要的规范 ID、任务 ID、相对文件链接、源系统定位信息和版本；不复制其他权威文档的完整正文。

| 尚未确定的事项 | 影响范围 | 需要的证据或决定 | 是否阻塞执行 |
|---|---|---|---|
| {{UNKNOWN}} | {{IMPACT}} | {{REQUIRED_EVIDENCE}} | {{YES_OR_NO}} |

## 维护与退出条件
相关规范、实现、证据或适用条件变化时，检查本条目是否仍适用。确实不适用的章节写 `不适用：原因`，不要为了填满模板编造信息。被替代时记录替代文档 ID 与路径，并更新 `status`；不要改写历史以假装一直正确。
