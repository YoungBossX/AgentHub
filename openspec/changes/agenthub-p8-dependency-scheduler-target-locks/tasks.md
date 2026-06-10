## 1. P8 依赖调度器与目标锁

- [x] 1.1 P8-1 依赖感知的任务调度器
  - 目标：使声明的任务图依赖关系可运行。
  - 范围：
    - 添加一个调度器边界，从 `dependsOnTaskIds` 评估任务就绪状态；
    - 确保下游任务等待依赖项完成；
    - 确保失败、中断或阻塞的依赖项会阻塞下游任务；
    - 通过任务、运行、事件或调度器元数据暴露依赖等待/阻塞原因；
    - 保留调度器路径之外任务的现有手动 TaskRun 创建行为。
  - 验收标准：
    - 未完成的依赖项阻止自动 TaskRun 创建；
    - 当没有其他规则阻塞时，已完成的依赖项允许可运行任务继续执行；
    - 失败的依赖项会阻塞下游任务并标识该依赖项；
    - 依赖状态可通过 API 负载或事件流可见。
  - 验证：
    - 调度器单元测试；
    - 依赖就绪状态 API 测试；
    - `pnpm check`；
    - `pnpm test`；
    - `git diff --check`；
    - `openspec validate agenthub-p8-dependency-scheduler-target-locks --strict`。

- [x] 1.2 P8-2 目标写入锁。
  - 目标：在计划执行期间防止同一目标的写入冲突。
  - 范围：
    - 从 P7 注册表感知计划中推导任务目标 ID 和 read/write 模式；
    - 为写入任务添加锁获取/释放；
    - 序列化 `demo-frontend` 写入任务；
    - 序列化 `demo-backend` 写入任务；
    - 保持 `agenthub-platform` 写入任务受平台模式和审批控制；
    - 允许面向读取的审查/QA 任务在安全时避免写入锁。
  - 验收标准：
    - 两个 `demo-frontend` 写入任务不能并发运行；
    - 两个 `demo-backend` 写入任务不能并发运行；
    - 等待任务报告带有目标 ID 的 `waiting_target_lock`；
    - 审查/QA 任务不会获取写入锁，除非显式配置为写入任务；
    - 普通后端任务不能锁定或写入 `agenthub-platform`。
  - 验证：
    - 目标锁单元测试；
    - 调度器并发测试；
    - 平台目标保护测试；
    - `pnpm check`；
    - `pnpm test`；
    - `git diff --check`；
    - `openspec validate agenthub-p8-dependency-scheduler-target-locks --strict`。

- [x] 1.3 P8-3 自动运行流水线。
  - 目标：通过现有的执行和制品路径，自动推进有边界的全栈应用流水线。
  - 范围：
    - 为以下流程添加调度器推进：
      契约 -> 后端 -> 前端 -> Review/QA -> 预览 -> 模拟部署；
    - 使用现有的 TaskRun 创建、适配器执行、差异收集、审查制品、预览和模拟部署代码路径；
    - 保留 P6/P7 迷你 CRM 行为和目标 ID；
    - 确保模拟部署明确标记为模拟；
    - 避免重复的真实 Claude/Codex 变更，除非有边界的冒烟测试明确要求。
  - 验收标准：
    - 迷你 CRM 流水线能够按依赖顺序自动推进；
    - 后端执行目标为 `demo-backend`；
    - 前端执行目标为 `demo-frontend`；
    - 审查仅在所需差异存在后开始；
    - 预览和模拟部署仍使用现有 API 和制品。
  - 验证：
    - 流水线推进测试；
    - 迷你 CRM 调度器 API 冒烟测试（在足够条件下使用模拟或脚本化执行）；
    - `pnpm check`；
    - `pnpm test`；
    - `pnpm demo:api:test`；
    - `git diff --check`；
    - `openspec validate agenthub-p8-dependency-scheduler-target-locks --strict`。

- [x] 1.4 P8-4 故障恢复与阻塞状态
  - 目标：使调度器的故障传播、重试和兜底状态显式化。
  - 范围：
    - 引入或形式化调度器可见的状态：
      `waiting_dependency`、`waiting_target_lock`、`running`、`completed`、
      `failed`、`blocked`、`retryable` 和 `fallback_available`；
    - 防止下游任务在上游故障后静默继续执行；
    - 通过 TaskRun 历史记录保持重试和兜底的可追溯性；
    - 确保真实的 Claude/Codex 成功声明有据可依；
    - 确保调度器在重试或兜底完成后重新评估下游任务。
  - 验收标准：
    - 故障的上游任务会阻塞下游任务；
    - 可重试和可兜底的状态可见；
    - 兜底会创建可追溯的运行历史；
    - 当依赖和锁规则满足时，完成的 retry/fallback 可以解除下游任务的阻塞；
    - 上游故障后，无下游任务声明成功。
  - 验证：
    - 阻塞状态测试；
    - retry/fallback 调度器测试；
    - event/history 回归测试；
    - `pnpm check`；
    - `pnpm test`；
    - `git diff --check`；
    - `openspec validate agenthub-p8-dependency-scheduler-target-locks --strict`。

- [x] 1.5 P8-5 调度器 UI 追踪。
  - 目标：在当前工作区 UI 中使调度器决策可见。
  - 范围：
    - 在现有任务卡片、时间线或执行追踪中展示调度器状态；
    - 显示依赖等待、目标锁等待、运行中、阻塞、失败、可重试、兜底可用和已完成状态；
    - 在有用处显示目标 ID 和依赖 ID；
    - 保留现有制品面板和制品消息卡片；
    - 避免大规模 UI 重新设计。
  - 验收标准：
    - 用户能判断任务为何未运行；
    - 阻塞任务在可用时标识上游失败；
    - 锁等待任务标识目标锁；
    - 现有的启动、重试、兜底、审查、预览、部署、制品卡片和制品面板行为保持可用。
  - 验证：
    - 前端组件测试；
    - 必要时进行 API 固件测试；
    - 可行时进行 browser/manual UI 冒烟测试；
    - `pnpm check`；
    - `pnpm test`；
    - `git diff --check`；
    - `openspec validate agenthub-p8-dependency-scheduler-target-locks --strict`。

- [x] 1.6 P8-6 P8 端到端预演与冻结评审。
  - 目标：验证 P8 在不回归的前提下添加调度器行为
    P6/P7.
  - 范围：
    - 验证迷你 CRM 任务图按正确顺序执行；
    - 验证目标锁保护 `demo-frontend` 和 `demo-backend`；
    - 验证失败依赖项阻止下游任务；
    - 验证评审、预览和模拟部署仍能正常工作；
    - 验证普通后端任务与 `apps/api` 保持隔离；
    - 验证平台任务保持显式且需审批；
    - 记录证据 ID、适配器使用情况、兜底使用情况、注意事项以及最终冻结建议。
  - 验收标准：
    - P8 迷你 CRM 预演生成合同、后端、前端、评审、预览和模拟部署证据；
    - 调度器顺序和锁证据已记录；
    - 失败阻塞证据已记录；
    - P6/P7 基线保持不变；
    - 未声明任何未经验证的真实 Claude/Codex 成功。
  - 验证：
    - 尽可能进行有针对性的 API/browser 预演；
    - `pnpm check`；
    - `pnpm test`；
    - `pnpm demo:api:test`；
    - `git diff --check`；
    - `openspec validate agenthub-p8-dependency-scheduler-target-locks --strict`。

## 2. P8 的明确非目标

- 分布式工作节点集群。
- 多用户即时通讯。
- Matrix、飞书、微信、Slack 或其他外部 IM 集成。
- 生产环境部署。
- Docker 沙箱。
- 提供商市场。
- PR 创建。
- 任意 SaaS 生成。
- 完整外部仓库导入。
- Desktop/mobile 客户端。
- Document/PPT 制品编辑器。

## 3. P8 完成定义

- 任务依赖关系驱动调度器的执行顺序。
- 针对同一目标写入的任务通过目标锁进行串行化。
- 受限的小型 CRM 流水线可通过现有的 TaskRun、差异对比、审查、预览和模拟部署路径自动推进。
- 失败的依赖关系会阻塞下游任务。
- 重试和兜底机制保持显式且可追溯。
- 调度器状态在 UI 中可见。
- P7 目标注册表仍是目标 ID 和目标保护的真实数据源。
- 普通后端任务无法修改 `apps/api`。
- 模拟部署仍保留模拟标签。
- 仅在实际运行时记录 Claude/Codex 的成功。
- P4/P5/P6/P7 基线保持不变。
