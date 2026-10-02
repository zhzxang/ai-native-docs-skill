# 自适应文档架构

文档系统的最小职责是让后续知识有稳定入口、身份、定位和验证方式。安装系统、描述代码、迁移旧知识和验证格式是四种不同动作，不能互相隐含。完整分类是内容归属词典，实际文件由已存在的内容决定，模板不是项目初始化清单。

## 四个独立 Skill

| 能力 | Skill | 确定性脚本职责 | AI 判断 |
|---|---|---|---|
| 最小初始化和升级 | [ai-docs-init](../skills/ai-docs-init/SKILL.md) | 盘点、合并四个入口、保存配置、版本和基线 | 原约定冲突和无法直接映射的项目定制 |
| 从代码同步必要文档 | [ai-docs-sync](../skills/ai-docs-sync/SKILL.md) | 代码/清单证据、来源哈希、草案渲染与安全刷新 | 模块职责、数据流、产品目标、命令含义 |
| 历史文档迁移 | [ai-docs-migrate](../skills/ai-docs-migrate/SKILL.md) | 显式映射转换、全文/meta保全、布局和链接修复 | 分类、独立对象边界、状态和唯一来源 |
| 按类型校验 | [ai-docs-check](../skills/ai-docs-check/SKILL.md) | meta schema、ID、布局、配置与本地引用检查 | 业务语义、批准真实性、验证是否充分 |

新旧项目都先执行同一最小初始化。初始化完成后，历史文档触发询问是否迁移及范围；只有代码而无业务文档时优先同步代码结构和开发入口。已有标准文档按原对象维护，空项目不生成业务文档。脚本只输出后续路由，独立动作由对应 Skill 在任务范围内执行。

`init/adopt` 是兼容提示，不再把“有代码”当作阻止最小安装的条件。`upgrade` 仍要求实际安装基线。所有计划默认预览、保存在目标之外，应用时验证同一计划和当前来源；哈希失配重新预览，失败回滚本次改动。

## 最小项目与公共资源

```text
目标项目/
├── README.md                    # 保留项目内容并合并托管区块
├── AGENTS.md
└── docs/
    ├── README.md
    ├── AGENTS.md
    └── .ai-docs.json             # 唯一项目配置、资源版本和安装基线
```

初始化只处理上述五个文件，不创建总纲、业务分类树、空集合或派生索引，也不复制 `_system/`、`_tools/`、`_templates/`。用户明确提供的项目概况由同步或日常写入独立创建 draft 总纲。

```text
本仓库/
├── tests/                       # Skill 和协议回归测试
└── skills/
    ├── ai-docs-init/scripts/bootstrap.py
    ├── ai-docs-sync/scripts/sync.py
    ├── ai-docs-migrate/scripts/migrate.py
    └── ai-docs-check/
        ├── scripts/check.py
        └── assets/templates/    # 唯一协议、入口、类型模板与运行工具源码
```

其他 Skill 默认读取相邻 ai-docs-check 公共资源，也支持 `--source /资源根`；校验工具支持 `--resources`。公共数据依赖不会隐式执行另一项能力。分发时复制所需动作 Skill 和 ai-docs-check，或提供同版本资源；项目不记录机器绝对路径。资源缺失或 `system.version` 不匹配时报错，不自动复制回退。保存到仓库不代表全局安装。

公共资源直接在 `skills/ai-docs-check/assets/templates/` 维护，随 Skill 原样分发，不再保留根目录 `templates/` 或复制构建层。该目录只携带运行工具、协议和实际类型模板，Skill 和协议回归测试集中在 `tests/`。集合分类说明由 `collections.json` 统一维护，参考目录不重复展开分类 README；结构检查和回归测试负责验证维护结果。验证记录位于 [validation.md](validation.md)。

## 从代码同步

确定性生成器只记录可观察的代码位置、构建清单、运行时声明和开发入口，生成 `architecture-overview`、`development-guide` 两个草案。来源 SHA-256 固定适用快照，命令不执行，核验与批准保持 null。需要阅读代码才能判断的职责、数据流和业务目标交给 AI，目录盘点不能代替架构分析。

来源或文档变化使计划失效；重复执行无差异时不写文件。未被人工修改的工具草案可以刷新，人工改动和其他位置的既有同类对象保留，由 AI 更新原对象。同步不隐式初始化，也不把安装或生成日期当核验日期。

## 迁移与集合状态

历史迁移先形成显式旧路径到 type/ID/slug 的映射。脚本保留全文、元数据、批准事实、相对附件关系和旧锚点，修复仓库 Markdown 入出链；旧文件可保留薄跳转而不保留第二份正文。无法可靠解析或映射的内容阻断该项并报告，不能用摘要替代原文。单例总纲、架构总览与开发指南直接迁入单篇路径，集合遵守下面的状态机。

| 内容情况 | 实际结构 | 动作 |
|---|---|---|
| 没有条目 | 没有业务文件或目录 | 不预建空壳 |
| 第 1 条 | `<base_path>.md` | 创建紧凑文件 |
| 第 2 条 | 同一紧凑文件 | 增加独立 ID、meta 和正文 |
| 第 3 条 | `<base_path>/ID-slug.md` | 完整展开并修复引用 |
| 已展开 | 保持目录 | 不自动收拢 |

条目是能够独立命名、检索和维护的对象；标题、篇幅和修改次数不计数。每条有独立状态和批准，不继承集合公共状态。逻辑路由按 collection key 解析实际布局，派生索引仅在需要时生成。

## 类型验证与事实边界

`skills/ai-docs-check/assets/templates/docs/_system/meta-schemas.json` 是类型 meta 的唯一机器定义，包含通用字段和72种类型的专属字段。front matter 与紧凑 doc-meta 都使用扁平 `key: JSON标量`，校验 required、类型、nullable、枚举、日期、authority、核验配对与生效批准；未知扁平扩展保留并提示，混用已知类型专属字段报错。

`check-meta` 可校验项目外候选文件，生成/迁移写入前执行；`new` 和 `check` 复用同一校验。`check` 进一步验证唯一 ID、布局和本地引用，`check --strict` 增加真实配置与核验就绪。结构通过不证明分类、业务行为或批准真实性，历史无 meta 的普通文档仍需单独盘点。安装完成、结构正确和严格就绪分别报告。

## 开发验证

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p 'test_*.py'
python3 skills/ai-docs-check/scripts/check.py --root skills/ai-docs-check/assets/templates check
```

上述检查验证文档系统自身，不代表目标项目业务测试通过。旧完整安装升级仍保留真实所有权、当地修改与引用保护，详细过程由初始化 Skill 的参考说明维护。
