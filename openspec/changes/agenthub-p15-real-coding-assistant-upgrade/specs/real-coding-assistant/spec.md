## ADDED Requirements
### Requirement: LLM 规划器 v1
系统 MUST 支持针对有界真实编码请求的 `llm_v1` 规划器模式。

#### Scenario: LLM 规划器收到完整的规划上下文
- **WHEN** 针对用户请求启用了 `llm_v1` 规划
- **THEN** 规划器输入 MUST 包含原始用户请求、
  CanonicalSharedContext、目标注册表摘要、项目分析器元数据、
  最近消息、制品引用和安全护栏。

#### Scenario: LLM 规划器生成结构化 PlanDraft
- **WHEN** `llm_v1` 返回一个计划
- **THEN** 输出 MUST 被解析为结构化 PlanDraft JSON
- **并且** 它 MUST 包含任务、角色、目标、依赖关系、计划文件、
  理由、验收标准和验证预期。

#### Scenario: 在创建任务前验证 LLM 输出
- **WHEN** 收到 LLM 规划器的输出
- **THEN** PlanValidator MUST 在创建 Task 行或 TaskRun 之前对其进行验证
- **并且** 无效、不安全、不受支持或格式错误的计划 MUST 被拒绝或转换为诚实的 clarification/failure 响应。

#### Scenario: 确定性兜底保持显式
- **WHEN** `llm_v1` 被禁用、不可用或返回无效输出
- **THEN** 仅当明确适用于请求时，方可使用确定性兜底
- **且** 所选规划器模式与兜底原因 MUST 需被记录。

#### Scenario: LLM 规划器成功未被伪造
- **WHEN** 提供商认证、配额、运行时或解析阻止了 LLM 规划
- **THEN** 系统 MUST 记录精确的标准化错误
- **并且** 它 MUST 不得声称 `llm_v1` 成功。

### Requirement: 透传指令模式
系统 MUST 支持为 `llm_v1` 和 `passthrough_v1` 计划透传提供方指令。

#### Scenario: 原始请求被保留
- **WHEN** 为 `llm_v1` 或 `passthrough_v1` 任务生成提供者指令
- **THEN** 该指令 MUST 保留用户的原始请求和任务描述
- **并且** 除非明确选择确定性演示兜底，否则它 MUST 不得将任务简化为登录页面、按钮文案或演示槽模板。

#### Scenario: 目标上下文仍然存在
- **WHEN** 使用直通指令模式
- **THEN** 指令 MUST 包含目标上下文、允许路径、禁止路径、验证命令、验收标准、上游制品或交接引用，以及护栏规则。

#### Scenario: 提供商包装器仍受支持
- **WHEN** 为 Claude Code 或 Codex 生成透传指令
- **THEN** 特定于提供商的包装器可能以不同方式格式化指令
- **并且**共享的目标、合约、制品、护栏和验收数据 MUST
  在语义上仍然存在。

### Requirement: 宽松目标护栏
系统 MUST 允许在已注册目标 `allowedPaths` 内执行有意义的编码工作，同时保留受保护路径的限制。

#### Scenario: 已注册的目标路径可写
- **WHEN** 写入任务指向已注册的前端或后端目标
- **THEN** 代理可根据 AgentProfile、目标注册表、调度器和任务策略，读取和写入该目标 `allowedPaths` 内的文件。

#### Scenario: 受保护路径仍被拒绝
- **WHEN** 代理指令、命令、差异或任务尝试访问受保护路径
- **THEN** `.git`、`.env`、`.env.*`、`secrets`、`node_modules`、`.venv`、所选 target/worktree 之外的路径以及未分配的主机路径 MUST 仍被拒绝。

#### Scenario: 生产部署和网络访问仍受限
- **WHEN** 任务请求生产部署或网络访问
- **THEN** 系统根据当前策略 MUST 拒绝该请求或要求明确批准
- **且** P15 MUST 不得静默允许生产部署。

#### Scenario: 平台维护保持显式
- **WHEN** 任务会修改 AgentHub 平台代码
- **THEN** 它 MUST 需要显式的平台维护模式以及现有的
  更严格的 validation/approval 流程。

### Requirement: 项目命令策略
系统 MUST 从目标元数据中推导出允许的项目命令，并诚实地记录命令证据。

#### Scenario: 命令来自目标配置
- **WHEN** 任务需要验证命令
- **THEN** 允许的命令 MUST 可源自目标注册表、项目分析器或显式目标配置。

#### Scenario: 支持通用配置命令
- **WHEN** 已注册的目标配置声明了通用项目命令，例如
  test、build、lint、dev、check、`pnpm`、`npm` 或 `pytest` 命令
- **THEN** 系统可以仅允许针对所选目标执行这些命令，并且
  仅在配置的命令策略范围内执行。

#### Scenario: 命令结果是诚实的证据
- **WHEN** 验证命令运行
- **THEN** 标准输出、标准错误、退出码、命令标识、目标 ID 和状态
  MUST 被记录为证据
- **并且** 失败的命令 MUST 不得被表示为通过。

### Requirement: 规划器理由与任务审查元数据
系统 MUST 为实际编码计划暴露有用的计划审查元数据。

#### Scenario: 计划依据可见
- **WHEN** 通过 `llm_v1` 或 `passthrough_v1` 创建计划
- **THEN** 规划器模式、计划依据、任务分解、分配角色、目标、
  依赖项、计划文件、验收标准和验证
  预期 MUST 可通过 API 或 UI 界面获取。

#### Scenario: P15 阶段计划审查为只读
- **WHEN** 用户检查计划审查元数据
- **THEN** P15 阶段可显示计划与任务分解
- **且** 除非现有安全 UI 操作已支持调整，否则 MUST 不需要新的交互式计划编辑器。

### Requirement: 打砖块游戏真实编码冒烟测试
系统 MUST 将打砖块/砖块消除游戏请求作为最终 P15
验收目标。

#### Scenario: Breakout 请求创建真实编码计划
- **WHEN** 用户询问 `帮我在当前前端项目里实现一个 Breakout / 打砖块游戏，要求可以用键盘控制挡板，球能反弹，能击碎砖块，有得分、胜利/失败状态和重新开始按钮。`
- **THEN** 规划器 MUST 为已注册的前端目标生成一个 `llm_v1` 或 `passthrough_v1` 前端任务
- **并且** 它 MUST 不使用硬编码的 Breakout 模板或脚本化 Breakout 实现。

#### Scenario: Breakout 提供者指令保留请求
- **WHEN** Breakout 前端任务被执行
- **THEN** 提供者指令 MUST 保留原始的 Breakout 请求
  和验收标准。

#### Scenario: 成功声明需要真实提供商执行
- **WHEN** P15 声明 Breakout 实现成功
- **THEN** 真实的 ClaudeCodeAdapter 或 CodexAdapter 运行 MUST 已成功完成
- **且** ScriptedMock MUST 不得用于声明 Breakout 成功。

#### Scenario: 突破证据已完成
- **WHEN** 突破烟雾测试成功
- **THEN** 系统 MUST 记录差异、审查、build/check 命令证据、
  预览和预发布部署证据。

#### Scenario: Breakout 可在浏览器中游玩
- **WHEN** 打开 Breakout 预览
- **THEN** 游戏 MUST 支持键盘挡板控制、球体运动、
  反弹行为、砖块 collision/destruction、得分、win/lose 状态以及
  重启按钮。

#### Scenario: 提供商阻塞被如实报告
- **WHEN** 真实的 Claude Code 或 Codex 执行被认证、配额、运行时或环境阻塞
- **THEN** 确切的标准化错误 MUST 被记录
- **并且** P15 MUST 不得声称突破成功。

### Requirement: P15 基线保留
系统 MUST 在添加真实编码助手能力的同时，保留 P6-P14 基线。

#### Scenario: 现有演示兜底仍可正常工作
- **WHEN** 使用了一个旧的确定性演示请求
- **THEN** 确定性演示兜底和 ScriptedMock 可靠性行为
  MUST 保持可用且清晰标注。

#### Scenario: 目标与提供者策略保持活跃
- **WHEN** P15 真实编码任务运行
- **THEN** 目标注册表、外部项目工作区模式、调度器锁、
  恢复、提供者分配矩阵、代理选择策略、
  CanonicalSharedContext、提供者指令适配器、审查、预览以及
  预发布部署行为 MUST 保持可运行状态。
