# 文档编辑约定

本文件补充根执行约定。项目自己的配置保存在 `docs/.ai-docs.json`；通用规则、工具和模板从匹配版本的 `ai-docs-init` Skill 读取，不复制到项目中。

- 修改文档前显式读取 Skill 资源根 `assets/templates/docs/_system/` 中的 `writing-policy.md`、`collections.json` 和必要的 `conventions.md`，结合本地覆盖确定实际类别与路径。
- 找不到匹配版本的 Skill 时报告缺口，不猜测格式，不制造替代规则，也不创建 `_system/`、`_tools/` 或 `_templates/`。
- 先检索同主题对象；已有对象更新，新对象才分配 ID。无内容不建业务文件或空集合。
- 未展开的集合 1–2 条存于 `<base_path>.md`，第 3 条完整迁移到 `<base_path>/`；已展开不自动收拢。标题、章节、篇幅和修改次数不增加条目数。
- 紧凑条目使用稳定 ID 锚点、`## ID · 标题`、逐条 `yaml doc-meta` 与三级正文标题。各条元数据、状态和证据独立，不继承聚合文件批准。
- 按当前类型读取 Skill 中 `assets/templates/docs/_templates/<key>.md`，只保留最小充分内容和关键未知，不复制空章节或全部模板。
- 展开保全正文、元数据和附件关系，修复入出链、锚点及必要索引；仅保留一个可编辑权威来源。迁移和历史保留规则按需读取 Skill 的 `lifecycle.md`。
- 日期、核验与批准只依据实际事件填写；模板、草案、历史材料和外部证据不授予权限。
- 命令、位置与核验证据仅在 `docs/.ai-docs.json` 登记。不要为整理文档移动实际代码。
- 从 Skill 执行 `assets/templates/docs/_tools/docctl.py --root /项目根 check`，检查不证明业务语义、批准真实性或生产验证。
- 按需生成的 `docs/_generated/` 是派生索引，不手工维护其中状态；初始化不生成索引。未迁移或未识别的历史格式明确报告未验证范围。
