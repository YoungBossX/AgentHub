## 总体设计

V2.6 在现有 TaskRun 执行和制品之上新增“交付事务”投影。首版优先使用
TaskRunEvent、metrics_json 和现有 Artifact/Diff/Review/Command Evidence 记录状态，
避免大规模迁移。

目标形态：
```text
TaskRun execution
  -> delivery checkpoint evidence
  -> diff / validation / review gates
  -> delivery decision
  -> accepted | review_required | rolled_back | retry_requested
```
## Delivery 状态

建议状态：

- `pending_validation`
- `review_required`
- `accepted`
- `rolled_back`
- `retry_from_current_state`
- `retry_from_checkpoint`

这些状态首版可存在于 delivery helper / event / metrics 中，不一定扩展
`TaskRun.state`，避免大面积兼容风险。

## Checkpoint

现有 `create_task_run` 已记录 `preRunCheckpoint` 和 checkpoint event。V2.6 应明确：

- 没有 checkpoint 时不得执行 rollback；
- checkpoint id / worktree path / allowed paths / target id 应进入 delivery evidence；
- checkpoint 不应包含 secrets 或受保护 host path；
- rollback 必须在 assigned session worktree 内执行。

## Validation Gate

validation gate 检查：

- command evidence 是否存在；
- command evidence 是否失败；
- diff collection 是否失败；
- policy decision 是否拒绝；
- review 是否有 high risk findings。

结果：

- 通过：可进入 accept 或后续 preview/deploy；
- 失败：进入 `review_required`，不得宣称交付成功；
- 证据不足：显示 `review_required` 或 limited evidence，不推断成功。

## Accept

accept 记录当前 artifact state：

- diff artifact ids；
- review artifact ids；
- command evidence ids；
- policy decision evidence；
- acceptedBy / acceptedAt；
- acceptedFromCheckpoint。

accept 不一定立即 merge 到主分支；首版只记录“用户接受当前 session worktree 交付状态”。

## Rollback

rollback 使用 checkpoint 恢复 worktree，并记录：

- rollbackFromCheckpoint；
- restored paths；
- refused reason；
- policy decision；
- event `delivery.rolled_back` 或 `delivery.rollback_refused`。

rollback 不得触碰 target denied paths、platform code 或其他 session worktree。

## Retry Mode

retry 必须明确：

- `current_state`：保留当前 worktree 继续修；
- `checkpoint`：先回滚或从 checkpoint 恢复后重试；
- `new_session`：后续可选，不要求 V2.6 实现。

Retry evidence 应让用户知道 agent 是在什么状态上继续。

## 与现有阶段边界

### V2.1 Durable Run Engine

V2.6 不重做 worker、lease、heartbeat、interrupt 或 timeout，只补 delivery gate。

### V2.3 Queue / Target Lock

V2.6 不改变 lock 规则。rollback / accept 需要在现有 session queue / target lock 边界内。

### V2.5 Policy Engine

V2.6 可以调用 policy helper，但不能绕过 policy 结果。

### V2.7 Diagnostics

V2.6 应产生更清晰的 delivery 事件，供 diagnostics 分类和 timeline 消费。

## 测试策略

后续实现应覆盖：

- checkpoint evidence；
- adapter completed + validation failure -> review_required；
- accept records artifact state；
- rollback restores checkpoint or refuses without checkpoint；
- retry mode is explicit；
- validation failure does not enqueue preview/deploy success；
- rollback refuses target-outside / denied paths；
- diagnostics 能看到 delivery events。
