---
id: "{{ID}}"
type: "term"
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

> 模板用途：一个术语的定义、边界和同义词。 复制成新条目后填写；本模板不代表项目已实现或已批准任何内容。

## 定义
{{术语在本项目中的准确含义；不要仅复制词典解释。}}

## 使用与排除
{{适用场景、明确不包含的概念以及容易混淆的近义词。}}

## 对应表示
| 表示层 | 使用名称 | 来源 |
|---|---|---|
| 用户界面 | {{UI_NAME}} | {{PAGE_OR_COPY}} |
| 业务规范 | {{SPEC_NAME}} | {{SPEC_REF}} |
| 代码 / 数据 | {{IMPLEMENTATION_NAME}} | {{MAPPING_OR_DOC}} |

## 例子与反例
正确使用：{{EXAMPLE}}。不正确使用：{{COUNTEREXAMPLE_AND_REASON}}。

## 变更影响
术语改变后检查 UI、API、数据说明、FAQ 和营销承诺；不要因名称变化默默修改实际语义。

## 关联与未知项
记录必要的规范 ID、任务 ID、相对文件链接、源系统定位信息和版本；不复制其他权威文档的完整正文。

| 尚未确定的事项 | 影响范围 | 需要的证据或决定 | 是否阻塞执行 |
|---|---|---|---|
| {{UNKNOWN}} | {{IMPACT}} | {{REQUIRED_EVIDENCE}} | {{YES_OR_NO}} |

## 维护与退出条件
相关规范、实现、证据或适用条件变化时，检查本条目是否仍适用。确实不适用的章节写 `不适用：原因`，不要为了填满模板编造信息。被替代时记录替代文档 ID 与路径，并更新 `status`；不要改写历史以假装一直正确。
