## ADDED Requirements

### Requirement: ProjectProfile 描述注册项目边界

系统 SHALL 为每个注册 target 提供可审计的 ProjectProfile，用于描述项目类型、技术栈、
允许路径、命令策略和预览策略。

#### Scenario: 已识别项目返回 ready profile
- **WHEN** 用户分析或注册一个可识别的 Vite、Next.js 或 FastAPI 项目
- **THEN** 系统 MUST 返回 ProjectProfile 摘要
- **AND** 摘要 MUST 包含 profile id、project type、detected framework、package manager、allowed paths、denied paths、commands、preview strategy、confidence 和 status
- **AND** status SHOULD 为 `ready`

#### Scenario: 未识别项目返回保守 profile
- **WHEN** 用户分析或注册一个无法识别的项目
- **THEN** 系统 MUST 返回 `generic-repo` 或等效保守 profile
- **AND** status MUST 为 `needs_confirmation`
- **AND** 系统 MUST NOT 自动开放任意 shell command

#### Scenario: Profile 不替代安全边界
- **WHEN** ProjectProfile 显示某个路径或命令可能适用于项目
- **THEN** 实际执行仍 MUST 通过 Target Registry、PlanValidator、Guardrails 和 command policy
- **AND** ProjectProfile MUST NOT 允许绕过 protected paths、platform maintenance approval 或 role/target 验证

### Requirement: 内置 profile 覆盖首批真实项目类型

系统 SHALL 至少支持 Vite/React、Next.js/React、FastAPI/Python 和 Generic Repo 的
profile 检测或规范化。

#### Scenario: Vite React profile 派生前端命令
- **WHEN** 项目包含 Vite React 标记和 package scripts
- **THEN** profile MUST 派生 dev、test、check 或 build 中已配置的命令
- **AND** preview strategy SHOULD 表示 Vite dev server
- **AND** allowed paths SHOULD 来自实际存在的 `src`、`public`、`tests` 或 `test`

#### Scenario: Next.js profile 派生前端命令
- **WHEN** 项目包含 Next.js 标记和 package scripts
- **THEN** profile MUST 标记 project type 为 Next.js 或等效类型
- **AND** allowed paths SHOULD 来自实际存在的 `app`、`pages`、`components`、`src`、`public`、`tests` 或 `test`
- **AND** profile MUST NOT 要求生产部署能力

#### Scenario: FastAPI profile 派生 Python 命令
- **WHEN** 项目包含 FastAPI 标记
- **THEN** profile MUST 标记 project type 为 FastAPI 或等效类型
- **AND** allowed paths SHOULD 来自实际存在的 `app`、`src` 或 `tests`
- **AND** check/test commands SHOULD 使用安全的 Python 检查或测试命令

#### Scenario: Generic profile 只接受显式配置
- **WHEN** 项目落入 Generic Repo profile
- **THEN** 系统 MUST 只允许用户显式配置且通过校验的 allowed paths 和 commands
- **AND** 缺失命令 MUST 被 command policy 拒绝

### Requirement: Target Registry 暴露 profile 审计信息

系统 SHALL 在 Target Registry 和 external target API 中暴露 ProjectProfile 审计信息。

#### Scenario: External target 转换保留 profile
- **WHEN** 已注册 external target 被转换为 TargetProject
- **THEN** TargetProject MUST 保留 profile id、project type、framework、package manager、analysis status、preview strategy 和 warnings 中可用的信息
- **AND** allowed agents MUST 仍由 target type 和现有策略决定

#### Scenario: Built-in demo target 保持兼容
- **WHEN** 系统列出 built-in demo frontend/backend/platform target
- **THEN** 它们 MUST 继续保留现有 allowed paths、commands 和 approval 行为
- **AND** 新 profile 字段缺失时旧逻辑 MUST 继续工作

#### Scenario: Profile 信息可用于指令但不泄密
- **WHEN** Planner 或 coding agent instruction 包含 target profile 摘要
- **THEN** 摘要 MUST 不包含 API keys、tokens、`.env` 内容、secrets 或受保护 host paths
- **AND** denied paths MUST 保持可见为安全边界提示

### Requirement: 命令策略由 target/profile 配置驱动

系统 SHALL 只允许 target/profile 显式配置的项目命令用于验证、构建或预览证据。

#### Scenario: 匹配命令被允许
- **WHEN** 运行请求的 command type 和 command 与 target/profile 配置完全匹配
- **THEN** command policy MUST 返回 allowed
- **AND** evidence SHOULD 记录 target id、command type 和允许原因

#### Scenario: 缺失命令被拒绝
- **WHEN** target/profile 没有配置某类命令
- **THEN** command policy MUST 返回 denied
- **AND** 系统 MUST NOT 猜测或生成替代 shell command

#### Scenario: 不匹配命令被拒绝
- **WHEN** 请求命令与 target/profile 配置命令不一致
- **THEN** command policy MUST 返回 denied
- **AND** 拒绝原因 SHOULD 说明期望命令和 target id

#### Scenario: Generic repo 不默认开放命令
- **WHEN** target 使用 Generic Repo profile 且用户没有显式配置 build/test/check 命令
- **THEN** build/test/check command policy MUST 拒绝执行
- **AND** AgentHub MUST NOT 因 generic profile 而允许任意 shell

### Requirement: V2.4 保持既有可靠性基线

系统 SHALL 保持 P6-P23 以及 Reliability V2.1-V2.3/V2.7 已完成基线。

#### Scenario: 执行计划仍需要 PlanValidator
- **WHEN** LLM Router 返回 task_plan
- **THEN** task_plan MUST 继续进入 schema validation 和 PlanValidator
- **AND** ProjectProfile MUST NOT 让 unsafe target/path/role 计划直接创建任务

#### Scenario: Provider 成功不被伪造
- **WHEN** coding agent provider 不可用、失败或 fallback
- **THEN** 系统 MUST 诚实记录 provider/fallback evidence
- **AND** ProjectProfile MUST NOT 将 fallback 成功宣称为 Claude/Codex 真实成功

#### Scenario: 平台维护仍需审批
- **WHEN** task_plan 或 target 指向 AgentHub platform code
- **THEN** 系统 MUST 保留 platform maintenance approval 要求
- **AND** external project profile MUST NOT 扩大到平台底层代码
