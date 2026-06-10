# V2.4 项目配置边界冻结审查

**日期：** 2026-06-09

## 范围

V2.4 为已注册项目新增了 ProjectProfile 边界。它将现有的项目分析和目标元数据转换为可审计的配置摘要，同时不改变硬执行边界。

已实现：

- ProjectProfile 契约，包含配置 ID、显示名称、项目类型、框架、包管理器、allowed/denied 路径、命令、预览策略、置信度、状态和警告。
- 项目分析器输出现在包含 `projectProfile`。
- 外部目标和工作区目标响应暴露了派生的 `projectProfile` 摘要。
- TargetProject 可为外部目标携带派生的项目配置。
- 项目命令策略直接覆盖已配置命令、缺失命令、不匹配命令、未知命令类型以及保守的通用仓库行为。
- 编码代理目标指令包含项目配置 ID、状态、预览策略和已配置的配置命令。

## 安全性

- ProjectProfile 是描述性上下文，而非授权边界。
- 目标注册表、计划验证器、护栏、提供者网关和命令策略仍然是硬执行控制。
- 通用仓库不会打开任意 shell 命令；仅允许显式配置的验证命令。
- 受保护路径仍然被拒绝：`.git`、`.env*`、`secrets`、`node_modules`、virtualenv/cache/build 输出以及目标外部路径。
- 平台维护仍然需要显式的平台模式和审批。
- 未新增任何适配器、提供者市场、WebSocket、Docker 沙箱、PR 创建、生产部署或任意 shell 命令代理。

## 验证

| 命令 | 结果 |
|---|---|
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_project_profiles.py tests/test_project_analyzer.py -q` | 通过 |
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_external_workspaces.py tests/test_target_registry.py tests/test_project_profiles.py tests/test_project_analyzer.py -q` | 通过 |
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_project_command_policy.py tests/test_external_evidence.py -q` | 通过 |
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_task_runs.py::test_external_target_context_reaches_instruction_builder tests/test_task_runs.py::test_external_backend_instruction_uses_external_target_metadata -q` | 通过 |
| `pnpm check` | 通过 |
| `pnpm test` | 通过，web 90 / API 556 / demo-api 5 |
| `pnpm demo:api:test` | 通过，5 个测试 |
| `openspec validate agenthub-v2-4-project-profile-boundary --strict` | 通过 |
| `git diff --check` | 通过 |

## 限制

- ProjectProfile 元数据派生自现有目标字段；V2.4 未为配置快照添加数据库列或迁移。
- Next.js 和 FastAPI 预览策略记录为元数据，但 V2.4 未为每个框架产品化完整的预览托管。
- 计划器目标摘要仍然依赖现有的上下文路径。V2.4 为编码代理指令和目标 API 添加了配置上下文，但未更改计划器路由语义。
- 策略引擎、事务性交付、检查点回滚和生产部署审批仍属于后续的可靠性 V2 阶段。

## 后续工作

建议的下一个实现任务：启动 V2.5 策略引擎，使用一个仅限后端的小型策略契约，该契约消费目标注册表、ProjectProfile 和现有护栏信号，返回 `allow`、`deny`、`require_approval` 或 `require_elevated_approval`。
