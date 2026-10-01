---
id: "{{ID}}"
type: "metric"
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

> 模板用途：一个指标的业务口径、公式、数据来源和验证。 复制成新条目后填写；本模板不代表项目已实现或已批准任何内容。

## 业务含义
{{指标用于判断什么问题、谁使用、哪些决策不适合依赖它。}}

## 精确定义
| 维度 | 定义 |
|---|---|
| 统计单位 | {{USER_ACCOUNT_OR_ORGANIZATION}} |
| 分子 | {{NUMERATOR}} |
| 分母 | {{DENOMINATOR_OR_NA}} |
| 事件时间 / 时区 | {{EVENT_TIME_AND_TIMEZONE}} |
| 观察窗口 / Cohort | {{WINDOW_AND_COHORT}} |
| 去重与身份合并 | {{DEDUP_IDENTITY}} |
| 排除条件 | {{BOTS_INTERNAL_REFUNDS_ETC}} |
| 延迟与补数 | {{LATE_DATA_AND_BACKFILL}} |

## 公式和实现
{{完整公式，包括分母为零和缺失值的处理。}} 查询或计算代码通过映射引用，不在多个文档中手工维护同一 SQL。

## 数据来源
{{事件 ID、实体 ID、字段语义、版本及数据权限。}}

## 核验样例
| 合成输入 | 应得到的结果 | 验证依据 |
|---|---|---|
| {{SYNTHETIC_DATA}} | {{EXPECTED_VALUE}} | {{TEST_OR_QUERY_REF}} |

## 解释限制
{{偏差、样本量、可比较区间、定义变化与历史重算影响。}} 目标值、观测值和历史基准分别注明来源；不要混成同一数字。

## 关联与未知项
记录必要的规范 ID、任务 ID、相对文件链接、源系统定位信息和版本；不复制其他权威文档的完整正文。

| 尚未确定的事项 | 影响范围 | 需要的证据或决定 | 是否阻塞执行 |
|---|---|---|---|
| {{UNKNOWN}} | {{IMPACT}} | {{REQUIRED_EVIDENCE}} | {{YES_OR_NO}} |

## 维护与退出条件
相关规范、实现、证据或适用条件变化时，检查本条目是否仍适用。确实不适用的章节写 `不适用：原因`，不要为了填满模板编造信息。被替代时记录替代文档 ID 与路径，并更新 `status`；不要改写历史以假装一直正确。
