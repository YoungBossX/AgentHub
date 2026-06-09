## 为什么

AgentHub 已经有 Target Registry、Guardrails、Project Command Policy、
Provider Gateway、Runtime Config 和 Approval 入口，但策略判断仍分散在多个模块里。
真实开发任务需要一个统一的 Policy Engine 来回答：

- 命令能不能跑；
- 路径能不能改；
- 网络、成本、破坏性操作和部署是否需要审批；
- 平台维护是否需要更高等级审批；
- 拒绝或审批等待的原因能否进入 evidence / diagnostics。

V2.5 的目标不是扩大权限，而是把现有安全边界收束成一个可测试、可审计、可逐步接入
的策略决策层。Policy Engine 输出 `allow`、`deny`、`require_approval` 或
`require_elevated_approval`，供后续 Run Engine、Transactional Delivery、Preview /
Deploy 和 UI 复用。

## 变更内容

- 新增 Policy Engine 合同，定义 policy input、policy check、policy decision、
  outcome、risk level、approval type 和 evidence。
- 首批覆盖策略类别：
  - command；
  - path；
  - network；
  - cost；
  - destructive change；
  - deploy；
  - platform maintenance。
- 复用现有 Guardrails、Target Registry、Project Command Policy 和 Deployment
  Provider 语义，不删除旧路径。
- 让策略结果可脱敏记录：category、outcome、reason、target id、command type、
  approval type、risk level、safe metadata。
- 定义 approval timeout 默认拒绝，不因审批通道失效而放行。
- 增加后端单元测试覆盖四种 outcome、受保护路径、未配置命令、网络默认审批、
  生产部署拒绝、platform maintenance 高级审批和 evidence 脱敏。

## 能力

### 新能力

- `policy-engine`：统一生成安全策略决策，返回 allow / deny / require_approval /
  require_elevated_approval。

### 修改后的能力

- `guardrails`：作为 Policy Engine 的输入来源之一，保持现有行为。
- `project-command-policy`：作为 command policy 的配置来源。
- `target-registry`：作为 path、target、platform maintenance 和 deploy policy 的
  硬边界输入。
- `run-diagnostics`：后续可消费 policy evidence，但 V2.5 不要求大改 UI。

## 影响

- 后续实现预计新增 `apps/api/app/policy_engine.py` 和
  `apps/api/tests/test_policy_engine.py`。
- 首版可以是后端合同和 helper，不强制一次性替换 Run Engine / Approval / Deploy
  的所有调用点。
- 后续实现需要更新 `docs/change-log.md` 和 `docs/project-state.md`。
- V2.5 不新增任意 shell command agent、不绕过 PlanValidator、不放开网络或生产部署、
  不新增 provider marketplace、不替换 Scheduler / Provider Gateway / adapters。
