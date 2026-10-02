---
name: ai-docs-init
description: "为新项目初始化、为已有项目接入或迁移、升级轻量 AI 文档系统。建立或更新这套文档体系时使用；日常文档写入由项目入口引导按需读取 Skill 资源。"
---

# 轻量 AI 文档系统初始化

初始化只合并四个 README/AGENTS 入口并保存 `docs/.ai-docs.json`，确认内容后才创建业务文档。通用规则、工具和模板留在本 Skill 的 `assets/templates/`，不在目标项目创建 `_system/`、`_tools/` 或 `_templates/`，没有完整安装选项。

## 模式与资源

`auto` 根据盘点选择 `init`（新项目）、`adopt`（已有项目接入）或 `upgrade`（已安装项目升级）；三种模式都是轻量布局。老项目、历史迁移、旧完整安装或本地冲突先读 [existing-project.md](references/existing-project.md)。模式名称不授予覆盖原内容的权限。

通过本 Skill 的实际位置定位脚本和资源，支持复制整个目录后独立使用。`docs/.ai-docs.json` 的 `system.version` 固定资源版本；找不到匹配资源时报告缺口，停止依赖它的写入或检查，不猜测格式或复制资源作为回退。入口必须显式引导日常写入读取 Skill，不依赖自动触发，不把某台机器绝对路径写入项目。保存在项目 `skills/` 中不代表已全局安装。

## 执行

1. 确认目标根，读取适用约定、工作区差异和已有资料。使用 Python 3.10+ 从本 Skill 执行：

   ```bash
   python3 /Skill目录/scripts/bootstrap.py --target /目标项目 --scan
   python3 /Skill目录/scripts/bootstrap.py --target /目标项目 --mode auto --summary --plan-file /tmp/ai-docs-plan.json
   ```

   盘点不替代语义阅读。摘要列出计数、更新与冲突，完整计划保存在目标之外；按需审阅实际原文与变更。省略 `--apply` 只预览，不能报告为已安装。
2. 在已授权范围内应用同一计划，无需例行重新请求许可：

   ```bash
   python3 /Skill目录/scripts/bootstrap.py --target /目标项目 --apply --summary --plan-file /tmp/ai-docs-plan.json
   ```

   目标变化后重新盘点并生成计划。保留入口原文、项目定制和历史事实；语义冲突先保留并继续兼容工作，需要裁决时说明具体冲突。用户确认项目名称概况后可在生成计划时同时传入 `--overview-title` 与 `--overview-summary`，仅创建 draft 总纲；已有同主题对象先复用。
3. 按 `assets/templates/docs/_system/configuration-guide.md` 填写目标 `docs/.ai-docs.json`。它是唯一项目配置，按字段区分身份、位置、命令、就绪、本地覆盖和工具管理的 `installation`，初始化不拆分文件，不登记全部空位置或空命令。未知保持未知，命令未执行不填核验日期，不把结构通过当作业务验证。
4. `adopt` 先接入后续写入，再按用户明确范围迁移历史。保留 ID、完整正文、状态、依据、附件和引用，最终一个对象只有一个可编辑正文来源；未迁移和未识别的范围准确报告。旧完整安装转换先保全配置和本地修改，流程见参考。
5. 从本 Skill 的工具验证目标：

   ```bash
   python3 /Skill目录/assets/templates/docs/_tools/docctl.py --root /目标项目 check
   python3 /Skill目录/assets/templates/docs/_tools/docctl.py --root /目标项目 check --strict
   ```

   工具只处理目标业务文档、配置与按需派生物，不运行登记命令。对照基线报告安装、真实配置和严格就绪三个状态；初始化 strict 有真实缺口时保留要求，不降低门禁制造通过。工具、旧格式或资源不兼容时报告实际未执行或未验证范围。

## 不变规则

- 逻辑分类固定，未使用模板不实例化。未展开集合 1–2 条在 `<base_path>.md`，第 3 条展开为 `<base_path>/<ID>-<slug>.md`；已展开不收拢。标题、篇幅、修改次数不计作条目。
- 已有对象优先更新；迁移保全身份与事实，修复入链、出链、锚点及必要索引。模板、安装、草案与外部证据不授予批准或生产权限。
- `installation` 记录入口托管区块的版本和基线，不登记业务条目数量，也不证明配置或业务就绪。升级保留用户字段，不伪造基线绕过本地修改保护。
- `operating_mode` 保持 `bootstrap`，直到实际事实、验证和交接满足要求。完成声明包含实际范围、冲突、未迁移项、检查证据和下一步。

## 模板维护

来源仓库 `templates/` 是唯一模板源码，`assets/templates/` 是生成资源，不手工维护第二份协议。改动后从来源仓库根执行：

```bash
python3 skills/ai-docs-init/scripts/build_assets.py
python3 skills/ai-docs-init/scripts/build_assets.py --check
```

日常写入从项目入口按需读取这里的规则和模板；项目配置与真实业务内容始终属于目标项目。
