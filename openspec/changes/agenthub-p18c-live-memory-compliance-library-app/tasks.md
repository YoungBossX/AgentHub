## 1. P18c-1 内存规则与合规框架

- [x] 1.1 为测试中的六条 P18c 规则添加或验证活跃的规范记忆项。
- [x] 1.2 为内存 ID、项目位置、框架、持久化、变更日志、平台边界、提供者证据和快照一致性添加 P18c 合规性 model/checker。
- [x] 1.3 为每个合规违规代码以及一个通过的证据夹具添加测试。
- [x] 1.4 验证 `pnpm check`、定向测试、`git diff --check` 和 `openspec validate agenthub-p18c-live-memory-compliance-library-app --strict`。

## 2. P18c-2 会话与外部目标设置

- [x] 2.1 创建或准备 `~/Desktop/agenthub-rehearsals/` 作为允许的排练根目录，无需手动创建库应用实现。
- [x] 2.2 通过现有的外部工作区/目标注册表路径，在需要时注册或分析桌面排练前端目标。
- [x] 2.3 在活动内存存在后创建新的 AgentHub 会话，并记录 `memorySnapshotId`。
- [x] 2.4 验证 AGENTS.md 哈希值、CLAUDE.md 哈希值、活动内存 ID、目标注册表版本、运行时配置版本以及上下文包哈希值在会话中可用。
- [x] 2.5 通过定向测试或冒烟命令、`git diff --check` 以及 OpenSpec 严格验证来验证设置。

## 3. P18c-3 实时库应用执行

- [x] 3.1 精确提交受限的图书馆管理用户提示，不重复记忆规则。
- [x] 3.2 如果 auth/quota/runtime 允许，使用真实的 ClaudeCodeAdapter 或 CodexAdapter 运行编码任务。
- [x] 3.3 如果无法使用真实提供商执行，则停止并记录确切的阻塞因素；不得使用 ScriptedMock 来声称符合实际运行要求。
- [x] 3.4 如果执行成功，验证应用包含登录功能、固定演示凭据、管理页面、add/delete/edit/search 本书籍以及 localStorage 持久化。
- [x] 3.5 收集 TaskRun、差异对比、已更改文件、build/check/test、审查、preview/staging 证据（如可用）。
- [x] 3.6 验证实际任务不会修改 `apps/api` 或 AgentHub 平台代码，除非处于明确的平台维护模式。

## 4. P18c-4 内存合规性评估

- [x] 4.1 针对实时证据运行 P18c 合规性检查器。
- [x] 4.2 当存在可比较的控制证据时，报告偏好召回率、项目记忆召回率、跨代理一致性率、快照一致性率、变更日志缺失率、目标边界违规次数、持久记忆违规次数、提供者证据违规次数以及任务成功差异。
- [x] 4.3 如果可行，添加确定性或空运行控制比较；否则将任务成功差异标记为未知或不确定。
- [x] 4.4 如果需要后续修复记忆合规性问题，如实记录首次失败和后续证据。
- [x] 4.5 验证定向测试、`git diff --check` 和 OpenSpec 严格验证。

## 5. P18c-5 冻结评审

- [x] 5.1 使用提供者、会话、task/run、快照、内存哈希、活跃内存、差异、审查、build/check/test、preview/staging、合规性、后续跟进和限制证据创建 `docs/p18c-freeze-review.md`。
- [x] 5.2 使用 P18c 状态更新 `docs/project-state.md` 和 `docs/change-log.md`。
- [x] 5.3 验证 `pnpm check`、`pnpm test`、`pnpm demo:api:test`、`git diff --check` 和 `openspec validate agenthub-p18c-live-memory-compliance-library-app --strict`。
- [x] 5.4 确认 P18c 未添加生产环境 backend/database、云部署、身份验证加固、新的检索算法、提供者市场，或任何绕过目标注册表/计划验证器/防护机制的行为。
