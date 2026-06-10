## 背景

P18 将 AgentHub 规范记忆确立为指令的真实来源。
P18b 增加了确定性的记忆有效性演练，并表明在受控场景下，记忆检索和安全指标可以得到改善。
剩余的差距在于实时证据：必须通过真实的 ClaudeCodeAdapter 或 CodexAdapter 运行来证明，活跃的长期记忆能够影响实际的编码任务，而无需用户在提示中重复记忆规则。

P18c 使用一个受限任务：根据一个极简的中文用户请求，创建一个简单的图书馆管理应用。被测试的活动记忆提供了通用项目位置、Vite/React/TypeScript 前端默认设置、localStorage 持久化、变更日志预期、平台边界以及供应商证据要求。

## 目标 / 非目标

**目标：**

- 在创建排练会话前，确认或激活长期记忆规则。
- 记忆激活后创建新会话，以便生成新的 `memorySnapshotId`。
- 验证规划器、编码代理、review/eval、TaskRun 证据和任务追踪使用同一快照。
- 当 auth/quota/runtime 允许时，使用 ClaudeCodeAdapter 或 CodexAdapter 执行图书馆管理任务。
- 评估实现是否遵循用户提示中未重复的记忆规则。
- 如实记录差异、build/check/test、审查、preview/staging 和记忆合规性证据。
- 生成 `docs/p18c-freeze-review.md`。

**非目标：**

- 不要构建生产级库系统。
- 不要添加真实后端、数据库、身份认证加固、云部署、多用户权限、提供商市场、向量搜索或知识图谱。
- 不要更改内存检索算法。
- 不要替换目标注册表、计划验证器、防护机制、运行时配置或调度器策略。
- 不要使用 ScriptedMock 来声称实时合规性。

## 决策

### 使用一个有边界的实时应用场景

实时用户提示词为：

```text
帮我在桌面开发一个简单的图书管理系统。有登录页面，初始账户和密码是 18088888888 / 888888。登录后进入管理页面，只需要有图书管理功能：加入图书、删除图书、修改图书、查询图书。
```

提示词有意省略了记忆规则。合规性通过实时任务是否遵循活跃记忆来衡量。

### 将内存设置视为前提条件

P18c 实现应首先确保以下内存规则处于激活状态：

1.  Unless otherwise specified, all new projects should be uniformly stored in the `~/Desktop/agenthub-rehearsals/` directory.
2.  The default tech stack for frontend projects is Vite + React + TypeScript.
3.  Unless explicitly required by the application, use localStorage for data persistence by default, without connecting to a backend or database.
4.  When code changes are involved, `docs/change-log.md` must be updated synchronously.
5.  Unless the platform maintenance mode is explicitly enabled, modifying the underlying code of the AgentHub platform is prohibited.
6.  Without supporting materials such as task run records, code diff files, or build logs, claims of successful third-party model service calls must not be made.

会话必须在这些规则生效后创建，以便快照证据能够证明规划器和编码代理已可获取这些规则。

### 基于证据而非声明评估合规性

冒烟测试应评估变更的文件、制品、提供者元数据、
快照元数据、build/check/test 输出和 preview/staging 记录。它
不应仅信任提供者的文本摘要。

### 让 control/treatment 保持诚实

治疗运行必须使用活跃内存。确定性或空运行控制可以
比较预期缺失的行为（无需内存）。如果不存在可比较的控制任务证据，
任务成功增量必须保持未知。

### 保障目标安全

目标应用位置位于 AgentHub 平台代码之外，位于桌面排练目录下。P18c 应尽可能使用现有的外部 workspace/target 注册和目标注册表规则。任何未明确处于平台维护模式的 AgentHub 平台代码变更均属违规行为。

## 风险 / 权衡

- [风险] 真实的 Claude/Codex 认证、配额或运行时可能不可用 ->
  缓解措施：记录确切的阻塞因素，不声称实时合规。
- [风险] 提供商创建了应用但遗漏了记忆规则 ->
  缓解措施：标记具体的合规违规项，而非重新路由到 ScriptedMock。
- [风险] 应用位置可能需要外部目标注册 ->
  缓解措施：为桌面预演目录和目标分析包含设置任务。
- [风险] 变更日志记忆可能与“不修改平台代码”冲突 ->
  缓解措施：将 `docs/change-log.md` 更新视为预期的文档证据，用于 AgentHub change/rehearsal，而应用源代码必须位于 AgentHub 平台代码之外。
- [风险] Preview/staging 可能对新创建的外部 Vite 目标不可用 ->
  缓解措施：记录确切的限制，并在可用时仍要求提供 build/check 证据。

## 迁移计划

无需迁移。P18c 是一个聚焦于 smoke/evaluation 的变更，构建在 P18/P18b. 之上。

## 待定问题

- 实现时哪个实时提供者可用：
  ClaudeCodeAdapter 还是 CodexAdapter？
- 实现将使用已注册的外部目标，还是在 `~/Desktop/agenthub-rehearsals/` 下创建并注册一个新目标？
