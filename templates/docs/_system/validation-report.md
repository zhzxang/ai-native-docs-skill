# 交付验证记录

验证对象：统一轻量初始化、共享 Skill 资源、文档工具与模板源码，不是实际业务项目。
验证日期：2026-10-02。资源包版本：2.0.0。

## 已执行

| 检查 | 结果 | 范围 |
|---|---|---|
| 文档工具行为测试 | 62 项通过 | 紧凑逐条元数据、第三条展开、状态、引用迁移、路由、索引、结构与严格门禁、外部资源及版本保护 |
| 轻量安装行为测试 | 42 项通过 | 精确五文件布局、入口合并、事实与配置保全、幂等与格式保留、旧完整安装转换、所有权与引用保护、计划过期、实时引用复验、锁及失败回滚 |
| 独立 Skill 包测试 | 11 项通过 | 整个 Skill 复制到临时目录，从其他工作目录操作目标；保存并应用计划、版本与路径边界、资源只读、外部 CLI 的 check/new/find/route/index、第三条展开与链接修复、省略 root 的写入保护 |
| Skill 格式校验 | 通过 | 官方 skill-creator quick_validate.py，入口名称、front matter 和未完成占位 |
| 打包资产一致性 | 通过，194 文件无差异 | templates 是唯一资源源码，生成 assets/templates；不打包派生索引或交付附件 |
| 源码参考包结构检查 | 通过，188 Markdown、0 错误、0 警告 | 60 类注册表和路由有效，集中源不作为项目实例，业务记录数 0 |
| 初始 strict 检查 | 按预期失败 | bootstrap、身份未知、核心文档和真实命令未就绪；未降低门禁 |
| 独立实际使用 | 新老项目两组通过 | 脱离本仓库使用 Skill 完成接入、普通二次调用和各三条功能草稿；结构、查找、路由、索引正常，第三条展开保全正文、元数据和相关引用 |
| 配置格式复测 | upgrade / noop，0 创建、0 更新、0 删除 | 使用不同缩进、逆序键和确认的扩展字段，全部14个目标文件字节、mtime和路径不变 |
| 变更格式检查 | 通过 | git diff --check |

共115项自动测试通过。文档工具62项的最终实现通过全套；之后仅安装器增加保留配置格式的修复，42项安装测试与11项独立包测试再次通过。

## 实际安装边界

空项目只生成根 AGENTS.md、根 README.md、docs/AGENTS.md、docs/README.md 和 docs/.ai-docs.json，共五个文件。确认项目概况后才额外创建 draft 总纲，不预建业务分类、空登记项或索引。规则、工具和模板保存在 Skill，目标项目不创建 _system、_tools 或 _templates，没有完整安装选项。

配置按字段区分项目身份、位置、命令、就绪、定制与安装状态，当前不拆分；system.version 固定匹配资源版本，不写开发者机器绝对路径。省略 --root 的 new/index 无法写入 Skill 资源。旧完整安装仅依据真实所有权、哈希及当前引用清理，未知、本地修改或仍被引用的材料保留并报告。

独立试用中原 README/AGENTS 正文保留，历史设计及 Python 源码字节不变，旧引用有效；历史材料未被整库迁移。新老项目严格检查保留真实配置缺口，负责人、批准和核验字段没有伪造。

复核发现保留自定义模板仍需要旧规则时可能误删其依赖，已修复引用遍历并加入回归。独立试用发现配置纯格式变化导致无语义写入，已修复并用新缩进、键序及扩展字段复测。

## 可复现命令

从本仓库根运行：

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s templates/docs/_tools -p 'test_*.py' -v
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s skills/ai-docs-init/scripts -p 'test_*.py' -v
python3 skills/ai-docs-init/scripts/build_assets.py --check
python3 templates/docs/_tools/docctl.py check
python3 templates/docs/_tools/docctl.py check --strict
git diff --check
```

实际目标项目使用 Skill 中的工具：

```bash
python3 /Skill目录/assets/templates/docs/_tools/docctl.py --root /目标项目 check
python3 /Skill目录/assets/templates/docs/_tools/docctl.py --root /目标项目 check --strict
```

测试环境为 Python 3.14.5。工具使用 Python 3.10+ 和标准库，未逐一验证其他解释器与操作系统。Skill入口位于 skills/ai-docs-init/SKILL.md；保存到仓库不代表全局安装，也不证明所有客户端均会自动发现。

## 验证边界

结构检查只能验证可识别元数据、布局、阈值、引用和普通Markdown锚点，不能证明对象语义独立、归类正确、批准真实、外部来源有效或生产行为正确。无元数据历史纯文本不进入find/index，需明确报告未迁移与未验证范围，不能把结构通过当作全集维护完成。

未接入真实业务构建、外部系统、客户端Hook或分支保护；未执行登记的项目命令。安装、配置就绪、业务验证、批准和上线是不同状态，不以安装行为或模板内容互相代替。
