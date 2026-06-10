## ADDED Requirements
### Requirement: 规范规划器提示词合约
系统 SHALL 为 API 规划器提供者和 Claude CLI 规划器提供者使用统一的规范规划器提示词合约。

#### Scenario: API 和 CLI 提示共享任务规划契约
- **WHEN** API 规划器提供者或 Claude CLI 规划器提供者构建其系统提示
- **THEN** 提示 MUST 描述相同的 `ConversationOutcome` 结果
- **并且** 提示 MUST 声明构建、实现、创建、开发或修改软件请求在安全时返回 `task_plan`
- **并且** 提示 MUST 包含 `task_plan` 所需的 `planDraft` 结构

#### Scenario: 提示中包含非任务示例
- **WHEN** 渲染规范提示
- **THEN** 它 MUST 包含一个返回 `assistant_reply` 的问候示例
- **并且** 它 MUST 包含一个返回 `task_plan` 的软件构建示例

#### Scenario: 提示词不会过度偏向聊天回复
- **WHEN** 渲染规范提示词
- **THEN** 该提示词MUST不得指示模型始终优先选择对话式回答而非任务计划
- **且** 该提示词MUST仅允许在`reply`字段中使用简洁回复，不得替代必需的可执行计划

### Requirement: LLM 任务计划保持已验证状态
系统 SHALL 在创建任务之前验证每个可执行的 LLM 任务计划。

#### Scenario: 有效的任务计划创建任务
- **WHEN** LLM 返回 `ConversationOutcome`，包含 `outcomeType=task_plan`
  以及一个有效的 `planDraft`
- **THEN** 系统 MUST 验证计划模式
- **并且** 系统 MUST 运行 PlanValidator
- **并且** 仅当验证通过时，任务 MUST 才会被创建

#### Scenario: 无效任务计划记录验证证据
- **WHEN** LLM 返回的 `task_plan` 包含无效模式、未知目标、
  不支持的角色、不安全路径、被拒绝的命令或 PlanValidator 失败
- **THEN** 系统 MUST 不会根据无效计划创建可执行任务
- **并且** 规划器证据 MUST 记录安全错误摘要和验证
  结果

### Requirement: 非任务 LLM 输出不得静默吞掉可执行请求
系统 SHALL 保留聊天和安全相关的非任务输出，但 SHALL 不得在清晰的、安全的编码请求被错误归类为 `assistant_reply` 时盲目返回无任务。

#### Scenario: 纯聊天保持非执行状态
- **WHEN** 用户发送问候语或询问 AgentHub 能做什么
- **且** LLM 返回 `assistant_reply`
- **THEN** 系统 MUST 创建编排器聊天回复
- **且** 系统 MUST 不创建 Task 或 TaskRun

#### Scenario: 澄清仍处于未执行状态
- **WHEN** LLM 返回 `clarification`
- **THEN** 系统 MUST 创建编排器澄清回复
- **并且** 系统 MUST 不创建 Task 或 TaskRun

#### Scenario: 拒绝与批准仍不执行
- **WHEN** LLM 返回 `refusal` 或 `approval_required`
- **THEN** 系统 MUST 创建对应的编排器回复
- **并且** 系统 MUST 不创建可执行任务，除非后续显式的批准流程创建了一个

#### Scenario: 可执行编码请求的助手回复触发兜底
- **WHEN** LLM 返回 `assistant_reply`
- **且** 用户请求并非纯聊天
- **且** 确定性路由或意图检查识别出安全的可执行编码请求
- **且** 请求具有已注册或已准备好的安全目标
- **THEN** 系统 MUST 继续执行确定性兜底或有限修复循环，而非返回 `[]`
- **且** 任何已创建的任务 MUST 被标记为兜底，而非 LLM 规划器成功

### Requirement: 确定性规划器作为兜底基线
系统 SHALL 将确定性规划器作为兜底和回归基线，而非主要能力边界。

#### Scenario: LLM 不可用时使用确定性兜底
- **WHEN** LLM 规划器被禁用、不可用、超时或返回无效输出
- **THEN** 确定性兜底可为已知的安全请求创建任务
- **并且** 兜底元数据 MUST 被记录

#### Scenario: 已知的固定模块仍存在回归问题
- **WHEN** 登录页面、待办事项、笔记、迷你 CRM 或 Breakout 回归请求已通过测试
- **THEN** 它们 MUST 仍可作为确定性或冒烟测试基线保持有效
- **并且** 它们 MUST 不能成为 AgentHub 可路由的唯一应用类型

#### Scenario: 新颖应用不会因新颖性而被拒绝
- **WHEN** 用户请求的新应用类型不属于固定模块
- **且** 该请求可基于安全目标、允许路径、允许命令及已验证风险进行落地
- **THEN** 系统 MUST 允许任务计划或兜底任务，无需为该应用类型提供硬编码模板

### Requirement: 目标注册表保持执行边界
系统 SHALL 要求对新型应用请求进行目标作用域的执行。

#### Scenario: 已准备好的外部目标支持新型应用路由
- **WHEN** 一个新型前端应用请求拥有一个已注册的活跃外部前端目标
- **THEN** 规划器或兜底路由可以创建一个限定于该目标的前端任务
- **并且** 任务 MUST 使用该目标的允许路径、拒绝路径、命令及策略元数据

#### Scenario: 缺失目标时不允许写入主机
- **WHEN** 一个新颖的应用请求指定了桌面或主机路径，但未注册或准备对应的目标
- **THEN** 系统MUST不得写入任意主机文件
- **并且** 系统MUST应要求设置目标、返回澄清说明，或使用已批准的目标注册流程

### Requirement: 规划器路由错误证据可观测
系统 SHALL 将规划器路由误分类和验证失败记录为可审计证据。

#### Scenario: 助手回复与可执行信号冲突
- **WHEN** LLM 返回 `assistant_reply`
- **并且**确定性意图检查将请求归类为可执行
- **THEN** 规划器证据 MUST 记录 LLM 结果类型、兜底原因、
  提供者 id/type/source，以及兜底创建任务时的任务 ID

#### Scenario: 兜底原因明确
- **WHEN** 兜底在非任务型 LLM 输出后创建一个任务
- **THEN** 任务计划元数据 MUST 包含 `plannerSource=fallback`
- **并且** 它 MUST 包含一个等同于 `non_task_coding_outcome` 的原因
- **并且** 它 MUST 不声称真实的 LLM 规划器成功

#### Scenario: 证据隐藏秘密
- **WHEN** 规划器证据记录在任务、任务追踪、日志或 API 响应中
- **THEN** 它 MUST 不包含原始 API 密钥、秘密、受保护的主机路径或敏感提供商凭据

### Requirement: 加固后的 P18c 库请求路由
系统 SHALL 在准备好安全的外部前端目标后，将 P18c 库管理应用提示路由为可执行的前端任务。

#### Scenario: 图书馆应用提示不会变为仅聊天模式
- **WHEN** 用户提交 P18c 图书馆管理应用请求
- **且** P18c 外部前端目标处于激活状态
- **且** 规划器 LLM 返回 `assistant_reply`
- **THEN** 系统 MUST 要么将 LLM 输出修复为已验证的 `task_plan`，要么创建经过审计的兜底前端任务
- **且** 系统 MUST 不会仅以编排器聊天消息结束

#### Scenario: 图书馆应用计划遵循内存与目标策略
- **WHEN** 图书馆管理应用的请求变为一个任务
- **THEN** 该任务 SHOULD 保留原始用户请求
- **并且** 它 MUST 保持限定在活动前端目标及允许路径范围内
- **并且** 它 MUST 不请求 backend/database，除非用户明确要求
