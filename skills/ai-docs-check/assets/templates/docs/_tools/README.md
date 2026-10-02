# 文档工具与独立能力

Python 3.10+，仅标准库。通用工具、规则、类型schema与模板由 `ai-docs-check` Skill 提供；项目只保存入口、配置和按实际内容建立的正文。工具不执行项目命令，不联网，不批准文档。

## 独立执行入口

```bash
python3 /ai-docs-init/scripts/bootstrap.py --target /项目 --plan-file /tmp/init.json
python3 /ai-docs-init/scripts/bootstrap.py --target /项目 --apply --plan-file /tmp/init.json
python3 /ai-docs-sync/scripts/sync.py --target /项目 --plan-file /tmp/sync.json
python3 /ai-docs-sync/scripts/sync.py --target /项目 --apply --plan-file /tmp/sync.json
python3 /ai-docs-migrate/scripts/migrate.py --target /项目 --scan
python3 /ai-docs-check/scripts/check.py check-meta /tmp/candidate.md
python3 /ai-docs-check/scripts/check.py --root /项目 check
python3 /ai-docs-check/scripts/check.py --root /项目 check --strict
```

初始化对新旧项目都只合并四个入口与项目配置；总纲生成、代码同步和历史迁移独立执行。历史迁移需用户明确范围；仅有代码时优先同步架构定位和开发入口草案。完整工具参数与映射见对应 Skill。

各动作默认定位相邻 ai-docs-check 的 `assets/templates`，可用 `--source /资源根`；docctl 使用 `--resources /资源根`。资源版本必须匹配目标配置，缺失时失败，不在项目创建回退目录。

## 类型校验与写入

`check-meta` 独立于项目安装，可检查多个暂存文件。front matter 和紧凑 `yaml doc-meta` 共用 [meta-schemas.json](../_system/meta-schemas.json)，校验 type、通用和专属字段、必填键、nullable、枚举、日期及生效批准。未知扩展标量保留并提示，混用类型专属字段失败。模板维护用 `--allow-template` 显式放行模板占位符。

生成或改写文档后先校验候选 meta，再写入并检查项目结构。`new`、sync 和 migrate 的脚本执行写入前类型校验；`check` 复用同一schema。完整结构检查还验证 ID、位置、集合阈值、唯一正文和本地引用；strict 增加真实配置和核验就绪。历史无 meta 的普通 Markdown 仍需单独盘点，结构通过不证明分类或业务事实。

```bash
python3 /ai-docs-check/scripts/check.py --root /项目 new feature FEAT-001 subscription --title "订阅功能"
python3 /ai-docs-check/scripts/check.py --root /项目 new task TASK-001 investigate --title "调查订阅问题" --kind bug
python3 /ai-docs-check/scripts/check.py --root /项目 find --type task --kind bug --state queued
python3 /ai-docs-check/scripts/check.py --root /项目 route billing
python3 /ai-docs-check/scripts/check.py --root /项目 index
```

先检索已有同主题对象，再创建条目；按需读写入协议和类型模板。未展开集合1–2条保存紧凑文件，第3条完整展开并修复引用；已展开不收拢。并发写入使用项目文档锁，失败回滚本次改动，派生索引按需生成。

## 工具维护

公共规则、类型模板和运行工具直接维护在 `ai-docs-check/assets/templates/`，这是各 Skill 共用的唯一资源源码，随 Skill 原样分发。Skill 和协议回归测试集中在仓库根的 `tests/`。修改后从仓库根执行：

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p 'test_*.py'
python3 skills/ai-docs-check/scripts/check.py --root skills/ai-docs-check/assets/templates check
```

测试只验证文档系统本身，不代表项目业务测试通过。
