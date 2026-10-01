---
id: "{{ID}}"
type: "journey"
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

> 模板用途：一个跨页面或跨功能流程的路径、分支与中断恢复。 复制成新条目后填写；本模板不代表项目已实现或已批准任何内容。

## 场景与参与者
{{用户目标、进入条件、角色、渠道与关联功能。}}

## 入口和终点
入口：{{ENTRY}}。成功终点：{{SUCCESS}}。失败或退出终点：{{FAILURE_OR_EXIT}}。

## 主流程
| 步骤 | 页面 / 系统 | 用户动作或触发 | 系统响应 | 状态变化 | 关联规范 |
|---|---|---|---|---|---|
| 1 | {{PAGE_OR_SYSTEM}} | {{ACTION}} | {{RESPONSE}} | {{TRANSITION}} | {{SPEC_REF}} |

## 分支和恢复
{{未登录、权限不足、支付失败、断网、刷新、跨设备、重复进入等适用分支；说明从哪里继续。}}

## 体验与数据约束
{{用户必须看到的信息、可取消点、可访问性、敏感数据处理及埋点关系。}}

## 验证
{{按路径覆盖的场景和证据，关联测试集合。}} 业务细则留在功能规范，本文件只描述跨功能衔接。

## 关联与未知项
记录必要的规范 ID、任务 ID、相对文件链接、源系统定位信息和版本；不复制其他权威文档的完整正文。

| 尚未确定的事项 | 影响范围 | 需要的证据或决定 | 是否阻塞执行 |
|---|---|---|---|
| {{UNKNOWN}} | {{IMPACT}} | {{REQUIRED_EVIDENCE}} | {{YES_OR_NO}} |

## 维护与退出条件
相关规范、实现、证据或适用条件变化时，检查本条目是否仍适用。确实不适用的章节写 `不适用：原因`，不要为了填满模板编造信息。被替代时记录替代文档 ID 与路径，并更新 `status`；不要改写历史以假装一直正确。
