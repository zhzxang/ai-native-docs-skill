---
id: "ARCH-OVERVIEW"
type: "architecture-overview"
status: "template"
summary: "当前与目标架构、模块边界和关键数据流。"
owner: null
applies_to: "{{VERSION_OR_SCOPE}}"
verified_at: null
verification_ref: null
authority: "descriptive"
---

# 架构总览

## 适用状态
明确描述当前实现还是目标架构；两者并存时分别标记。填写对应提交、部署版本和环境，不用图示代替版本依据。

## 系统上下文
{{用户、前后端、数据库、队列和第三方系统之间的关系。}}

## 模块边界
| 模块 ID | 职责 | 不负责什么 | 允许依赖 | 详细文档 |
|---|---|---|---|---|
| {{MODULE}} | {{RESPONSIBILITY}} | {{NON_GOALS}} | {{DEPENDENCIES}} | {{MODULE_DOC}} |

## 关键数据流
按关键业务说明输入、鉴权、读写、异步事件、外部调用和失败恢复。真实路径使用项目映射；接口和数据结构引用 contracts、db 中的条目。

## 必须保持的约束
{{依赖方向、一致性、安全隔离、可用性和性能约束及其验证方法。}}

## 运行拓扑与部署差异
{{本地、测试、生产的差异；关联环境、部署和服务记录。}}

## 关键决策与已知局限
引用仍适用的 ADR，不抄写完整决策史。列出已知技术债对应任务，不维护第二份任务状态。

## 变更检查
新增模块、修改依赖边界、核心数据流或外部系统时核验本总览；文件目录调整仅更新映射，不必重写全部架构。
