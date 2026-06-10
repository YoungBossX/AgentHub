## 背景

P14 引入了 agent/provider/profile 基础，P16 增加了运行时配置，P17-P17b 将规划器 LLM 与编码代理分离，P20 清理了工作区 UI，P21 增加了 PMO 协调。AgentHub 现在需要一个面向操作员的代理目录，使这个代理名册可见且可安全配置。

当前系统已经具备有用的原语：

- 内置的 `Agent` 行和角色联系人；
- AgentProfile 注册表概念；
- ProviderConfig 注册表与提供者可用性；
- AgentProfileDraft 安全约束；
- AgentRuntimeConfig 验证；
- 目标注册表与 PlanValidator 执行边界。

P22 应该将这些原语产品化，而不是替换它们。

## 目标 / 非目标

**目标：**

- 提供一流的 Agent 目录 API 和 UI。
- 以联系人风格档案展示内置 Agent 和安全草稿元数据。
- 添加对角色、提供商、适配器、能力、目标、模式和安全标志的兼容性检查。
- 保持草稿 Agent 仅为元数据且禁止执行，除非通过现有策略验证。
- 将运行时设置选择与兼容的目录条目关联。
- 保留简洁的聊天工作区；详细配置归属于设置。

**非目标：**

- 无任意 shell 命令代理。
- 无提供商市场或 OpenCode。
- 无新适配器。
- 无生产环境 secret/token 管理。
- 无多用户 sharing/RBAC.。
- 无完整插件执行系统。

## 决策

### 目录条目是派生而来的，并非新的真相源

Agent Directory 应从内置配置文件、已启用的 agent 行、提供商配置、运行时配置和安全草稿元数据中派生条目。P22 不应引入冲突的注册表。

### 草稿代理仍为仅元数据

草稿代理创建可收集显示名称、首字母缩写、角色、提供者 ID、
适配器类型、能力、支持的目标、支持的模式、描述以及
review/write 安全标志。它必须拒绝 shell 命令、不安全的工具
权限、不受限制的文件系统标志或写安全的草稿执行。

### 兼容性明确且可审计

每个目录条目应暴露兼容性元数据：

- 角色兼容性；
- provider/adapter 兼容性；
- 目标兼容性；
- 模式兼容性；
- 能力兼容性；
- 安全兼容性；
- availability/auth 状态。

运行时配置 PUT 必须如实拒绝不兼容的条目。

### 聊天保持整洁

工作区外壳可以显示紧凑的代理联系标签和设置链接，
但完整的目录管理应归属于专门的设置页面或标签页。

### 无执行绕过

选择代理配置文件仅改变运行时解析输入。执行
仍然流经规划器、计划验证器、调度器、目标注册表、
护栏和现有适配器。

## API 草图

- `GET /workspaces/{workspace_id}/agent-directory`
  返回具有兼容性和可用性的派生目录条目。
- `POST /workspaces/{workspace_id}/agent-profile-drafts`
  创建仅包含元数据的安全草稿。
- `GET /workspaces/{workspace_id}/agent-profile-drafts`
  列出草稿。
- `POST /workspaces/{workspace_id}/agent-directory/check-compatibility`
  根据 profile/provider. 检查 role/target/mode/capability 请求。

现有的运行时配置端点仍然是所选 Planner / Frontend / Backend / Review 默认值的持久化接口。

## 数据形态

目录条目：

- `id`
- `entryType`: `built_in` | `draft`
- `displayName`
- `avatarInitials`
- `role`
- `agentProfileId`
- `providerId`
- `adapterType`
- `capabilityTags`
- `supportedTargets`
- `supportedModes`
- `safeForWrite`
- `safeForReview`
- `status`
- `authStatus`
- `available`
- `runtimeSelectedForRoles`
- `compatibility`
- `description`

兼容性：

- `compatible`
- `reasons`
- `warnings`
- `role`
- `targetId`
- `mode`
- `requiredCapabilities`

## UI 草图

- `/settings/agents` 或运行时设置代理标签页。
- 包含简洁中文文案和返回链接的标题。
- 按角色、提供商、能力、目标、状态进行 Search/filter。
- 联系人风格卡片，包含提供商徽章、适配器、能力、目标、安全标志和可用性。
- 包含 save/cancel. 的草稿创建面板。
- 运行时角色选择器仅使用兼容条目，并将不可用或不兼容的条目显示为禁用状态并附上原因。

## 风险 / 权衡

- [风险] 若 profile/provider/runtime 数据不一致，目录推导可能造成混淆。→ 缓解措施：公开兼容性原因和来源标签。
- [风险] 用户可能期望草稿代理立即执行。→ 缓解措施：在验证前将草稿代理标记为 review-only/disabled。
- [风险] 运行时配置可能成为另一种策略绕过方式。→ 缓解措施：继续使用 AgentRuntimeConfig 验证和目标 Registry/PlanValidator.。
- [风险] 用户界面过于复杂。→ 缓解措施：保持聊天界面简洁，将详细信息移至设置中。

## 回滚

删除目录 UI/API helpers，并保持现有的 AgentProfile、ProviderConfig、AgentRuntimeConfig 和 AgentProfileDraft 行为不变。
