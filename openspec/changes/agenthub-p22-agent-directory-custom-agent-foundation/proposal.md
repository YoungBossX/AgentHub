## 为什么

AgentHub 现在可以将工作路由到规划、前端、后端、审查和 PMO 协调路径，但可见的 Agent 体验仍然薄弱。用户需要一个日常使用的 Agent 目录，用于展示可用的内置 Agent、provider/runtime 状态、能力以及安全的草稿 Agent，同时避免将聊天视图变成配置界面。

P22 使多智能体名册变得可理解且可管理，同时保留现有的 AgentProfile、ProviderConfig、AgentRuntimeConfig、Target Registry、PlanValidator、Scheduler 和适配器边界。

## 变更内容

- 在工作区外壳的运行时设置 and/or 中添加一个代理目录界面。
- 将每个内置代理和草稿代理显示为联系人式资料，包含头像、名称、角色、提供商徽章、适配器类型、能力标签、支持的目标、支持的模式、安全标志和可用性。
- 添加后端 API 支持，用于列出从现有代理 profile/provider/runtime 配置注册表派生的代理目录条目。
- 为仅元数据的草稿添加安全的自定义代理草稿 CRUD：
  - 无任意 shell 命令；
  - 无危险工具权限；
  - 在验证前不写入安全的草稿代理；
  - 仅草稿代理保持禁用状态，无法执行。
- 添加针对提供商、适配器、角色、能力、支持的目标和支持的模式的代理兼容性检查。
- 让运行时设置仅选择兼容的已启用内置代理或已验证的安全资料。
- 在运行时配置响应中记录选定的 agent/profile/provider 元数据，且不暴露密钥。

## 能力

### 新能力

- `agent-directory-custom-agents`: Agent 目录列表、安全草稿元数据、兼容性检查以及运行时配置选择约束。

### 修改后的能力

- `agent-runtime-config`：运行时设置应消费该目录，以便用户能够从兼容的安全条目中选择规划器/前端/后端/审查代理。
- `daily-agent-workspace`：工作区可链接至代理目录，而无需在聊天中嵌入详细的配置控件。

## 影响

- 可能影响 `apps/api/app/agent_profiles.py`、
  `apps/api/app/agent_profile_drafts.py`、`apps/api/app/provider_configs.py`、
  `apps/api/app/agent_runtime_config.py`、`apps/api/app/main.py` 和
  `apps/api/app/schemas.py`。
- 可能影响 `apps/web/src/components/runtime-settings-page-client.tsx`、
  `apps/web/src/components/workspace-shell.tsx` 以及新的 Agent 目录 UI
  组件。
- 新增目录条目、草稿安全性、兼容性检查
  以及运行时配置选择拒绝的后端测试。
- 新增代理卡片、筛选器、安全草稿表单、运行时
  选择以及聊天界面简洁性的前端测试。

## 非目标

- 无提供商市场。
- 无 OpenCode 集成。
- 无任意 shell 命令代理。
- 无生产环境云令牌管理器。
- 无多用户代理共享或 RBAC。
- 无新的编码适配器。
- 不替换当前的调度器、目标注册表、计划验证器或护栏。
