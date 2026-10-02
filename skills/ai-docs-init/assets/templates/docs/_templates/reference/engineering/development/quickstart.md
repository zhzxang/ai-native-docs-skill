---
id: "DEV-QUICKSTART"
type: "development-guide"
status: "template"
summary: "经过核验的环境准备、启动和检查流程。"
owner: null
applies_to: "{{VERSION_OR_SCOPE}}"
verified_at: null
verification_ref: null
authority: "procedure"
approved_by: null
approval_ref: null
---

# 本地开发与验证入口

## 前提
{{操作系统、运行时及版本、必要账户和安全边界。}} 依赖版本以项目锁文件或选定的版本来源为依据，不在这里手工复制整份依赖清单。

## 代码与命令定位
实际目录与具体命令统一在目标项目的 `docs/.ai-docs.json` 登记。这里按顺序引用命令 ID，不猜测 pnpm、npm、uv、cargo 等技术栈。

| 步骤 | 命令 ID 或操作入口 | 预期结果 | 失败处理 |
|---|---|---|---|
| 准备依赖 | setup | {{SUCCESS_SIGNAL}} | {{GUIDE_OR_ERROR}} |
| 配置环境 | {{ENV_GUIDE}} | {{REQUIRED_SAFE_CONFIG}} | {{MISSING_CONFIG_BEHAVIOR}} |
| 启动 | dev | {{LOCAL_URL_OR_PROCESS}} | {{TROUBLESHOOTING}} |
| 静态检查 | lint | {{EXPECTED_RESULT}} | {{FAILURE_ACTION}} |
| 相关测试 | test-unit / test-integration / test-e2e | {{TEST_SCOPE}} | {{FAILURE_ACTION}} |

## 本地数据
说明安全的样例数据来源和重置方法，禁止默认下载生产数据。需要外部 sandbox 时说明帐号、权限、额度与清理方式，不保存凭据。

## 仓库导航
按任务说明应查看哪些模块映射、契约、数据说明和测试集合。具体路径由映射维护。

## 已知平台差异
{{不同操作系统或容器环境的差异，无法运行的条件和替代验证方式。}}

## 核验依据
填写最近一次实际从干净环境启动的环境版本、提交和证据；未执行前保持 unknown，不填写虚构成功输出。
