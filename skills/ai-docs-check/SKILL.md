---
name: ai-docs-check
description: "按文档类型校验 AI 文档 meta、仓库结构与引用，提供版本化公共协议和模板；用于候选文档写入前校验及生成、同步、迁移后的检查。"
---

# 文档类型校验与公共协议

本 Skill 的 `assets/templates/` 提供共享协议、类型 schema、模板和 docctl。项目事实位于目标 `docs/.ai-docs.json` 和业务文档，资源不复制到项目。初始化、代码同步和历史迁移由各自 Skill 执行，本 Skill 不隐式执行这些动作。

## 校验候选文档

```bash
python3 /ai-docs-check/scripts/check.py check-meta /tmp/candidate.md /tmp/another.md
python3 /ai-docs-check/scripts/check.py --root /项目 check
python3 /ai-docs-check/scripts/check.py --root /项目 check --strict
```

`check-meta` 不要求项目已初始化，可以检查仓库外暂存文档。独立 front matter 与紧凑 `yaml doc-meta` 使用同一类型 schema，校验必填键、标量类型、nullable、枚举、日期、authority、核验配对和生效批准。未知扁平扩展字段保留并提示；已知类型专属字段混用会失败。`--allow-template` 只用于维护模板资源，不能把模板作为项目正文交付。

`check` 复用类型校验，进一步检查 ID、布局、单一正文源、本地链接与配置；`check --strict` 增加事实和核验就绪要求。类型未知或 meta 格式不支持时报告错误；历史无 meta 的普通 Markdown 仍需独立盘点和语义审查，不可凭结构通过宣称全部材料已验证。错误输出是 JSON，非零退出码用于自动化门禁。

## 写入与定位

日常写入先按需读取 `assets/templates/docs/_system/writing-policy.md`、`collections.json`、`conventions.md` 和对应类型模板。已有对象优先更新。docctl 的 `new` 在写入前用同一 schema 校验；AI 或其他生成器的候选文件用 `check-meta` 先验，再写入并检查仓库。

```bash
python3 /ai-docs-check/scripts/check.py --root /项目 find --type feature
python3 /ai-docs-check/scripts/check.py --root /项目 new feature FEAT-001 login --title "登录"
python3 /ai-docs-check/scripts/check.py --root /项目 route feature
```

schema 的唯一源码是 `assets/templates/docs/_system/meta-schemas.json`。公共规则、模板和运行工具直接维护在本 Skill 的 `assets/templates/`，其他 Skill 共用这份资源；分发直接携带本目录，无需复制构建。Skill 和协议回归测试集中在仓库根的 `tests/`。修改后从仓库根执行：

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p 'test_*.py'
python3 skills/ai-docs-check/scripts/check.py --root skills/ai-docs-check/assets/templates check
```

分发时复制本 Skill，再按需要携带 ai-docs-init、ai-docs-sync、ai-docs-migrate；其他脚本可用 `--source` 指定资源根。项目 `system.version` 必须匹配资源版本，缺失或不兼容时报错。meta 与结构通过只能证明机器检查范围，不能证明业务语义、批准真实性或项目命令执行成功。
