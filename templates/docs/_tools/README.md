# Skill 中的文档工具

需要 Python 3.10+，只使用标准库。工具、通用规则和集中模板保存在 Skill 中，不复制到目标项目，不执行登记的项目命令，也不批准文档或改变生产权限。

## 初始化

从本仓库或整个 Skill 的副本使用增量初始化；新项目、接入和升级都创建轻量布局。

```bash
python3 templates/docs/_tools/init_docs.py --target /目标项目 --mode auto
python3 templates/docs/_tools/init_docs.py --target /目标项目 --mode auto --apply
```

目标只保存四个 README/AGENTS 入口与 `docs/.ai-docs.json`，明确提供总纲标题摘要时再增加 draft 总纲。项目配置和业务内容属于项目，通用资源属于 Skill；没有完整安装模式。计划、托管区块、锁、哈希复验与回滚保护已有内容。

Skill 的 `scripts/bootstrap.py` 另提供 `--scan`、`--summary` 和 `--plan-file` 保存及应用同一计划，使用方式见 [初始化指南](../_system/bootstrap.md)。

## 从 Skill 操作目标项目

```bash
python3 /Skill目录/assets/templates/docs/_tools/docctl.py --root /目标项目 check
python3 /Skill目录/assets/templates/docs/_tools/docctl.py --root /目标项目 check --strict
python3 /Skill目录/assets/templates/docs/_tools/docctl.py --root /目标项目 new feature FEAT-001 subscription --title "订阅功能"
python3 /Skill目录/assets/templates/docs/_tools/docctl.py --root /目标项目 new task TASK-001 investigate --title "调查订阅问题" --kind bug
python3 /Skill目录/assets/templates/docs/_tools/docctl.py --root /目标项目 find --type task --kind bug --state queued
python3 /Skill目录/assets/templates/docs/_tools/docctl.py --root /目标项目 route billing
python3 /Skill目录/assets/templates/docs/_tools/docctl.py --root /目标项目 index
```

工具通过自身位置解析 Skill 资源，可用全局参数 `--resources /资源根` 显式指定 `assets/templates` 或来源仓库 `templates`。项目配置记录版本和覆盖，不记录机器绝对路径；资源缺失或版本不匹配时失败，不在项目创建资源回退目录。

## 写入、展开与门禁

写入前按需读取 Skill 的 `docs/_system/writing-policy.md`、分类注册表与对应 `docs/_templates/<key>.md`，查找已有同主题条目后才 `new`。新草案不填写核验、批准或成功事实；填写最小充分内容并移除不适用空章节。

1–2 条保存于 `<base_path>.md`，第 3 条迁移为目录，每条 front matter 文件保留 ID、状态、范围和证据；修复普通 Markdown 入链、出链和锚点，必要时按需重建索引。已展开不自动收拢。并发写入持有目标项目的锁；不修改 Skill 资源，失败回滚本次变更。

`check` 检查可识别元数据、位置、条目数、引用和单一正文来源；`check --strict` 还检查核心事实、必需位置和已核验命令。未识别旧格式、业务语义、批准真实性或外部权限不能由结构通过证明，需另行报告。索引按需生成在目标 `docs/_generated/`，初始化不创建。

## 验证工具自身

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s templates/docs/_tools -p 'test_*.py' -v
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s skills/ai-docs-init/scripts -p 'test_*.py' -v
```

这是文档系统测试，不代表项目业务测试通过。
