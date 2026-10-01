---
id: "{{ID}}"
type: "pricing"
status: "template"
summary: "{{ONE_LINE_SUMMARY}}"
owner: null
applies_to: "{{VERSION_OR_SCOPE}}"
verified_at: null
verification_ref: null
authority: "normative"
approved_by: null
approval_ref: null
effective_from: null
effective_until: null
---

# {{TITLE}}

> 模板用途：一个生效范围明确的定价版本、套餐限制和试用规则。 复制成新条目后填写；本模板不代表项目已实现或已批准任何内容。

## 版本与适用范围
{{产品、币种、地区或市场、用户类别、生效起止时间、旧用户规则。}}

## 套餐规则
| 套餐 | 收费方式 | 金额 / 单位 | 权益与限制 | 试用 / 免费规则 |
|---|---|---|---|---|
| {{PLAN}} | {{BILLING_MODEL}} | {{PRICE_AND_CURRENCY}} | {{ENTITLEMENT_REFS}} | {{TRIAL_RULE}} |

## 计费语义
{{周期、时区、用量、超额、税费、折扣、按比例计算、升级/降级与失败扣款行为。}} 不从模板猜测支付平台能力。

## 取消与退款
引用有效退款/取消规则及订阅功能规范，不在此维护相互冲突的另一套规则。

## 实现与展示
{{实际价格配置、支付平台对象映射、权益配置、官网/应用/FAQ 的引用。}} 商业规范和实际配置需对账核验。

## 生效与历史
{{批准主体、迁移用户范围、通知要求、发布记录、撤回或更正方法。}} 编辑文档不等于执行调价。

## 验证
{{合成或 sandbox 计费、权益、边界和页面一致性检查；不能未经授权真实扣款。}}

## 关联与未知项
记录必要的规范 ID、任务 ID、相对文件链接、源系统定位信息和版本；不复制其他权威文档的完整正文。

| 尚未确定的事项 | 影响范围 | 需要的证据或决定 | 是否阻塞执行 |
|---|---|---|---|
| {{UNKNOWN}} | {{IMPACT}} | {{REQUIRED_EVIDENCE}} | {{YES_OR_NO}} |

## 维护与退出条件
相关规范、实现、证据或适用条件变化时，检查本条目是否仍适用。确实不适用的章节写 `不适用：原因`，不要为了填满模板编造信息。被替代时记录替代文档 ID 与路径，并更新 `status`；不要改写历史以假装一直正确。
