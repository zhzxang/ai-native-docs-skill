---
name: ai-docs-init
description: "为新项目初始化、为已有项目接入或迁移、升级按需展开的 AI 文档系统。用户希望建立这套文档体系或更新其安装时使用；日常功能开发与普通文档回写遵守项目内协议。"
---

# AI 文档系统初始化

把项目接入“逻辑分类固定、文件按需创建、第 3 个独立条目展开”的文档系统。安装只建立入口、规则、配置、工具和集中模板；项目事实有确认内容后才写入。日常写入由目标项目的 `AGENTS.md`、`docs/AGENTS.md` 和 `docs/_system/writing-policy.md` 承担。

客户端是否自动发现当前 Skill 目录取决于其实际配置；也可以显式引用本 `SKILL.md` 使用。不要把保存到项目目录误报为已全局安装。

## 选择模式

| 模式 | 适用情况 | 结果 |
|---|---|---|
| `init` | 尚未建立文档体系的新项目 | 最小安装，按需建立已确认的项目事实 |
| `adopt` | 有代码、文档或执行约定，尚未完整接入本系统 | 保留原内容，增量合并入口，配置定位；历史迁移按明确范围执行 |
| `upgrade` | 已安装本系统 | 更新兼容的系统资产，保留配置、事实和本地定制 |

默认 `auto` 由盘点选择模式。先核验结果；存在旧版系统但没有安装清单时，读取 [existing-project.md](references/existing-project.md) 的无清单升级流程。不要把模式名称视为覆盖已有内容的授权。

## 执行

1. 确认目标项目根目录。读取适用的项目与局部执行约定，检查分支和工作区差异，盘点已有入口、代码配置、文档和系统版本。已有项目、历史迁移、冲突或本地定制时，先读 [existing-project.md](references/existing-project.md)。
2. 从本 Skill 所在目录定位 `scripts/bootstrap.py`，使用 Python 3.10 或更高版本。它通过自身路径读取打包模板，可从任意工作目录运行，也可单独复制整个 Skill 后使用。

   ```bash
   python3 /绝对路径/ai-docs-init/scripts/bootstrap.py --target /目标项目 --scan
   python3 /绝对路径/ai-docs-init/scripts/bootstrap.py --target /目标项目 --mode auto --summary --plan-file /tmp/ai-docs-plan.json
   ```

   `--scan` 只盘点；省略 `--apply` 只生成增量计划。`--summary` 返回创建计数、更新路径、保留计数和完整冲突，避免大量资产哈希占满上下文；`--plan-file` 仍保存完整变更快照。按摘要定位需审阅的原文件与计划中的实际变更，计划不能报告为已安装。脚本不运行项目登记命令，也不自动完成历史文档语义迁移。
3. 在用户已授权的范围内应用可兼容的增量变更，无需例行重新请求许可。

   ```bash
   python3 /绝对路径/ai-docs-init/scripts/bootstrap.py --target /目标项目 --apply --summary --plan-file /tmp/ai-docs-plan.json
   ```

   应用保存计划前会检查目标哈希；目标已变化时重新盘点、生成并审阅计划，不绕过过期保护。不提供 `--plan-file` 时，`--apply` 当场生成并应用计划，适用于已明确的小范围工作。

   用户已确认项目名称和概况时，可在生成计划时同时传入 `--overview-title "项目名称" --overview-summary "已确认概况"`，按需创建 draft 总纲。已有同主题文档先复用或迁移；不要另造空总纲。语义冲突先保留原文件，继续独立且兼容的工作；需要用户裁决时说明具体冲突与备选结果，不因冲突擅自覆盖。
4. 按目标项目 `docs/_system/configuration-guide.md` 填写 `project-map.json` 和 `commands.json`：登记真实位置、真实命令、环境、副作用及证据。未知保持未知，不适用须有理由。检查文件存在不代表命令已执行；不猜测启动方式、核验日期、批准或预授权。只在实际核验后记录 `verified_at`。
5. 接入协议与历史迁移分开交付。`adopt` 先让后续写入遵守新规则，再按用户明确的领域、任务或全集范围迁移旧文档。迁移前核验同主题对象，保留稳定 ID、正文、状态、历史、证据、附件和引用；具体做法见 [existing-project.md](references/existing-project.md)。
6. 使用目标项目安装的工具检查最终状态：

   ```bash
   python3 /目标项目/docs/_tools/docctl.py --root /目标项目 check
   python3 /目标项目/docs/_tools/docctl.py --root /目标项目 check --strict
   ```

   结合基线区分已有缺陷和本次引入的问题。若安装被冲突阻断或工具不兼容，不盲目运行受阻的检查，也不把未执行写为通过。保留可审查结果并报告缺口。

## 不变规则与交付

- 分类是词典，未使用模板不实例化。1–2 个独立条目存于 `<base_path>.md`，第 3 个迁移为 `<base_path>/<ID>-<slug>.md`；已展开集合保持目录。标题数、修改次数和篇幅不触发展开。
- 已有对象优先更新。展开须保留身份与事实，修复入链、相对出链、锚点和必要索引；最终只保留一个可编辑正文来源。
- 不把模板或安装行为提升为有效规范、批准、上线或访问权限。`operating_mode` 保持 `bootstrap`，直到项目实际满足声明的维护条件。
- `docs/_system/installation.json` 记录安装版本、托管文件或区块及基线哈希，用于重复运行跳过和升级保护本地修改；不维护业务条目数量。清单存在本身不能证明安装完整或兼容。
- 分别报告：**系统安装**（无阻断的必需资产与入口）、**项目配置**（真实定位及命令）、**严格就绪**（实际 `check --strict` 结果）。新安装因缺少核心事实或核验而 strict 失败是正常缺口；保留要求，不能降低门禁来制造通过。结构通过也不证明业务验证、发布或生产验证完成。
- 交付说明包含实际应用范围、冲突或未迁移范围、检查证据和下一步；已知历史问题或未验证旧格式未解决时，不宣称文档维护完整完成。

## 模板维护

来源仓库的 `templates/` 是模板唯一源码；Skill 内 `assets/templates/` 是打包生成的可携带资产，不手工维护第二份协议。维护模板时，在来源仓库运行：

```bash
python3 skills/ai-docs-init/scripts/build_assets.py
python3 skills/ai-docs-init/scripts/build_assets.py --check
```

打包后可复制整个 Skill 独立使用，初始化不依赖来源仓库。使用安装后的项目协议处理日常写入，升级使用本 Skill。
