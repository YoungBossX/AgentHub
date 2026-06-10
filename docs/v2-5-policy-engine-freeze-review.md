# V2.5 策略引擎冻结审查

**日期:** 2026-06-09

## 范围

V2.5 新增了独立的策略引擎合约和无副作用的策略评估辅助函数。其目标是在不扩大 AgentHub 执行权限的前提下统一策略决策。

已实现：

- 策略类别：命令、路径、网络、成本、破坏性变更、部署和平台维护。
- 策略结果：允许、拒绝、需要审批、需要高级审批。
- 风险等级、审批类型、决策证据和安全元数据脱敏。
- 基于现有项目命令策略的命令策略辅助函数。
- 基于现有目标注册表/护栏语义的路径策略辅助函数。
- 默认需要审批的网络策略辅助函数。
- 允许 local/mock 预发布环境、外部预发布环境需要审批、默认拒绝生产环境部署的部署策略辅助函数。
- 针对 AgentHub 平台目标需要高级审批的平台维护辅助函数。
- 默认拒绝的审批超时辅助函数。
- 稳定的 `policy.decision` 证据负载辅助函数。

## 安全性

- V2.5 不会替换目标注册表、计划验证器、护栏、提供商网关、调度器或适配器。
- V2.5 不会新增任意 shell 命令代理、市场行为、生产环境部署、Docker 沙箱、WebSocket、云密钥管理器或 PR 创建。
- 通用仓库和项目配置文件元数据不允许未配置的命令。
- 外部网络和第三方部署仍受审批限制。
- 平台维护需要高级审批。
- 策略证据在序列化前会进行脱敏处理。

## 验证

| 命令 | 结果 |
|---|---|
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_policy_engine.py -q` | 通过 |
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_policy_engine.py tests/test_guardrails.py tests/test_project_command_policy.py -q` | 通过 |
| `pnpm check` | 通过 |
| `pnpm test` | 通过，Web 90 / API 568 / demo-api 5 |
| `pnpm demo:api:test` | 通过，5 项测试 |
| `openspec validate agenthub-v2-5-policy-engine --strict` | 通过 |
| `git diff --check` | 通过 |

## 限制

- V2.5 有意先添加了 contract/helper 层。现有的运行引擎、审批、部署和事务性交付路径尚未完全重构以要求策略引擎决策。
- 策略证据可在后续阶段由运行诊断/MissionTrace 消费，但 V2.5 不会新增 UI。
- 成本和破坏性变更策略已在合约中表示，可在 V2.6 事务性交付引入更丰富的变更门控时进行扩展。

## 后续工作

建议的下一个实现任务：启动 V2.6 事务性交付，以便预检、验证、接受、回滚和重试能够在正确的执行点调用策略引擎决策。
