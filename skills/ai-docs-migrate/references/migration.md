# 独立文档迁移

先通过 `ai-docs-init` 初始化最小 AI 文档系统。初始化只提供协议入口和配置；迁移只处理用户已指定或已授权的旧文档范围。AI 负责判断对象边界、类型、事实与适用状态，脚本负责盘点、布局、复制完整内容、修复引用、元数据校验、预览和受保护应用。

## 只读盘点

```sh
python3 "<ai-docs-migrate>/scripts/migrate.py" --target "/absolute/project" --scan
```

`--inventory` 是 `--scan` 的兼容别名。默认共享资源来自同级 `ai-docs-check/assets/templates`，不复制到目标项目。开发或不同安装布局可通过 `--source "/absolute/resources"` 显式指定匹配版本的资源根目录。盘点可在初始化之前运行，只报告 Markdown 的真实路径、内容哈希、已识别的 meta 和锚点，不按标题猜测业务类型。

盘点与入链修复覆盖整个仓库的 Markdown，包含源码旁 README 与非 `docs/` 的旧说明；跳过 `.git`、`node_modules`、`.venv`、`venv`、`__pycache__`、`.cache`、`.next`、`dist`、`build` 等依赖、缓存和构建产物。这些范围不属于扫描或迁移输入。

## 显式映射

用仓库相对路径指定旧文档，并显式选择协议文档类型、稳定 ID、标题和 slug。根与 docs 的 README/AGENTS 是最小系统协议入口，不能作为整文件迁移输入；这些入口已有业务内容时，AI 在明确授权范围内提取独立对象并保留托管区块，再交给脚本迁移。每个旧文件必须对应一个独立对象；脚本不把多个对象自动拆开，也不把多份旧文档自动合并。

```json
{
  "documents": [
    {
      "source": "legacy/architecture.md",
      "type": "architecture-overview",
      "id": "ARCH-OVERVIEW",
      "title": "架构总览",
      "slug": "architecture-overview"
    },
    {
      "source": "legacy/decision-001.md",
      "type": "adr",
      "id": "ADR-001",
      "title": "存储方案决策",
      "slug": "storage-decision"
    }
  ]
}
```

集合类型来自共享 `collections.json`，目标位置由注册表决定。前两条聚合存储，每条有独立 `yaml doc-meta`；第三条展开所有原条目，并修复旧集合的稳定锚点、章节锚点和入链；已经展开的集合继续使用目录。

三个常用单例直接写独立文件，不经过集合计数：

| 类型 | 默认位置 |
|---|---|
| `project-overview` | `docs/project/overview.md` |
| `architecture-overview` | `docs/engineering/architecture/overview.md` |
| `development-guide` | `docs/engineering/development/quickstart.md` |

这些默认位置由对应共享 reference 模板推导。单例可提供 `destination` 覆盖为安全的 `docs/` 业务 Markdown 路径，不能覆盖协议入口、配置或 `_` 系统目录。原文件恰好已在目标单例路径时可原地适配；目标已有另一份文件时阻断，先由 AI 判断是否同一对象及如何合并。

已有平面 JSON 标量 meta 的 ID、type、status、slug、批准、核验、范围和扩展字段保留；映射不得改变已有身份或事实。未知的类型专属字段与不兼容旧格式会明确报错，不以删除字段消除问题。没有 meta 的旧文档使用 `status: draft`，未知普通字段补 `null`，authority 来自对应文档类型。不能因迁移默认标记 `active`、已批准或已核验。

`meta` 仅可补充原文缺少的已确认事实，不能覆盖已有值。`task` 的 `kind`、`state` 和 `release` 的 `release_state` 必须满足枚举；没有旧事实时需要显式确认后填写，脚本不猜测“功能”“待办”或“计划发布”。例如：

```json
{
  "source": "legacy/cleanup.md",
  "type": "task",
  "id": "TASK-001",
  "title": "清理缓存目录",
  "slug": "cleanup-cache",
  "meta": {"kind": "chore", "state": "queued"}
}
```

## 预览与应用同一计划

```sh
python3 "<ai-docs-migrate>/scripts/migrate.py" \
  --target "/absolute/project" \
  --mapping "/private/tmp/migration-mapping.json" \
  --dry-run --plan-file "/private/tmp/migration-plan.json"

python3 "<ai-docs-migrate>/scripts/migrate.py" \
  --target "/absolute/project" \
  --apply --plan-file "/private/tmp/migration-plan.json"
```

计划文件必须位于目标仓库之外，脚本拒绝覆盖已有计划。预览仅写指定计划文件和临时校验目录，不写目标仓库。JSON 含完整输入映射、所有文件的最终内容、操作与哈希、旧新路径及锚点映射、真实检查基线与候选结果；审阅完整计划后在已授权范围内应用。`--apply` 不能同时提供新的 `--mapping`，修改范围需要重新生成计划。

每份生成文档先按类型校验 meta，再在临时树运行共享 `docctl.validate` 和整个仓库的普通 Markdown 本地引用检查。保留历史问题会在真实 baseline 中展示；新增错误使计划 `blocked`。迁移到新路径时仍然存在的缺失附件或引用也会明确阻断，不把旧缺陷隐藏成通过。正文充分性、批准真实性、语义分类和外部链接有效性仍需 AI 或人判断。

正文完整保留，仅适配 ATX 标题层级、注入稳定章节锚点、重定位相对引用。脚本修复普通内联链接、引用式链接、旧章节锚点、相对附件地址，以及根相对的 meta `*_ref`。附件保持原位置和原内容。旧正文替换为 `<!-- doc-redirect -->` 薄入口，不留第二份可编辑正文；原地适配的单例保留唯一文件。已有 `_generated/indexes` 或 `_generated/catalog` 时，在同一计划内重新生成索引及机器目录，并保护每个生成文件的原哈希。

应用使用共享 `docs/.docctl.lock`。它核对目标与资源版本、整个 Markdown/config/生成目录快照、共享资源哈希和计划内容，再从当前原始资料重建计划；即使篡改者重算计划哈希，也不能插入与当前显式映射不一致的写入。写入前再次核对单文件哈希，创建目标使用排他写入，不覆盖同名文件。异常时恢复已修改文件、权限和创建的目录；若其他执行者在写入后再次改变文件，回滚不覆盖该修改，并明确报告未恢复的路径。进程被直接终止或机器断电时，保留计划与写入锁供人工检查，脚本不承诺跨崩溃事务恢复。

## 明确受限的输入

当前自动迁移只支持 UTF-8 Markdown、ATX `#` 标题，以及本协议的平面 `key: JSON 标量` meta。Setext 标题、Wiki 链接、未转义嵌套括号目的地址、需要重定位的本地 HTML `href/src`、多对象旧紧凑集合、任意 YAML 嵌套字段、符号链接路径和无法唯一映射的旧锚点会报错。先由 AI 在明确范围内保全事实并适配格式，再重新盘点；不要复制正文作为“已迁移”结果。

仓库外的入链、非 Markdown 文件内引用、被忽略目录内引用和上述不支持格式不在自动修复范围。需要保留的外部旧 URL 应由调用方记录并处理；旧薄入口只提供可发现的新位置。

退出码：`0` 表示盘点成功、计划可应用或应用成功；`1` 表示候选检查新增错误而受阻；`2` 表示输入、权限、格式、冲突或并发保护报错。只有 `status: applied` 表示应用成功；结构通过不表示项目已具备 strict 就绪条件。
