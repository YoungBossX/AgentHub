## 为什么

P8 增加了依赖感知调度和目标锁，但它仍然是调度器 v1。P9 现在允许 AgentHub 操作已注册的外部本地项目，这增加了陈旧运行、陈旧锁、不安全重试和文件冲突的成本。

P10 是必要的，用于在不将 AgentHub 转变为分布式工作平台的前提下，使外部项目执行更安全、更易恢复。

## 变更内容

- 添加 TaskRun 心跳与租约元数据，以便将正在运行的工作检测为健康、过期、超时或已放弃。
- 添加过期目标锁清理功能，仅释放由过期运行持有的锁，并写入审计事件。
- 为写入任务添加运行前快照/检查点，包括 git 状态、基础提交、脏文件、目标路径以及外部目标元数据。
- 强化重试幂等性：记录先前运行上下文、检测脏工作区，并在未做出明确恢复决策时阻止不安全的重试。
- 强化失败传播机制：使失败的依赖项阻止下游工作，且 preview/mock 部署在前提条件失败后绝不执行。
- 添加冲突检测：针对重叠文件、脏工作区及合约漂移进行检测。
- 添加恢复操作：用于将过期任务标记为失败、释放过期锁、从当前状态重试、在安全时从检查点重试，以及停止或恢复下游推进。
- 针对过期任务、过期锁、失败依赖项、重试和冲突场景演练 P10，同时保留 P6/P7/P8/P9 基线。

P10 保留现有的 `CodexAdapter`、`ClaudeCodeAdapter` 和 `ScriptedMockAdapter` 行为。除非实际执行并记录了真实的运行过程，否则不得声称真实的 Claude/Codex 成功。

## 能力

### 新能力

- `scheduler-robustness`: TaskRun heartbeat/lease、过期锁清理、
  运行前检查点、重试幂等性、故障传播加固、
  冲突检测、可审计的恢复操作以及冻结演练。

### 修改后的能力

无。P10 在保留 P8 调度器语义和 P9 外部项目工作区模式的同时，增加了一层调度器健壮性层。

## 影响

OpenSpec 制品：

- `openspec/changes/agenthub-p10-scheduler-robustness-conflict-recovery/proposal.md`
- `openspec/changes/agenthub-p10-scheduler-robustness-conflict-recovery/design.md`
- `openspec/changes/agenthub-p10-scheduler-robustness-conflict-recovery/tasks.md`
- `openspec/changes/agenthub-p10-scheduler-robustness-conflict-recovery/specs/scheduler-robustness/spec.md`

P10 后续应用时的预期实现影响：

- 后端：
  - TaskRun 心跳/租约字段或等效的持久化元数据；
  - 过期运行和过期锁检测服务；
  - 运行前检查点记录和恢复元数据；
  - 重试幂等性检查；
  - 文件重叠、脏工作树和合约漂移的冲突检测；
  - 通过 `TaskRunEvent` 或专用审计界面实现可审计的恢复操作。
- 前端：
  - 现有任务时间线/执行轨迹中的调度器健壮性状态；
  - 可见的过期、超时、冲突、不安全重试、检查点和恢复状态；
  - 仅在显式 API 支持的情况下提供恢复操作入口。
- 运行时：
  - 过期锁清理不得释放活动锁；
  - 外部目标 allowed/denied 路径保持强制约束；
  - 不安全重试被阻止或需要显式恢复决策；
  - 预览和模拟部署仍受成功前置条件限制；
  - 不引入分布式工作节点集群、Docker 沙箱、生产部署、提供商市场、PR 创建、自动 Git 冲突合并、多用户 IM 或企业级 RBAC。
