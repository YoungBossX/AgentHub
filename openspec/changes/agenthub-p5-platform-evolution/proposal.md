## 为什么

AgentHub 最终演示加固已冻结，围绕一个经过验证的本地单用户
Agent 编码工作区 / 强大的演示 MVP。基准循环为：

```text
requirement -> plan -> agent execution -> diff -> preview -> mock deploy
```

这个基线很有价值，但它仍然像一个演示指挥中心。

P5 应该更果断地将 AgentHub 推向产品方向：

```text
IM-style interaction -> Manager Agent planning -> coding agent execution
-> review agent -> artifact cards -> preview -> mock deploy -> follow-up interaction
```

当前的 P5 计划过于保守，因为它以轻量级会话上下文作为主要的首个切片开始。P5 应改为一个可执行的平台演进计划，用于构建 IM 风格的多智能体编码工作区 v1，同时仍保留最终演示基线，并避免长期平台功能，例如真正的多用户同步、外部 IM 集成、生产部署或提供商市场。

## 变更内容

将 `agenthub-p5-platform-evolution` 从宽泛的研究路线图修订为本地单用户 IM 风格多智能体编码工作区 v1 的可执行 OpenSpec 变更。

P5 为以下内容增加了计划中的实现路径：

1. Agent 注册表与 IM 联系人界面。
2. 共享上下文与执行账本。
3. 审查 Agent 工作流。
4. 多 Agent 执行追踪界面。
5. 动态管理器规划器 v1。
6. 制品消息卡片 v2。
7. P5 端到端预演与冻结审查。

预期的 P5 产品体验是：

```text
user requirement -> Manager Agent planning -> coding agent execution
-> review agent -> artifact cards -> preview -> mock deploy
-> follow-up interaction
```

P5 将当前已验证的适配器保留为一级运行时选项：

- `CodexAdapter`
- `ClaudeCodeAdapter`
- `ScriptedMockAdapter`

P5 可能会引入更清晰的产品角色，例如管理 Agent、编码 Agent 和审查 Agent，但绝不能移除或退化当前的适配器以及现有的 diff / preview / mock deploy 路径。

## 能力

### 新能力

- `im-agent-workspace`: 本地单用户 IM 风格多智能体编码工作区
  v1，包含智能体联系人、direct-chat/group-workflow 模式、执行
 台账、审查制品、执行轨迹、有限管理器规划，以及
  制品消息卡片。

### 修改后的能力

最终演示的运行保障均未移除。P5 基于冻结基线构建。

## 影响

OpenSpec 制品：

- `openspec/changes/agenthub-p5-platform-evolution/proposal.md`
- `openspec/changes/agenthub-p5-platform-evolution/design.md`
- `openspec/changes/agenthub-p5-platform-evolution/tasks.md`
- `openspec/changes/agenthub-p5-platform-evolution/specs/im-agent-workspace/spec.md`

P5 后续应用时的预期实现影响：

- 后端：
  - 智能体 registry/contact 元数据；
  - 共享执行账本；
  - 审查制品类型与审查任务流程；
  - 有界的管理器规划器输出；
  - 支持后续交互的制品引用。
- 前端：
  - 智能体联系人列表；
  - direct-chat/group-workflow 可视化模式；
  - 多智能体执行轨迹；
  - 用于差异对比、预览、审查和模拟部署的内联制品卡片；
  - 制品 selection/reference 用户界面。
- 数据模型：
  - 可能新增的元数据，用于智能体联系人展示、执行账本、审查制品、规划图结构及制品引用。
- 运行时：
  - 同会话内的写入任务保持串行，以避免工作树冲突；
  - v1 版本中审查任务可能为只读且非阻塞；
  - 差异对比、预览和模拟部署功能保持不变。

## 明确非目标

P5 不是一个完整的即时通讯平台。P5 明确不实现以下功能：

- 完整的多用户即时通讯平台；
- 对接真实的飞书、微信、Slack、Matrix 或其他即时通讯系统；
- 桌面端或移动端应用；
- 服务商市场；
- 生产环境部署；
- Docker 沙箱；
- 创建 PR；
- 无限制的任意代码编辑；
- 完整的向量数据库记忆；
- 分布式工作节点集群；
- 企业审批工作流；
- 实时多用户同步与冲突解决；
- 用户创建的智能体作为即时 P5 运行时功能。

用户创建的智能体将作为内置注册表、能力模型、权限和审计功能稳定后的未来能力。

## 验证

对于此提案修订：

```bash
git diff --check
openspec validate agenthub-p5-platform-evolution --strict
```
