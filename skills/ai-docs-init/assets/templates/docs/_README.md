# 文档入口

先读取根执行约定和 [文档编辑约定](AGENTS.md)。项目配置统一在 `docs/.ai-docs.json`；匹配版本的 `ai-docs-init` Skill 提供通用规则、工具和模板。

## 按任务定位

从 Skill 执行 `assets/templates/docs/_tools/docctl.py --root /项目根 route <id>`。常用路由为 `orientation`、`feature`、`bug`、`ui`、`api`、`database`、`billing`、`release`、`incident`、`security` 与 `docs`；完整路由按需读取 Skill 默认资源和项目覆盖。

使用 `find --type <类别> --query <关键词>` 查找相关条目，命中紧凑集合时按条目锚点读取。已有对象优先更新，新对象才创建；业务文件与目录按内容需要形成，不预建领域导航。

## 规则与检查

所有写入先显式读取 Skill 的 `assets/templates/docs/_system/writing-policy.md` 与 `collections.json`，再按当前类型读取模板。未展开集合 1–2 条保存于单文件，第 3 条展开；已展开不收拢。

工具由 Skill 提供，执行时通过 `--root` 指定本项目。`check` 核验可识别结构和引用；`check --strict` 进一步核验真实配置就绪。模板、结构通过和安装完成都不代表批准、上线或业务验证完成。

只读取当前任务需要的规则、证据和条目，不默认加载完整模板库、派生索引或历史归档。尚未迁移的旧资料保留原位置，明确其适用范围和未验证项。
