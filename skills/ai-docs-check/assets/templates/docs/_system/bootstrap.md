# 最小初始化与独立后续能力

## 安装边界

新旧项目默认执行同一最小初始化：合并根 `AGENTS.md`、根 `README.md`、`docs/AGENTS.md`、`docs/README.md`，保存 `docs/.ai-docs.json`。不生成业务正文、分类树或索引，不复制系统目录，不提供完整安装选项。

公共规则、模板和类型schema直接维护在 `ai-docs-check/assets/templates/`，这里是唯一资源源码，随 Skill 一起分发。动作分为 `ai-docs-init`、`ai-docs-sync`、`ai-docs-migrate` 和 `ai-docs-check`，各有独立入口。

## 盘点、计划与应用

```bash
python3 /ai-docs-init/scripts/bootstrap.py --target /项目 --scan
python3 /ai-docs-init/scripts/bootstrap.py --target /项目 --summary --plan-file /tmp/init-plan.json
python3 /ai-docs-init/scripts/bootstrap.py --target /项目 --apply --summary --plan-file /tmp/init-plan.json
```

`init/adopt` 都安全合并最小入口，`auto` 返回来源提示，`upgrade` 要求实际安装基线。省略 `--apply` 只预览，目标变化重新盘点。已有正文、本地定制和未知扩展保留，语义冲突交给 AI 裁决，不用托管标记掩盖矛盾。

资源默认来自相邻 ai-docs-check，独立部署可用 `--source /匹配资源根`。目标不记录机器绝对路径；缺少匹配协议资源时报错，不复制资源作为回退。

## 初始化后的路由

先完成最小初始化，再处理 `follow_up`：历史文档为 `ask_user_migration`，询问用户是否迁移及范围，已有授权直接执行；代码且无业务文档为 `sync_minimum_docs`，优先同步必要代码文档；空项目或只有标准业务文档为 null。README 的实际说明可作为证据，导航和模板不算业务文档。

```bash
python3 /ai-docs-sync/scripts/sync.py --target /项目 --plan-file /tmp/sync-plan.json
python3 /ai-docs-sync/scripts/sync.py --target /项目 --apply --plan-file /tmp/sync-plan.json
python3 /ai-docs-migrate/scripts/migrate.py --target /项目 --scan
```

初始化脚本不执行后续动作，不接受总纲参数。用户已提供概况时，独立 sync 预览命令可带 `--overview-title` 与 `--overview-summary`；草案不代表核验或批准。历史迁移的显式分类映射和工具参数由 ai-docs-migrate 参考维护。

## 配置、升级与校验

`docs/.ai-docs.json` 保存身份、位置、命令、就绪、覆盖和安装状态，不登记全部空项目。字段语义见 [configuration-guide.md](configuration-guide.md)。旧完整安装升级先迁入真实配置与定制；清理只处理可证明属于旧安装且未修改、无保留引用的资源，归属不明或有修改的材料保留报告。

```bash
python3 /ai-docs-check/scripts/check.py check-meta /tmp/candidate.md
python3 /ai-docs-check/scripts/check.py --root /项目 check
python3 /ai-docs-check/scripts/check.py --root /项目 check --strict
```

安装、结构和 strict 就绪分别报告。最小安装缺少真实业务事实时 strict 不通过是预期缺口，不能降低要求制造就绪。工具不运行项目登记命令，结构通过不证明历史全集、业务语义或生产行为已验证。
