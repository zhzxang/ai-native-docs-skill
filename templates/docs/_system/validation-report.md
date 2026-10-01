# 交付验证记录

验证对象：自适应文档模板、内置文档工具与项目内 `ai-docs-init` Skill，不是实际业务项目。
验证日期：2026-10-02。

## 已执行

| 检查 | 结果 | 范围 |
|---|---|---|
| 工具行为测试 | 88 项全部通过 | 原有 58 项文档工具测试，加 30 项增量安装测试；覆盖最小部署、托管区块合并、历史内容保留、幂等升级、配置保护、本地修改冲突、schema 阻断、计划过期、总纲草案、所有权边界、锁与失败回滚，以及集合展开、状态、引用、路由和索引 |
| Skill 可携带测试 | 8 项全部通过 | 将完整 Skill 复制到临时目录，从其他工作目录预览并应用同一计划，重复执行跳过；检查过期计划、目标不匹配、只读盘点、计划存放边界、目标符号链接保护及摘要不损失完整计划 |
| Skill 格式校验 | 通过 | 官方 skill-creator 的 quick_validate.py，检查入口名称、front matter 和未完成占位 |
| 打包资产一致性 | 通过，193 个文件无差异 | templates 为唯一模板源码，生成的 assets/templates 可独立使用；不打包派生索引和参考包交付附件 |
| 独立使用验证 | 新老项目两组通过 | 独立 Agent 在临时目录使用整个 Skill 的副本完成安装、真实配置与普通第二次调用；两组结构通过、strict 缺口保留，第二次整个文件树路径与 SHA-256 不变，历史正文、源码和链接保全 |
| 参考包结构检查 | 通过，188 个 Markdown、0 错误、0 警告 | 集中参考源不作为项目实例，当前业务记录数为 0；60 类注册表与路由有效 |
| 初始严格就绪检查 | 按预期返回失败 | bootstrap、项目名和负责人未填写、必需业务文档及真实命令未配置，不能宣称项目就绪 |
| 索引重建 | 成功，0 个实例、0 个类型页面 | 移除旧模板草案索引，集中源不计入实例，空集合不生成页面 |
| 变更格式检查 | 通过 | git diff --check |

独立复核补充了五类回归场景：注册条目错位、展开文件保存多个紧凑条目、旧标题锚点、docs 之外的仓库 Markdown 入链、任务 handover_ref 路径与锚点。这些问题已修复并纳入测试。

Skill 独立试用发现首次逐文件计划输出过长，已增加 `--summary`；空项目预览从 1,378 行缩为 32 行，完整变更仍保存于计划文件。无元数据的历史文档在结构检查中仅核验链接等可识别结构，尚未迁移、语义及有效性未验证的范围须另行报告。

## 可复现命令

从本参考包仓库根目录运行：

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s templates/docs/_tools -p 'test_*.py' -v
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s skills/ai-docs-init/scripts -p 'test_*.py' -v
python3 skills/ai-docs-init/scripts/build_assets.py --check
python3 templates/docs/_tools/docctl.py check
python3 templates/docs/_tools/docctl.py index
python3 templates/docs/_tools/docctl.py check --strict
git diff --check
```

实际项目部署后使用 `docs/_tools/docctl.py`。初始化只部署入口、规则、工具和集中参考源；默认不创建业务文件、集合目录或生成索引，需实际内容时才实例化。

项目内 Skill 位于 `skills/ai-docs-init/SKILL.md`，可显式引用或复制整个目录使用。客户端是否自动发现该目录取决于其配置，本次验证不代表已全局安装或已核验所有客户端的发现行为。

测试在 Python 3.14.5 环境执行。工具使用 Python 3.10+ 语法与标准库，未逐一验证其他解释器版本和操作系统。

## 验证边界

结构检查判断声明、逐条元数据、位置、阈值、普通 Markdown 链接与本套格式的锚点一致性，不能证明对象的语义独立性、归类判断、批准真实性、外部来源或生产行为正确。本文的“通过”只覆盖实际执行的工具检查。

未接入真实项目构建、业务测试、外部系统、客户端 Hook 或分支合并保护。写入工具和文档入口不等于不可绕过的文件权限边界，实际项目需要自行接入所需门禁。

模板中的未知项、草案和参考写作指令不能机械转换为“已批准”“已验证”或“已上线”。条目填写与语义审查仍是每次文档交付的一部分。
