## 为什么

P5 让 AgentHub 感觉像一个本地单用户 IM 风格的多智能体编码工作区，但执行仍然过于演示化：普通用户请求需要过于明确的编排器措辞，而角色提及尚未作为清晰的分配快捷方式。P6 需要默认将普通消息路由到编排器/管理器，更直接地使用 Claude Code 和 Codex 作为实用的编码执行器，并保留 AgentHub 的安全边界、证据纪律以及 diff / 预览 / 模拟部署循环。

## 变更内容

P6 通过三个连续层级引入了代理执行能力升级：

1. **消息路由、直接代理分配与编排器自动运行**
   - 未明确提及角色的消息默认路由至编排器/管理器。
   - 明确提及角色时优先级最高：
     - `@orchestrator` 路由至编排器/管理器；
     - `@frontend` 创建前端代理任务；
     - `@backend` 创建后端代理任务；
     - `@qa` 创建质量保证任务；
     - `@review` 创建审查任务。
   - `@frontend`、`@backend`、`@qa` 和 `@review` 是为高级用户提供的显式分配模式，并非普通请求的默认路径。
   - 直接分配的任务保留用户的原始请求，可通过现有 TaskRun 路径启动。
   - 编排器创建的、针对安全演示目标的编码任务，通过现有 TaskRun 执行路径自动启动。
   - 请求被限定在安全目标目录范围内，但不会降级为仅限登录页面的旧指令模板。

2. **会话上下文包 + 基于角色的指令构建器**
   - 智能体指令包含最近的消息、执行账本、选定的制品上下文、最新差异、变更文件、preview/deploy 状态以及当前目标。
   - 前端、后端、QA/review 和管理员指令根据角色不同而有所区别，并为 Claude/Codex 提供足够的上下文以执行有意义的工作。
   - 对于不支持或不安全的请求，系统会如实失败或生成澄清任务，而不是假装系统可以完成任意工作。

3. **有界全栈应用生成垂直切片**
   - 添加一个安全的演示后端目标，如 `apps/demo-api`，使后端代理的工作不会随意修改 AgentHub 平台后端。
   - 添加契约优先的编排，使前端和后端任务引用相同的结构化应用契约。
   - 验证一个有界的小型应用流程，例如待办事项、笔记或迷你 CRM 联系人：

     ```text
     user requirement -> contract -> backend task -> frontend task
     -> qa/review -> diff -> preview -> mock deploy
     ```

P6 保留现有适配器：

- `CodexAdapter`
- `ClaudeCodeAdapter`
- `ScriptedMockAdapter`

它不会新增适配器系列，也不会替换 P4/P5 基线。

## 能力

### 新能力

- `agent-execution`: 默认编排器路由、直接角色分配、会话上下文打包、基于角色的指令、安全演示后端执行、契约优先规划以及受限的全栈垂直切片验证。

### 修改后的能力

无。P6 新增了一项执行能力，同时保留了现有的 P5
IM 风格工作区和 P4 最终演示保障。

## 影响

OpenSpec 制品：

- `openspec/changes/agenthub-p6-agent-execution-upgrade/proposal.md`
- `openspec/changes/agenthub-p6-agent-execution-upgrade/design.md`
- `openspec/changes/agenthub-p6-agent-execution-upgrade/tasks.md`
- `openspec/changes/agenthub-p6-agent-execution-upgrade/specs/agent-execution/spec.md`

P6 后续应用时的预期实现影响：

- 后端：
  - 消息路由策略：未提及的消息默认路由至编排器；
  - 针对显式可执行角色任务的直接提及路由；
  - 支持将 `@review` 作为可执行审查提及；
  - 默认将选定的制品上下文传递给编排器，而非绕过它；
  - 会话上下文包生成；
  - 基于角色的指令构建器；
  - 演示后端目标注册；
  - 契约优先的编排器输出；
  - 支持有界全栈垂直切片的任务图。
- 前端：
  - 保留当前 chat/task/artifact 界面；
  - 将直接提及任务显示为一级可执行任务；
  - 在需要时暴露 context/contract/review 制品；
  - 保留现有制品卡片和右侧制品面板。
- 数据模型：
  - 可能新增应用契约、上下文包元数据、选定制品引用及演示后端工作区元数据；
  - P6 阶段不包含多用户账户模型。
- 运行时：
  - 在冲突处理机制实现前，同会话写入任务保持串行执行；
  - 前端和后端写入任务使用安全的演示目标目录；
  - 预览和模拟部署仍为本地演示证据，不涉及生产环境部署。

## 明确非目标

P6 未实现：

- 任意 SaaS 生成；
- 不受限制地编辑 AgentHub 平台代码；
- 生产环境部署；
- 多用户即时通讯；
- Matrix、飞书、微信、Slack 或其他外部 IM 集成；
- 提供商市场；
- Docker 沙箱；
- 创建 PR；
- 企业审批工作流；
- 支付、认证或多租户生产系统。

## 验证

对于此 OpenSpec 变更：

```bash
git diff --check
openspec validate agenthub-p6-agent-execution-upgrade --strict
```
