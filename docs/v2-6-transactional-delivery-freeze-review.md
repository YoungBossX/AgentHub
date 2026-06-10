# V2.6 事务性交付冻结审查

**日期：** 2026-06-09

## 范围

V2.6 在现有 TaskRun 检查点、差异、审查、命令证据、恢复和诊断路径之上，新增了事务性交付证据层。

已实现：

- 交付状态和重试模式。
- 基于现有 TaskRun `preRunCheckpoint` 指标的检查点证据投影。
- 待定验证和回滚预检决策。
- 验证门控辅助函数，可将失败的命令证据、被拒绝的策略证据以及高风险审查证据转换为 `review_required`。
- 交付制品状态和接受决策证据。
- 记录检查点恢复意图并拒绝缺失检查点的回滚决策证据。
- 当前状态与检查点重试的显式重试模式证据。
- 用于交付决策的 TaskRunEvent 记录辅助函数。
- `delivery.*` 事件的运行诊断映射。

## 安全性

- V2.6 不会替换持久运行引擎、提供者网关、会话队列、目标锁、策略引擎或运行诊断。
- V2.6 不会新增适配器、WebSocket、Docker 沙箱、PR/export、生产部署或规划器核心重写。
- 回滚辅助函数当前仅记录安全证据和预检决策；尚不执行破坏性工作树恢复。
- 验证失败表示为 `review_required` 证据，不得声称交付成功。

## 验证

| 命令 | 结果 |
|---|---|
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_transactional_delivery.py tests/test_recovery.py -q` | 通过 |
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_transactional_delivery.py tests/test_run_diagnostics.py -q` | 通过 |
| `pnpm check` | 通过 |
| `pnpm test` | 通过，Web 90 / API 582 / demo-api 5 |
| `pnpm demo:api:test` | 通过，5 项测试 |
| `openspec validate agenthub-v2-6-transactional-delivery --strict` | 通过 |
| `git diff --check` | 通过 |

## 限制

- V2.6 有意将实际回滚执行排除在范围之外。当前实现仅记录回滚 readiness/refusal 和恢复意图。
- 运行引擎终结器行为尚未更改以阻止交付验证上的 preview/deploy 任务；V2.6 为后续集成提供了证据钩子和诊断映射。
- 接受记录会记录制品状态证据，但不会将更改合并到其他分支或创建 PR/export 制品。

## 后续工作

建议后续工作：将事务性交付门控接入运行引擎终结流程，以便验证失败时暂停下游 preview/deploy，直至用户接受、回滚或重试。
