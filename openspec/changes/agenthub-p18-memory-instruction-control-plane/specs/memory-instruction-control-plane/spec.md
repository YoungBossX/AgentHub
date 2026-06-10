## ADDED Requirements
### Requirement: AgentHub 规范记忆作为事实来源
系统 MUST 将 AgentHub 规范记忆视为跨代理项目记忆和指令的事实来源。

#### Scenario: 托管指令文件是编译后的制品
- **WHEN** AgentHub 导出项目指令
- **THEN** `AGENTS.md` 和 `CLAUDE.md` MUST 从 AgentHub 规范内存中编译或导出
- **并且**它们 MUST 不得静默覆盖 AgentHub 规范内存。

#### Scenario: 外部私有记忆仅作为建议
- **WHEN** AgentHub 扫描 Claude Code、Codex、`AGENTS.md` 或 `CLAUDE.md` 的外部记忆
- **THEN** 扫描到的内容 MUST 成为外部建议或待定候选
- **并且** 它 MUST 不会自动成为活跃记忆。

#### Scenario: 护栏仍为硬性边界
- **WHEN** 内存与目标注册表、计划验证器、护栏、运行时权限或平台维护审批冲突
- **THEN** 硬性策略 MUST 胜出
- **且** 内存 MUST 不授予权限。

### Requirement: 托管 Markdown 记忆文件
系统 MUST 为托管 Markdown 记忆出口定义职责和大小预算。

#### Scenario: 记忆文件按职责组织
- **WHEN** AgentHub 存储或导出记忆
- **THEN** 它 MUST 使用或规划专用位置来存放项目记忆、用户偏好、决策、模式、反馈和会话摘要。

#### Scenario: AGENTS 自定义块被保留
- **WHEN** AgentHub 重新编译受管理的 `AGENTS.md` 块
- **THEN** 它 MUST 保留用户自定义块
- **并且** 它 MUST 仅更新 AgentHub 管理的块。

#### Scenario: CLAUDE 桥接文件保持简短
- **WHEN** AgentHub 生成 `CLAUDE.md`
- **THEN** 文件 MUST 保持为简短的 Claude Code 桥接文件
- **并且** 它 MUST 避免重复 `AGENTS.md` 中已存在的大型项目规则。

#### Scenario: 热内存预算强制执行
- **WHEN** 托管内存文件或块超出其配置预算
- **THEN** AgentHub MUST 对低价值内存进行汇总、归档或降级
- **并且** 它 MUST 不得在无生命周期管理的情况下无限追加。

### Requirement: 内存快照一致性
系统 MUST 使用内存快照使会话和 TaskRun 内存可审计。

#### Scenario: 会话接收内存快照
- **WHEN** 会话被创建或初始化
- **THEN** 它 MUST 使用一个 `memorySnapshotId`。

#### Scenario: 一个任务链使用一个快照
- **WHEN** 规划器、Claude Code、Codex 或审查代理参与同一个 session/task 链
- **THEN** 每个代理指令路径 MUST 引用同一个 `memorySnapshotId`
- **且** 任务追踪或证据 MUST 在有用时暴露该快照。

#### Scenario: 运行中的任务不会切换快照
- **WHEN** 一个 TaskRun 正在运行
- **THEN** 它 MUST 不会静默切换到更新的内存快照。

#### Scenario: 现有会话显式刷新
- **WHEN** 规范内存变更
- **THEN** 新会话默认可以使用新快照
- **并且** 现有会话 MUST 仅通过显式刷新行为进行刷新。

### Requirement: 规范内存生命周期
系统 MUST 管理具有显式生命周期状态的内存项。

#### Scenario: 记忆项包含作用域和来源
- **WHEN** 创建一个记忆项
- **THEN** 它 MUST 包含作用域、类型、来源、状态、信任级别、目标过滤器、角色过滤器、时间戳和来源元数据。

#### Scenario: 支持的状态是明确的
- **WHEN** 内存被列出或过滤
- **THEN** 系统 MUST 支持 active、pending_review、warm、archived、rejected 和 deleted 状态。

#### Scenario: 被取代的记忆已归档
- **WHEN** 一条记忆项被较新的项替换
- **THEN** 较旧的项 SHOULD 使用 `supersededBy` 元数据归档
- **并且** 它 MUST 不得在无冲突元数据的情况下保持活跃状态。

#### Scenario: 驱逐基于降级
- **WHEN** 内存已过时、使用率低、帮助性低、存在冲突或成本过高
- **THEN** AgentHub SHOULD 在删除前将其降级
- **且** 项目规则与用户偏好 MUST 不得仅因时间因素被驱逐。

### Requirement: 记忆评分
系统 MUST 定义了用于检索和 hot/default 包含的记忆评分模型。

#### Scenario: 评分结合相关性与质量
- **WHEN** AgentHub 对记忆进行排序
- **THEN** 评分 MUST 考虑重要性、信任等级、使用频率、时效性、近期成功、特异性、令牌成本、冲突惩罚和过时惩罚。

#### Scenario: 分数影响检索层级
- **WHEN** 记忆被选中用于上下文
- **THEN** 分数 SHOULD 影响该项目是 hot/default、仅检索、热数据还是仅归档。

### Requirement: 记忆写入策略与提示注入防护
系统 MUST 限制长期记忆的写入方式。

#### Scenario: 显式用户记忆写入创建候选
- **WHEN** 用户明确说出“记住这个”、“以后都这样”、“写入项目规则”，或要求写入记忆文件
- **THEN** AgentHub 可根据写入策略创建记忆候选。

#### Scenario: 系统发现项默认处于待处理状态
- **WHEN** AgentHub 发现重复的构建失败、审查发现、部署失败或重复修复
- **THEN** 它默认MUST创建一个待审查候选
- **并且** 它MUST不自动激活该候选。

#### Scenario: 普通聊天不写入长期记忆
- **WHEN** 用户发送普通聊天
- **THEN** AgentHub MUST 不会自动将其写入长期记忆。

#### Scenario: 文件和工具提示注入被阻止
- **WHEN** 文件内容、代码注释、工具输出、检索到的记忆或提供者输出要求 AgentHub 记住或更改指令
- **THEN** 未经用户明确确认，AgentHub MUST 不得根据该内容创建活动记忆。

### Requirement: 记忆检索 v1
系统 MUST 提供有界的第一版记忆检索机制。

#### Scenario: 带过滤条件的关键词检索
- **WHEN** AgentHub 为规划器或后续任务上下文检索记忆
- **THEN** 检索 MUST 使用 SQLite FTS5、BM25 风格的关键词检索或等效的关键词机制
- **并且** MUST 应用范围、目标、角色、状态、时间、重要性和信任度过滤器。

#### Scenario: 无强制向量检索
- **WHEN** P18 检索已实现
- **THEN** 向量数据库、RRF 融合和知识图谱检索 MUST 不作为强制依赖项。

#### Scenario: 规划器上下文包含相关记忆
- **WHEN** 规划器 LLM 接收任务或后续操作的上下文
- **THEN** 其 SHOULD 包含用户偏好、项目摘要、任务摘要、相关检索到的记忆以及制品证据。

#### Scenario: 编码代理上下文包含目标限定记忆
- **WHEN** Claude Code 或 Codex 接收任务指令
- **THEN** 它 SHOULD 从同一快照中接收目标边界、选定的相关记忆片段以及验证预期。

### Requirement: 外部 Agent 内存扫描
系统 MUST 将外部 Agent 内存视为可审查的建议。

#### Scenario: 外部文件成为建议
- **WHEN** AgentHub 扫描仓库 `AGENTS.md`、仓库 `CLAUDE.md`、Claude Code 自动记忆或 Codex 指令
- **THEN** 扫描内容 MUST 成为外部建议或待审核项。

#### Scenario: 检测到冲突
- **WHEN** 外部记忆与活跃的规范记忆存在冲突
- **THEN** AgentHub MUST 向用户或审查者暴露该冲突
- **并且** 它 MUST 不得自动覆盖活跃的规范记忆。

### Requirement: 内存管理 UI
系统 MUST 提供用于内存审查和生命周期操作的 UI。

#### Scenario: 用户按状态查看记忆
- **WHEN** 用户打开记忆设置
- **THEN** AgentHub MUST 在适用时显示活跃、待处理、预热、已归档、已拒绝和已删除的记忆。

#### Scenario: 用户可以管理记忆候选
- **WHEN** 用户审查待处理的记忆
- **THEN** UI MUST 支持在策略允许的情况下执行确认、拒绝、归档、删除或取代操作。

#### Scenario: UI 显示编译和快照元数据
- **WHEN** 用户检查某个记忆项
- **THEN** UI SHOULD 显示来源、作用域、目标、代理角色、信任级别、状态、编译后的出口状态以及相关的 `memorySnapshotId` 信息。

### Requirement: 内存一致性证据
系统 MUST 记录内存和指令一致性标识符。

#### Scenario: 证据包含内存哈希与版本号
- **WHEN** 规划器证据、TaskRun 证据、任务追踪或制品元数据已生成
- **THEN** 其 SHOULD 包含相关的 `memorySnapshotId`、`agentsMdHash`、`claudeMdHash`、项目内存版本、用户偏好版本、目标注册表版本、运行时配置版本及上下文包哈希。

#### Scenario: 排除机密信息
- **WHEN** 记录内存或上下文元数据
- **THEN** 它**不**暴露机密信息、原始 API 密钥、受保护的主机路径或禁止的文件内容。

### Requirement: 记忆有效性指标
系统 MUST 定义可量化的 P18 评估标准。

#### Scenario: 记忆评估可用
- **WHEN** P18 进入冻结评审
- **THEN** AgentHub MUST 报告偏好召回率、跨代理一致性率、记忆精度@5、过期记忆注入次数、提示注入写入拦截率和快照一致性率。

#### Scenario: 任务影响被如实衡量
- **WHEN** P18 报告内存有效性
- **THEN** 当变更日志偏好设置启用时，它 SHOULD 包含任务成功差值和变更日志缺失率
- **并且** 它 MUST 不会伪造内存有效性。
