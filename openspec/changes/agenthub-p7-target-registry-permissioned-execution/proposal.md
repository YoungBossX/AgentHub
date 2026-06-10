## 为什么

P6 证明了 AgentHub 能够协调一个有限的全栈迷你 CRM 流程，并执行真实的 `ClaudeCodeAdapter`，但也暴露出目标知识分散在规划器逻辑、指令文本、审查检查、脚本和文档中。P7 是必要的，这样代理才能针对明确的目标项目执行，这些项目具有已知的允许路径、禁止路径、验证命令、预览设置和后端基础 URL。

## 变更内容

- 引入目标项目注册表作为受支持执行目标的唯一真实来源：
  - `demo-frontend` 用于 `apps/demo`；
  - `demo-backend` 用于 `apps/demo-api`；
  - `agenthub-platform` 用于 AgentHub 平台维护。
- 将目标元数据移入注册表记录，包括：
  - 目标 ID、显示名称、目标类型、根目录、允许路径、禁止路径、
    dev/test/preview 命令、基础 URL、允许的代理，以及平台模式/审批要求。
- 使指令构建器具备目标感知能力，以便角色指令使用注册表元数据，而非分散的硬编码路径和 URL。
- 使契约优先规划具备目标感知能力，通过引用 `frontendTargetId` 和 `backendTargetId`，然后从注册表推导出原始路径和后端基础 URL。
- 使审查/质量保证具备目标感知能力，检查允许路径违规、禁止的平台代码编辑、前后端基础 URL 不匹配以及契约目标一致性。
- 添加显式的平台维护模式，使普通应用后端任务与 `apps/api` 保持隔离，而平台维护仅在明确请求和批准时才能以 `agenthub-platform` 为目标。
- 针对 P6 迷你 CRM 路径演练 P7，以验证目标注册表间接引用是否保留了完整的 P6 差异/审查/预览/模拟部署基线。

## 能力

### 新能力

- `target-registry`：目标项目注册表、带权限的执行元数据、
  目标感知的 planning/instructions/review，以及显式的平台维护
  模式。

### 修改后的能力

P7 在保留 P4/P5/P6 基线的基础上引入了一项新能力。

## 影响

OpenSpec 制品：

- `openspec/changes/agenthub-p7-target-registry-permissioned-execution/proposal.md`
- `openspec/changes/agenthub-p7-target-registry-permissioned-execution/design.md`
- `openspec/changes/agenthub-p7-target-registry-permissioned-execution/tasks.md`
- `openspec/changes/agenthub-p7-target-registry-permissioned-execution/specs/target-registry/spec.md`

P7 后续应用时的预期实现影响：

- 后端：
  - 目标注册表模块或服务；
  - 上下文包和适配器运行请求中包含的目标元数据；
  - 规划器更新，以使用目标 ID 和注册表解析的元数据；
  - 指令构建器更新，以消费注册表记录；
  - 针对目标策略、允许路径、拒绝路径和后端基础 URL 一致性的审查/QA 检查；
  - 明确的平台维护路由和审批边界。
- 前端：
  - 无需进行广泛的重新设计；
  - 可选地在任务、上下文和制品界面上显示目标名称/模式，以便清晰展示。
- 数据模型：
  - P7 可以从静态的代码内注册表记录开始；
  - 持久化是可选的，除非实现需要，否则可推迟。
- 运行时：
  - 同一会话中的写入任务保持串行；
  - 普通应用程序任务保持在 `apps/demo` 和 `apps/demo-api` 内；
  - `apps/api` 保持受保护状态，除非明确进入平台维护模式。

P7 不添加多用户即时通讯、外部即时通讯集成、生产环境部署、
Docker 沙箱、提供商市场、PR 创建、无限制的仓库编辑、
分布式调度或任意 SaaS 生成。
