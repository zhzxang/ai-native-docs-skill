---
id: "WF-DOCS-AUDIT"
type: "workflow"
status: "draft"
summary: "项目中立的可复用流程；启用前核验适用性与授权。"
owner: null
applies_to: "{{VERSION_OR_SCOPE}}"
verified_at: null
verification_ref: null
authority: "procedure"
approved_by: null
approval_ref: null
---

# 检查文档

## 触发
用于结构调整、重要代码变更后的文档影响检查或已获授权的定期审查。

## 机械检查
运行本套件 check；需要时生成分页索引。检查断链、重复 ID、元数据、路由和配置的结构一致性。生成工具不访问网络或执行项目命令。

## 语义核验
从本次变更关联的规范开始，确认版本、来源、实现和用户承诺是否一致；按需要读取证据。不把重新保存文件或刷新日期当核验。

## 修复
在原权威位置修正；重复状态移除或改生成视图；历史内容标记替代与适用范围。无法确认的内容保留未知，重要缺口形成任务。

## 输出
报告核验范围、已修复项、尚未验证或需要批准的部分。完整文件树是交付参考，不应该成为所有任务的默认上下文。
