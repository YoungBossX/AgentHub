## ADDED Requirements
### Requirement: 编码 TaskRun 通过 Provider Gateway 解析 provider
系统 SHALL 在执行编码适配器前通过 Provider Gateway 生成 provider 解析方案，而不是让 Durable Run Engine、endpoint 或零散 helper 直接决定具体适配器。

#### Scenario: 默认编码 provider 被解析
- **WHEN** Durable Run Engine 准备执行一个编码 TaskRun
- **AND** 用户没有显式指定 provider
- **THEN** Provider Gateway MUST 基于工作区运行时配置、角色、目标、模式和能力选择 provider
- **AND** 系统 MUST 记录所选 provider 和选择原因

#### Scenario: 显式 provider 请求被验证
- **WHEN** 用户或任务请求一个具体编码 provider
- **THEN** Provider Gateway MUST 验证该 provider 是否存在、可用于编码适配器、兼容当前 role/target/mode/capability
- **AND** 不兼容时 MUST 拒绝或选择被策略允许的兜底方案
- **AND** 拒绝原因 MUST 被记录为安全证据

#### Scenario: Planner provider 不进入编码 gateway
- **WHEN** 工作区同时配置 Planner provider 和编码 provider
- **THEN** Provider Gateway MUST 只解析 ClaudeCodeAdapter、CodexAdapter、ScriptedMockAdapter 等编码适配器 provider
- **AND** Planner provider MUST 不作为编码适配器候选

### Requirement: Provider Registry 暴露安全编码 provider 元数据
系统 SHALL 为编码 providers 提供安全 registry 视图，供解析、健康、兼容性和诊断使用。

#### Scenario: Registry 包含现有编码适配器
- **WHEN** Provider Gateway 加载 registry
- **THEN** registry MUST 包含 ClaudeCodeAdapter、CodexAdapter 和 ScriptedMockAdapter 对应的 provider
- **AND** registry MUST 不要求新增适配器才能满足 V2.2

#### Scenario: Registry 区分真实 provider 与 mock 兜底
- **WHEN** registry 返回 ScriptedMockAdapter 元数据
- **THEN** 它 MUST 标记为 fallback/mock provider
- **AND** 它 MUST 不被描述为真实 Claude 或 Codex provider

#### Scenario: Registry 不泄露秘密
- **WHEN** registry 元数据被写入日志、API 响应或任务追踪
- **THEN** 元数据 MUST 不包含原始 API 密钥、令牌、凭证、秘密或受保护的主机路径

### Requirement: 健康探测贴近实际启动路径
系统 SHALL 为每个编码 provider 提供健康检查或探测，且结果必须与实际适配器启动路径对齐。

#### Scenario: 真实 provider 健康检查
- **WHEN** Provider Gateway 检查 Claude Code 或 Codex provider
- **THEN** 健康结果 MUST 反映配置、CLI 可用性和安全启动前探测的结果
- **AND** 未知或不可用 MUST 被诚实记录

#### Scenario: 兜底可用不代表真实 provider 健康
- **WHEN** Claude Code 或 Codex 健康状态为不可用
- **AND** ScriptedMockAdapter 可用
- **THEN** 系统 MUST 不将 Claude Code 或 Codex 标记为健康
- **AND** 系统 MAY 将 ScriptedMockAdapter 作为兜底候选记录

#### Scenario: 健康证据被脱敏
- **WHEN** 健康探测产生 stderr、路径或配置摘要
- **THEN** 系统 MUST 对秘密、令牌、API 密钥和受保护主机路径进行脱敏处理
- **AND** 只保存安全摘要

### Requirement: Provider Gateway 控制并发
系统 SHALL 在启动编码适配器前检查 provider/global 并发限制。

#### Scenario: 容量可用时启动 provider
- **WHEN** 所选 provider 未超过并发限制
- **THEN** Provider Gateway MUST 在启动前获取容量
- **AND** TaskRun 结束后 MUST 释放容量

#### Scenario: 容量不可用时不启动适配器
- **WHEN** 所选 provider 或全局编码运行容量已耗尽
- **THEN** Provider Gateway MUST 不启动适配器子进程
- **AND** 系统 MUST 记录容量阻塞证据

#### Scenario: 释放幂等
- **WHEN** TaskRun finalizer、恢复或延迟事件多次释放同一容量
- **THEN** 释放操作 MUST 保持幂等
- **AND** 不得让并发计数变成负数或错误允许过量运行

### Requirement: 速率限制占位符记录限流状态
系统 SHALL 建立 provider 速率限制占位符，用于记录和传播限流状态，即使本阶段不实现完整外部配额系统。

#### Scenario: provider 报告速率限制
- **WHEN** 适配器或健康探测返回可识别的速率限制错误
- **THEN** Provider Gateway MUST 将其分类为 `rate_limit`
- **AND** 系统 SHOULD 记录 provider、窗口摘要、下次可用时间或未知

#### Scenario: 占位符不执行外部计费
- **WHEN** Provider Gateway 使用速率限制占位符
- **THEN** 系统 MUST 不要求 provider 市场、计费、令牌预算或外部配额同步
- **AND** 它 MUST 保留后续扩展所需的证据字段

### Requirement: 断路器阻止冷却中的 provider
系统 SHALL 为编码 providers 提供断路器，避免连续不可恢复 provider 失败后继续启动适配器。

#### Scenario: 连续 provider 失败打开断路器
- **WHEN** provider 连续出现 auth、quota、rate_limit 或 unavailable 类失败并达到策略阈值
- **THEN** 断路器 SHOULD 打开该 provider 的冷却期
- **AND** 系统 MUST 记录断路器打开证据

#### Scenario: 打开的断路器阻止启动
- **WHEN** 所选 provider 的断路器处于打开冷却期
- **THEN** Provider Gateway MUST 不启动该 provider 适配器
- **AND** 系统 MUST 记录断路器阻塞原因和冷却信息

#### Scenario: 本地防护不误开 provider 断路器
- **WHEN** TaskRun 因防护或脏工作区分类失败
- **THEN** 断路器 SHOULD 不将该失败计为 provider 健康失败
- **AND** 系统 MUST 保留本地安全失败证据

### Requirement: Provider 错误分类统一失败分类
系统 SHALL 将编码 provider 和 gateway 失败归类到统一分类体系。

#### Scenario: 失败被分类
- **WHEN** 适配器、健康探测、并发限制器、断路器或 gateway 控制路径失败
- **THEN** ProviderErrorClassifier MUST 产生类别、provider id、可重试、可兜底、可触发断路器、用户消息和安全证据

#### Scenario: 分类体系覆盖核心类别
- **WHEN** 失败被分类
- **THEN** 类别 MUST 是 auth、quota、rate_limit、timeout、format、tool、guardrail、dirty_worktree、unavailable 或 unknown 之一

#### Scenario: 未知不被包装成成功
- **WHEN** 系统无法识别 provider 失败
- **THEN** 类别 MUST 为 unknown
- **AND** TaskRun MUST 不被标记为真实 provider 成功

### Requirement: 兜底策略可审计
系统 SHALL 使用明确的 FallbackPolicy 来决定是否从失败或不可用的 provider 切换到 fallback。

#### Scenario: fallback 被选择
- **WHEN** 选中的 provider 因健康度、容量、熔断或错误分类无法执行
- **AND** FallbackPolicy 允许 fallback
- **THEN** Provider Gateway MUST 记录原始 provider、fallback provider、触发类别和原因
- **AND** fallback provider MUST 重新经过兼容性和安全检查

#### Scenario: ScriptedMock fallback 明确标记
- **WHEN** Provider Gateway 使用 ScriptedMockAdapter 执行 fallback
- **THEN** TaskRun evidence MUST 明确标记 `fallback=true` 和 `mock=true`
- **AND** evidence MUST NOT 声称 Claude Code 或 Codex 成功

#### Scenario: fallback 不覆盖原始失败
- **WHEN** 原始 provider 失败后 fallback 成功
- **THEN** 系统 MUST 同时保留原始 provider failure evidence 和 fallback success evidence
- **AND** mission trace MUST 能展示最终执行 adapter 与原始失败 provider 不同

#### Scenario: fallback 不被允许时诚实失败
- **WHEN** 选中的 provider 失败
- **AND** FallbackPolicy 不允许 fallback 或没有可用 fallback
- **THEN** TaskRun MUST 进入诚实失败状态
- **AND** 系统 MUST 记录无 fallback 的原因

### Requirement: Provider Gateway 与 Durable Run Engine 分工明确

系统 SHALL 保持 Durable Run Engine 和 Provider Gateway 的职责分离。

#### Scenario: RunWorker 通过 gateway 启动 coding adapter
- **WHEN** RunWorker 执行 coding TaskRun
- **THEN** RunWorker SHOULD 调用 ProviderGateway 获取 resolution 和 adapter execution result
- **AND** 不应在 endpoint 或 RunWorker 内散落 provider fallback 判断

#### Scenario: RunSupervisor 仍负责进程中断与超时
- **WHEN** coding adapter 已被 gateway 启动
- **THEN** RunSupervisor MUST 继续负责 interrupt、terminate、kill、max runtime timeout 和 idle timeout
- **AND** Provider Gateway MUST 保留 provider 分类和 fallback 证据

#### Scenario: Artifact Collector 不被 gateway 扩大范围
- **WHEN** coding adapter 执行结束
- **THEN** diff、review、preview、deploy evidence SHOULD 继续由 ArtifactCollector/Finalizer 处理
- **AND** Provider Gateway MUST NOT 变成 preview/deploy 执行器

### Requirement: MissionTrace 记录 Provider Gateway 证据

系统 SHALL 在任务追踪或 TaskRun evidence 中展示 Provider Gateway 的关键诊断信息。

#### Scenario: 追踪显示 provider resolution
- **WHEN** 用户查看 mission trace 或 TaskRun 详情
- **THEN** 系统 SHOULD 显示选中的 provider、选择原因、被拒绝的候选和 fallback 候选的安全摘要

#### Scenario: 追踪显示 gateway 控制状态
- **WHEN** TaskRun 受健康度、容量、速率限制占位符或熔断器影响
- **THEN** 系统 SHOULD 显示对应状态、原因和下一步建议的安全摘要

#### Scenario: 追踪显示 fallback chain
- **WHEN** TaskRun 使用 fallback
- **THEN** 系统 SHOULD 显示原始 provider、fallback provider、触发类别、mock/fallback 标记和最终 adapter

### Requirement: V2.2 保留现有 demo 与安全边界

系统 SHALL 在引入 Provider Gateway 时保留当前本地单用户 demo、安全边界和 adapter 集合。

#### Scenario: 不新增 adapter
- **WHEN** V2.2 实现 Provider Gateway
- **THEN** 系统 MUST 保留 CodexAdapter、ClaudeCodeAdapter 和 ScriptedMockAdapter
- **AND** 系统 MUST NOT 要求新增 HumanAgentAdapter、Docker sandbox、provider marketplace 或 Codex cloud wrapper

#### Scenario: 不改变 demo app boundary
- **WHEN** gateway 执行 coding provider
- **THEN** agent-modified demo app boundary MUST 仍是 Vite React
- **AND** provider execution MUST 继续遵守受保护路径和命令 allowlist

#### Scenario: 不伪造真实 Codex 或 Claude 成功
- **WHEN** CodexAdapter 或 ClaudeCodeAdapter auth、quota、rate、timeout、tool、format 或 unavailable 失败
- **THEN** 系统 MUST 记录真实失败类别
- **AND** 系统 MUST NOT 用 ScriptedMockAdapter 结果覆盖为真实 provider 成功
