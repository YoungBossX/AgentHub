## 为什么

AgentHub Reliability V2 已经补齐 durable run、provider gateway、session queue、
target lock、project profile、policy engine 和 run diagnostics。但当前交付链路仍偏直通：
coding agent 完成后，系统收集 diff / review / preview / deploy 证据；如果中间某一步失败，
用户往往只能看到失败状态，而缺少一个明确的“交付事务”来决定：

- 是否已有 checkpoint；
- diff 是否可检查；
- validation 是否通过；
- review 是否需要用户处理；
- 是否接受当前变更；
- 是否回滚到 checkpoint；
- retry 是基于当前状态还是 checkpoint 状态。

V2.6 的目标是把每个 coding TaskRun 的交付过程建模成可审计事务：

```text
preflight
  -> checkpoint
  -> execute agent
  -> collect diff
  -> validate commands
  -> review
  -> accept / rollback / retry
```

这不是新增一个执行引擎，也不是替换 V2.1/V2.3/V2.7，而是在现有 worktree、diff、
review、command evidence、checkpoint 和 diagnostics 基础上补齐交付闭环。

## 变更内容

- 新增 Transactional Delivery 合同与 helper，定义 delivery state、checkpoint、
  validation gate、review gate、accept、rollback 和 retry mode。
- 复用现有 TaskRun checkpoint / metrics、diff collection、review artifact、
  command evidence 和 recovery retry 逻辑。
- validation failed 不得伪装成成功；应进入 `review_required` 或失败诊断状态。
- accept 应记录当前 diff/review/command evidence 的 artifact state。
- rollback 应恢复 checkpoint，记录事件，并继续受 target allowed/denied paths 和
  Policy Engine 约束。
- retry 应显式区分 `retry_from_current_state` 与 `retry_from_checkpoint`。
- 增加后端测试覆盖 checkpoint、validation failure、accept、rollback、retry mode、
  preview/deploy 后续边界。

## 能力

### 新能力

- `transactional-delivery`：为 TaskRun 交付过程提供 checkpoint、validation gate、
  review_required、accept、rollback 和 retry evidence。

### 修改后的能力

- `run-engine`：后续可在 finalizer 阶段调用 delivery gate，但 V2.6 不重写 worker。
- `recovery`：retry/rollback 应显式记录基于当前状态还是 checkpoint。
- `run-diagnostics`：可消费 delivery validation/review/rollback 事件。
- `policy-engine`：preflight、rollback、deploy gate 等后续步骤可调用策略决策。

## 影响

- 后续实现预计新增 `apps/api/app/transactional_delivery.py` 和
  `apps/api/tests/test_transactional_delivery.py`。
- 可能小改 `run_engine.py`、`task_runs.py` 或 `recovery.py`，但必须保持 V2.1 durable
  worker、V2.3 queue/lock 和 V2.7 diagnostics 语义。
- V2.6 不新增 adapter、不做 PR/export、不做生产部署、不新增 WebSocket/Docker、不改
  Planner 路由核心。
