# 初始化与迁移指南

## 先理解交付物
这是一套技术栈无关的文档骨架，不包含你的业务事实，也不假设源码、测试、迁移或部署脚本位于某个目录。根目录保留人和 AI 的入口；所有项目说明放在 `docs/`。

## 第一步：合并，不覆盖
在独立分支或安全副本中解压。对已有 README、AGENTS.md 和 docs 内容逐项比对，保留原有事实与约束；不要直接覆盖。核验根执行入口及权限提案，确认它们符合你的使用方式。

## 第二步：建立定位能力
填写 `project-map.json`：仓库入口、前后端、机器契约、数据库 Schema、迁移、测试、环境配置、观测、发布来源和外部设计来源。不适用的位置标记 disabled 并说明原因。可以映射多个仓库，不要求移动代码。

填写 `commands.json`：真实可执行程序与参数、工作目录、环境、副作用、验证时间和证据。工具不会执行这些命令；不要从文件名猜测它们的安全性。

## 第三步：初始化当前事实
优先填写项目总纲、架构总览、开发启动指南、测试策略、安全基线和权限边界。保留未知项。只有适用范围、依据和批准条件满足后，才将草案改为 active。

## 第四步：迁移原文档
依据 `original-document-map.md` 拆分。先解决重复事实与冲突，再统一命名。需求按功能、Backlog/Bug 按任务、发布按版本、成本按月、日志按会话、反馈按条目迁移。旧路径有引用时留下跳转或更新入链。

## 第五步：形成一个闭环
选一个已批准的小任务，创建任务条目，关联规范、代码映射和测试；让一个没有历史聊天的新 AI 按入口完成定位与验证。其结果用于修补文档缺口，不靠一次性补齐所有模板。

## 工具操作
以下命令在仓库根目录执行，需要 Python 3.10 或更高版本，不安装第三方依赖。

```bash
python3 docs/_tools/docctl.py check
python3 docs/_tools/docctl.py new feature FEAT-001 subscription --title "订阅功能"
python3 docs/_tools/docctl.py new task TASK-001 implement-subscription --title "实现订阅功能"
python3 docs/_tools/docctl.py index
python3 docs/_tools/docctl.py find --type task --state ready --limit 20
python3 docs/_tools/docctl.py route billing
```

`check` 检查模板结构；`check --strict` 额外检查核心文档、必需路径和命令是否达到已声明的就绪条件。未配置的新模板在 strict 模式下应失败，不能把它误报成项目已可自治。

## 不要做的事情
不要把所有模板改成 active；不要自动填写核验日期；不要一次性导入全部文档到 Agent 上下文；不要为了适配本套件移动实际代码；不要把未配置的测试写为通过。
