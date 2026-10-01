---
id: "{{ID}}"
type: "competitor"
status: "template"
summary: "{{ONE_LINE_SUMMARY}}"
owner: null
applies_to: "{{VERSION_OR_SCOPE}}"
verified_at: null
verification_ref: null
authority: "evidence"
---

# {{TITLE}}

> 模板用途：一个竞品在特定时间的功能、价格、定位和来源快照。 复制成新条目后填写；本模板不代表项目已实现或已批准任何内容。

## 采集边界
{{对象、产品版本、地区、套餐、采集日期与研究问题。}}

## 可核验事实
| 维度 | 观察事实 | 来源与采集时间 | 限制 |
|---|---|---|---|
| 定位 | {{FACT}} | {{SOURCE}} | {{LIMITATION}} |
| 功能 | {{FACT}} | {{SOURCE}} | {{LIMITATION}} |
| 价格 | {{AMOUNT_UNIT_CURRENCY}} | {{SOURCE}} | {{TAX_REGION_TERM}} |
| 用户评价 | {{OBSERVATION}} | {{SOURCE_AND_SAMPLE}} | {{BIAS}} |

## 分析与假设
{{清楚区分事实、推断和待验证判断；不把过时价格当当前价格。}}

## 对项目的意义
{{可能影响的功能、定位、商业假设或研究，不自动转成批准需求。}}

## 更新方式
需要新的时间点时新建快照或明示核验版本，不抹掉历史采集事实。

## 关联与未知项
记录必要的规范 ID、任务 ID、相对文件链接、源系统定位信息和版本；不复制其他权威文档的完整正文。

| 尚未确定的事项 | 影响范围 | 需要的证据或决定 | 是否阻塞执行 |
|---|---|---|---|
| {{UNKNOWN}} | {{IMPACT}} | {{REQUIRED_EVIDENCE}} | {{YES_OR_NO}} |

## 维护与退出条件
相关规范、实现、证据或适用条件变化时，检查本条目是否仍适用。确实不适用的章节写 `不适用：原因`，不要为了填满模板编造信息。被替代时记录替代文档 ID 与路径，并更新 `status`；不要改写历史以假装一直正确。
