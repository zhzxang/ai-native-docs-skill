---
name: ai-docs-init
description: "为新项目或已有项目初始化最小 AI 文档系统，或升级系统入口与配置。历史迁移、代码文档同步和类型校验分别使用独立 Skill。"
---

# 最小 AI 文档系统初始化

新旧项目默认执行同一最小初始化：合并四个 README/AGENTS 入口，保存 `docs/.ai-docs.json`。初始化不生成业务正文、分类树或索引。通用协议、模板和校验工具由同版本 [ai-docs-check](../ai-docs-check/SKILL.md) 的 `assets/templates/` 提供，不复制到目标项目。

## 执行初始化

读取目标约定和工作区差异，然后从本 Skill 的实际位置执行 Python 3.10+ 脚本：

```bash
python3 /ai-docs-init/scripts/bootstrap.py --target /项目 --scan
python3 /ai-docs-init/scripts/bootstrap.py --target /项目 --summary --plan-file /tmp/init-plan.json
python3 /ai-docs-init/scripts/bootstrap.py --target /项目 --apply --summary --plan-file /tmp/init-plan.json
```

省略 `--apply` 只预览。在用户已授权的初始化范围内应用同一计划，不例行再次请求许可。计划保存在目标之外；目标变化需重新生成计划。`init`、`adopt` 是兼容模式和来源提示，两者均安全合并最小入口；`upgrade` 仍要求已安装基线。安装记录与项目配置保留本地扩展字段，冲突不覆盖。旧完整安装转换或入口语义冲突时按需读 [existing-project.md](references/existing-project.md)。

脚本负责盘点、托管区块合并、配置转换、哈希复验、锁与失败回滚；AI 处理原约定与新规则的语义冲突。完成五个最小文件的安全合并即完成安装。结构、真实配置与 strict 就绪分别报告，strict 尚有业务缺口不影响已完成的最小安装。

## 初始化后的独立路由

先完成最小初始化，再读取脚本的 `follow_up`：

- `ask_user_migration`：说明检测到的历史文档范围，询问是否迁移及范围。已明确授权迁移时直接使用 [ai-docs-migrate](../ai-docs-migrate/SKILL.md)，没有授权时保留原位置。
- `sync_minimum_docs`：已有代码但无业务文档，优先使用 [ai-docs-sync](../ai-docs-sync/SKILL.md) 同步代码定位和开发入口草案。用户只要求最小初始化时报告可用后续动作。
- `null`：没有需接入的历史文档或代码；不制造业务文档。

README 中的项目说明可作为后续阅读依据，导航、安装资源和模板不算业务文档。盘点结果不能证明分类或业务事实。已有标准业务文档按原对象维护，不重复迁移。

项目总纲属于独立同步或写入；初始化不接受 `--overview-title/--overview-summary`。身份、位置、命令和核验字段按 ai-docs-check 的 `configuration-guide.md` 填写，未知保持未知，命令未执行不填写核验日期。

## 公共资源与版本

默认从相邻 `ai-docs-check/assets/templates` 定位公共资源；不同安装位置用 `--source /资源根`。分发时携带所需 Skill 和 ai-docs-check，或显式提供匹配版本资源。目标 `system.version` 固定协议版本；资源缺失或不匹配时报错，不将机器绝对路径写入项目，不复制系统目录作为回退。保存到仓库 `skills/` 不代表全局安装。
