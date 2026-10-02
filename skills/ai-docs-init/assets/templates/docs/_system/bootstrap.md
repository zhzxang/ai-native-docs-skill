# 轻量初始化与迁移

## 安装边界

初始化统一使用轻量模式。目标项目只新增或合并根 `AGENTS.md`、根 `README.md`、`docs/AGENTS.md`、`docs/README.md`，并创建 `docs/.ai-docs.json`。不复制 `_system/`、`_tools/`、`_templates/`，不提供完整安装选项，不预建业务分类或派生索引。

通用资源保存在 `ai-docs-init` Skill 的 `assets/templates/`；本仓库唯一模板源码仍是 `templates/`。源中的 `_AGENTS.md` 与 `_README.md` 仅是入口模板，安装时重命名并通过托管区块合并。

## 盘点、计划与应用

先读取目标约定，盘点已有文档、配置和引用，再从已安装或显式提供的 Skill 执行：

```bash
python3 /Skill目录/scripts/bootstrap.py --target /目标项目 --scan
python3 /Skill目录/scripts/bootstrap.py --target /目标项目 --mode auto --summary --plan-file /tmp/ai-docs-plan.json
python3 /Skill目录/scripts/bootstrap.py --target /目标项目 --apply --summary --plan-file /tmp/ai-docs-plan.json
```

`auto` 选择 `init`、`adopt` 或 `upgrade`，它们都采用轻量布局。省略 `--apply` 只预览；保存计划应用前核对目标哈希。保留原入口正文和本地修改，不用托管标记掩盖执行约定的语义冲突。

也可从本仓库运行 `python3 templates/docs/_tools/init_docs.py --target /目标项目 --mode auto`，添加 `--apply` 才应用。工具不运行登记的项目命令。

## 项目配置与确认内容

`docs/.ai-docs.json` 是唯一项目配置：保存依赖版本、项目身份、代码与外部来源位置、命令、本地覆盖及安装状态。未知身份保留 `null`，位置和命令只按已知内容登记；不复制全部空登记项。配置暂不拆分，字段语义见 [configuration-guide.md](configuration-guide.md)。

用户确认项目名称和概况后，在生成计划时传入 `--overview-title` 与 `--overview-summary`，才创建 draft 总纲 `docs/project/overview.md`。已有同主题文档先复用或迁移，不造空总纲；安装不填写批准、核验时间或成功结果。

## 已有项目与旧完整安装

普通老项目先接入后续写入规则，历史正文按用户明确范围迁移，保留身份、事实、证据、附件与引用。旧完整安装的项目配置迁入统一配置，项目定制分类和路由保留为本地覆盖；原系统资产根据实际所有权及基线哈希处理。无法证明归属或有本地修改的材料保留并报告，不批量删除目录。

配置迁移、入口合并、规则资源版本需一起核验。历史格式未知或本地修改冲突未解决时，准确报告保留范围；不得宣称全集已迁移、安装完整或严格就绪。

## 外部资源与检查

根入口必须显式引导读取 Skill，不依赖自动触发。`system.version` 固定协议资源版本；找不到匹配版本时报告缺口，不记录开发者机器的绝对路径，也不复制系统目录作为回退。

```bash
python3 /Skill目录/assets/templates/docs/_tools/docctl.py --root /目标项目 check
python3 /Skill目录/assets/templates/docs/_tools/docctl.py --root /目标项目 check --strict
python3 /Skill目录/assets/templates/docs/_tools/docctl.py --root /目标项目 route feature
```

结构通过与严格就绪分别报告。初始化因缺少核心事实或真实命令导致 strict 失败是预期缺口，不能降低要求来制造通过。团队、其他机器和 CI 使用同一版本的 Skill 资源，工具只输出和修改目标项目的业务文档与必要派生物。
