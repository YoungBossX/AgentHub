## 为什么

P14 冻结了 provider/profile 基础，但 AgentHub 仍然感觉比底层的 Claude Code 和 Codex 编码代理更受限制。下一个差距在于执行质量：规划和指令路径仍然会将合理的编码请求过度改写为狭窄的演示模板指令，或者拒绝本应在注册目标内安全执行的工作。

P15 将 AgentHub 升级为更真实的编码助手，同时保留目标注册表、调度器、提供者策略和制品证据护栏。最终验收目标是在已注册的前端目标中实现一个可玩的 Breakout / 打砖块游戏，且不包含硬编码的 Breakout 规划器模板。

## 变更内容

- 新增 LLM 规划器 v1 (`llm_v1`)，该规划器利用原始用户请求、CanonicalSharedContext、目标注册表、项目分析器数据、最近消息、制品引用和护栏，生成经过验证的 PlanDraft JSON。
- 为 `llm_v1` / `passthrough_v1` 计划新增直通指令模式，使提供方指令保留原始用户请求和任务描述，而非将工作简化为旧的演示槽重写。
- 扩展目标作用域护栏，允许在已注册目标 `allowedPaths` 内执行有意义的 read/write 工作，同时继续拒绝 `.git`、`.env`、密钥、依赖目录、主机路径、生产部署及未经批准的网络访问。
- 新增基于目标的项目命令策略，用于配置的 test/build/lint/dev 命令及诚实的命令证据。
- 公开规划器推理过程、分配的角色、目标、依赖项、计划文件及验收标准，作为任务审查元数据。
- 演练一个真实的编码冒烟测试：用户要求 AgentHub 在已注册的前端目标中实现一个打砖块/弹球游戏。
- 保留确定性演示兜底、ScriptedMock 兜底诚实性、调度器语义、提供方分配、目标锁、review/preview 及暂存部署行为。

## 能力

### 新能力

- `real-coding-assistant`: LLM Planner v1，透传提供者指令，
  目标作用域内的宽松护栏、项目命令策略、规划器
  rationale/task 审查元数据，以及 Breakout 游戏真实编码冒烟测试。

### 修改后的能力

- 现有编排器的规划和指令行为已扩展了
  `llm_v1` / `passthrough_v1` 模式，同时确定性演示兜底仍
  可用于旧的演示流程。

## 影响

- 后端：
  - planner 服务新增基于 LLM 的规划模式及经过验证的 PlanDraft 输出契约；
  - 指令 builder/adapters 保留用户对直通计划的请求；
  - 护栏和命令策略路径变为目标感知，且不再强绑定演示模板；
  - task/run 元数据记录规划模式、理由、计划文件及验收标准。
- 前端：
  - plan/task 界面可展示规划理由、目标、依赖、计划文件及验收标准元数据；
  - P15 阶段无需进行大规模 UI 重构或引入交互式计划编辑器。
- 运行时：
  - ClaudeCodeAdapter 和 CodexAdapter 仍为实际编码执行器；
  - ScriptedMock 仅作为兜底方案，不得用于声称 Breakout 成功；
  - P6-P14 基线、目标注册表、调度器 locks/recovery、CanonicalSharedContext、提供者分配、审查、预览及预发布部署证据必须保持完整。
