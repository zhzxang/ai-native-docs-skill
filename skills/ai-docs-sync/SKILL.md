---
name: ai-docs-sync
description: "从已有项目代码与构建清单同步必要的 AI 文档草案，优先补齐只有代码的项目；初始化、历史迁移和类型校验使用各自独立 Skill。"
---

# 从代码同步最小文档

初始化已完成而缺少业务文档时，优先补齐代码结构与开发入口。公共规则和类型模板从同版本 [ai-docs-check](../ai-docs-check/SKILL.md) 的 `assets/templates/` 按需读取；项目配置仍是 `docs/.ai-docs.json`。

## 脚本负责的事实

```bash
python3 /ai-docs-sync/scripts/sync.py --target /项目 --scan
python3 /ai-docs-sync/scripts/sync.py --target /项目 --plan-file /tmp/sync-plan.json
python3 /ai-docs-sync/scripts/sync.py --target /项目 --apply --plan-file /tmp/sync-plan.json
```

脚本只读本地代码路径与支持的清单字段，创建 `architecture-overview` 和 `development-guide` 两个 draft；有源事实才建文档。未知运行时或命令明确保留，清单中的脚本不会执行，不填核验日期或批准。Python 3.10 下 TOML 只登记定位，3.11+ 可提取字段。

生成器按类型渲染 meta，写入前校验，应用后比较结构基线；来源哈希变化使旧计划失效。重复同步无变化时不写入；工具生成且未被编辑的草案可以刷新，人工修改或已有同类对象保留并报告，由 AI 在原对象上补充。同步不隐式初始化，也不生成代码清单无法直接证实的产品规范。

用户已明确提供概况时，可在预览命令同时传入 `--overview-title` 与 `--overview-summary`，额外建立项目总纲 draft；应用仍读取同一计划。已有同主题资料先阅读复用，历史正文需要整理时转 [ai-docs-migrate](../ai-docs-migrate/SKILL.md)。

## AI 负责的判断

按任务阅读必要代码，确认模块职责、业务边界、数据流、入口、约束和命令副作用。把清单观察、代码证明的现状与产品目标分开，不能把目录树当作完整架构。确认后的内容更新已有对象，再用 ai-docs-check 校验候选 meta 与目标结构。正式命令登记在项目配置；实际执行结果才构成核验依据。

默认使用相邻 ai-docs-check 公共资源，支持 `--source /匹配资源根`；资源缺失或协议版本不一致时停止对应操作。计划保存在目标之外，`--apply` 必须使用已保存计划；同步失败回滚本次写入。脚本产出是待完善草案，严格就绪需另行核验。
