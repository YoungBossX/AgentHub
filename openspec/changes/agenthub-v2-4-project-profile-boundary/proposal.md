## 为什么

AgentHub Reliability v2 已完成 Durable Run Engine、Provider Gateway、Session Queue、Target Lock 和 Run Diagnostics。执行内核开始变得可靠，但项目边界仍然偏 demo：系统可以分析外部项目，也能注册 target，却还缺少一个正式的 ProjectProfile 合同来描述真实项目的技术栈、允许命令、预览策略和保护路径。

这会导致两个问题：

- Planner / PlanValidator / Provider 指令看到的是 target allowedPaths 和若干命令字段，但不知道这些字段来自什么项目 profile，也难以解释为何某个命令被允许或拒绝。
- AgentHub 想承接真实开发任务时，容易退回 demo-only 思维：Vite demo 能跑，但 Next.js、FastAPI、Generic repo 的构建、检查、预览和安全边界不够统一。

V2.4 的目标是把现有 Project Analyzer 升级为正式 ProjectProfile Boundary：AgentHub 能以 target-scoped 的方式识别并记录项目 profile，从 profile 派生允许命令和预览策略，同时继续让 Target Registry、PlanValidator 和 Guardrails 作为硬边界。

## 变更内容

- 定义 ProjectProfile 模型，覆盖 profile id、project type、framework、package manager、allowed paths、denied paths、commands、preview strategy、confidence 和 warnings。
- 将现有 project analyzer 的输出规范化为 profile，不用硬编码 demo regex 判断真实项目能力。
- 支持首批内置 profile：
  - Next.js / React；
  - Vite / React；
  - FastAPI / Python；
  - Generic Repo。
- 让外部 target 注册和 Target Registry 暴露 profile 信息，后续 planner、指令构建、run diagnostics 和 UI 能审计 target 使用的 profile。
- 让 Project Command Policy 使用 target profile 派生的命令白名单，继续拒绝未配置或不匹配命令。
- 为 unknown / generic 项目提供保守行为：需要确认或只允许显式配置命令，不默认开放任意 shell。
- 增加测试覆盖 profile 检测、命令派生、target 注册、命令策略和安全边界。

## 能力

### 新能力

- `project-profile-boundary`：为注册 target 提供正式 ProjectProfile 合同，用于真实项目边界、命令策略和预览策略。

### 修改后的能力

- `project-analyzer`：应返回可审计的 ProjectProfile，而不只是松散分析字段。
- `target-registry`：external target 应携带 profile 信息，并继续暴露 allowedPaths、deniedPaths 和 allowed commands。
- `project-command-policy`：命令允许规则应来自 profile/target 配置，不来自 demo 固定路径。
- `plan-validator`：执行计划仍必须通过 target、role、path、dependency 和 approval 验证；ProjectProfile 只能提供上下文和命令策略，不能绕过验证。

## 影响

- 后续实现预计会新增 ProjectProfile 模块、扩展 analyzer/target registry/schema/API 响应，并增加 API 单元测试。
- 后续实现需要更新 `docs/change-log.md` 和 `docs/project-state.md`。
- V2.4 不新增 adapter、不新增 provider marketplace、不允许任意 shell command agent、不替换 Target Registry / PlanValidator / Guardrails、不改变 ClaudeCodeAdapter 或 CodexAdapter 的真实执行语义。
