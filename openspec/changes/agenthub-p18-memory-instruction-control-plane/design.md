## 背景

AgentHub 现在有了清晰的运行时拆分：

```text
user message
-> Conversation Router / Planner LLM
-> ConversationOutcome
-> PlanValidator
-> Scheduler
-> Frontend / Backend / Review coding agents
```

P17b 添加了 API Planner 提供程序，P17c 将 Planner/Frontend/Backend/Review 运行时配置移入设置。P9 到 P17 还添加了目标注册表、外部工作区模式、调度器、恢复、规范上下文、任务追踪、diff/review/preview/staging 证据以及目标感知执行。

剩余的差距在于指令一致性。规划器可能接收一条系统提示，Claude Code 可能读取 `CLAUDE.md` 或自动记忆，Codex 可能读取 `AGENTS.md`，审查可能接收另一条指令块，而目标 Registry/PlanValidator 可能强制执行一个独立的现实。P18 应使 AgentHub 成为记忆和指令的权威来源，同时在记忆系统之外保留硬性护栏。

## 目标 / 非目标

**目标：**
- 使 AgentHub 规范记忆成为项目指令和跨代理记忆的唯一真实来源。
- 为 `AGENTS.md`、`CLAUDE.md`、规划器、Claude Code、Codex 和审查代理生成 Compile/export 确定性指令制品。
- 添加会话级记忆快照，以便 session/task 链中的每个代理都能基于同一记忆版本进行审计。
- 添加范围感知的记忆生命周期、评分、检索、写入策略、提示注入防护和外部记忆建议处理。
- 添加记忆管理 UI 和可衡量的评估标准。
- 保留 P6-P17c 基线及现有运行时提供程序设置。

**非目标：**
- 在 P18 阶段不构建完整的图记忆、强制向量检索或 RRF 融合。
- 不允许未经用户审查的自动长期学习。
- 不添加多用户共享记忆、提供商市场、云密钥管理器、生产部署或新的编码适配器。
- 不允许记忆绕过目标注册表、计划验证器、护栏、运行时提供商配置或平台维护审批。

## 核心决策

### AgentHub 规范内存是事实来源

AgentHub 应维护规范化的记忆条目，并从中编译指令输出口。`AGENTS.md` 和 `CLAUDE.md` 成为保留用户自定义区域的 generated/managed 制品。

外部代理记忆，包括 Claude Code 自动记忆或 Codex global/repo 指令，应仅作为建议输入处理。它可能创建 `pending_review` 记忆候选和冲突，但不得自动成为活动记忆或覆盖 AgentHub 规范记忆。

### 记忆并非护栏

记忆可能会说“优先使用中文回复”或“在前端更改后运行 `pnpm check`”。它不得强制执行安全策略。禁止路径、机密保护、平台维护模式、生产部署禁止、目标写入权限以及命令策略仍保留在目标注册表、计划验证器、防护栏、调度器和运行时执行策略中。

### 执行前快照

每个会话都应获得一个 `memorySnapshotId`。规划器证据、TaskRun 元数据、任务追踪和审查证据应在有用时引用该快照。正在运行的 TaskRun 不得静默切换快照。内存变更默认应影响新会话。现有会话仅能通过显式刷新操作进行刷新，该操作需记录旧快照和新快照。

### 受管 Markdown 文件职责

P18 应支持或规划以下文件：

| 文件 | 职责 |
|---|---|
| `AGENTS.md` | 跨编码代理项目指令出口。包含一个 AgentHub 管理的块以及保留的用户自定义块。供 Codex 和其他编码代理使用。 |
| `CLAUDE.md` | 简短的 Claude Code 桥接。尽可能使用 References/imports `AGENTS.md`，避免重复大型规则。 |
| `.agenthub/memory/project.md` | 项目结构、技术栈、命令、工作流规则。 |
| `.agenthub/memory/user-preferences.md` | 用户语言、风格、验证和文档偏好。 |
| `.agenthub/memory/decisions.md` | 架构决策、阶段结论和替代记录。 |
| `.agenthub/memory/patterns.md` | 失败模式、常见修复和已知回归陷阱。 |
| `.agenthub/memory/feedback.md` | 用户对代理行为的反馈。 |
| `.agenthub/memory/sessions/YYYY-MM-DD.md` | 会话摘要和每日任务日志。 |

### 热内存预算

P18 应定义初始实际限制，并强制执行 summarization/archive 行为，而非仅追加增长：

| 文件 / 区域 | 初始预算 |
|---|---:|
| `AGENTS.md` 托管块 | 8k-12k 字符 |
| `CLAUDE.md` | 1k-3k 字符 |
| `project.md` | 6k-10k 字符 |
| `user-preferences.md` | 1.5k-3k 字符 |
| `decisions.md` | 8k-12k 字符 |
| `patterns.md` | 8k-15k 字符 |
| `feedback.md` | 5k-8k 字符 |
| `sessions/YYYY-MM-DD.md` | 20k-50k 字符 |

如果文件超出预算，AgentHub 应总结、归档或降级低价值记忆。不应优先删除。

### 生命周期与驱逐

记忆项状态：

- `active`
- `pending_review`
- `warm`
- `archived`
- `rejected`
- `deleted`

驱逐基于降级机制。项目规则和用户偏好不应仅因时间因素被驱逐。模式记忆可能因低使用率、时效性、低帮助度、冲突或高令牌成本而被降级。会话摘要可被压缩并归档。被取代的记忆应附带 `supersededBy` 元数据进行归档。

### 评分模型

记忆检索和hot/default包含应基于以下评分：

- 重要性
- 信任等级
- 使用频率
- 时效性
- 近期成功率
- 特异性
- Token 成本
- 冲突惩罚
- 陈旧惩罚

分数应决定记忆是 hot/default、仅检索、热记忆还是仅归档。

### 内存写入策略

显式用户记忆写入可能会创建记忆候选：

- "记住这个"
- "以后都这样"
- "写入项目规则"
- "写进 user-preferences.md"

构建失败、审查发现、部署失败和重复修复中的自动系统发现可能仅创建 `pending_review` 候选。普通聊天不得自动成为长期记忆。文件内容或代码注释中的"记住这个"不得自动创建记忆。

### 提示注入防护

来自文件、工具输出、提供者输出、Claude/Codex建议或检索内容的记忆写入必须进入`pending_review`或`rejected`，而非`active`。在长期项目规则、用户偏好和跨代理指令生效前，需要获得用户确认。

### 检索 v1

P18 检索应有意保持适度：

- SQLite FTS5 或 BM25 风格的关键词检索；
- 范围筛选；
- 目标筛选；
- 角色筛选；
- 状态筛选；
- 时间衰减；
- importance/trust 评分。

嵌入检索、RRF融合和知识图谱检索是未来的增强功能。

### 上下文注入策略

Planner LLM 接收：

- 用户偏好；
- 项目摘要；
- 当前会话/任务摘要；
- 相关检索记忆；
- 相关制品证据。

Claude Code 收到：

- `AGENTS.md` / `CLAUDE.md` 指令；
- 任务指令；
- 目标边界；
- 选定的相关记忆片段；
- 验证预期。

Codex 收到：

- `AGENTS.md` 指令；
- 任务指令；
- 目标边界；
- 选定的相关记忆片段；
- 验证预期。

审查代理接收：

- diff（差异）；
- review checks（审查检查）；
- project rules（项目规则）；
- relevant pattern memory（相关模式记忆）。

普通聊天不得调用编码代理。

### 外部 Agent 内存管理

AgentHub 可以扫描：

- 仓库 `AGENTS.md`；
- 仓库 `CLAUDE.md`；
- Claude Code 本地自动记忆；
- Codex 全局或仓库指令。

扫描到的记忆成为外部建议。它不得自动覆盖规范记忆。应检测冲突并向用户显示。

### 一致性证据

P18 应在适当位置记录这些 identifiers/hashes/versions：

- `memorySnapshotId`；
- `agentsMdHash`；
- `claudeMdHash`；
- `projectMemoryVersion`；
- `userPreferenceVersion`；
- `targetRegistryVersion`；
- `runtimeConfigVersion`；
- `contextPackHash`。

这些内容应酌情出现在 TaskRun 证据、规划器证据、任务追踪或制品元数据中。

## 风险 / 权衡

- 记忆系统范围可能膨胀 -> 缓解措施：将 P18 拆分为小型、可评估的任务，并保持检索 v1 基于关键词。
- 生成的 `AGENTS.md` 可能覆盖用户编辑 -> 缓解措施：使用受管理的块标记并保留用户自定义块。
- Claude/Codex 私有记忆可能与 AgentHub 规则冲突 -> 缓解措施：作为建议扫描并要求确认。
- 通过文件或提供者输出进行的提示注入可能创建持久规则 -> 缓解措施：pending/rejected 默认设置，并在激活长期记忆时要求用户确认。
- 快照元数据可能增加噪音 -> 缓解措施：在任务轨迹中暴露摘要，在证据元数据中暴露详细哈希值。

## 评估指标

P18 应定义有针对性的评估：

- 偏好召回率
- 跨智能体一致性率
- 记忆精确度@5
- 过期记忆注入次数
- 提示注入写入拦截率
- 快照一致性率
- 任务成功差值
- 变更日志偏好启用时的变更日志缺失率
