## 为什么

P17、P17b 和 P17c 使 AgentHub 能够通过 Planner LLM 路由正常对话、配置多个 Planner 提供者、在运行时配置编码代理提供者，以及选择工作区目标。下一个协调风险不再是“AgentHub 能否调用代理”，而是“代理实际服从的是哪个记忆和指令源？”

目前，规划器 LLM、Claude Code、Codex、审查代理、目标注册表、PlanValidator、仓库 `AGENTS.md`、潜在 `CLAUDE.md` 以及提供商本地的私有记忆各自可能看到不同的指令。这导致了行为不一致，并且难以审计规划器或 TaskRun 做出某个决策的原因。在添加更多自主代理行为之前，AgentHub 需要一个规范的、带版本控制的、具备作用域感知的记忆与指令控制平面。

## 变更内容

- 将 AgentHub Canonical Memory 引入为跨智能体项目指令、用户偏好、决策、模式、反馈和会话摘要的真相来源。
- 将 `AGENTS.md` 和 `CLAUDE.md` 视为 compiled/exported 制品，而非静默覆盖 AgentHub 内存的独立来源。
- 添加会话内存快照，使 Planner LLM、Claude Code、Codex 和 Review Agent 在 session/task 链中使用相同的 `memorySnapshotId`。
- 规划内存项的生命周期、评分、检索、淘汰、写入策略、提示注入防护和外部内存扫描。
- 定义内存如何编译为 `AGENTS.md`、`CLAUDE.md`、Planner 上下文块、Claude Code 指令、Codex 指令和 Review 指令。
- 添加内存管理 UI 计划，用于审查活跃、待定、预热、归档、拒绝、删除和外部建议的内存。
- 添加可衡量的内存有效性标准以及 P18 冻结演练。
- 将 Target Registry、PlanValidator 和 Guardrails 作为硬安全边界。内存指导行为；防护措施强制执行权限。

## 能力

### 新能力

- `memory-instruction-control-plane`: 规范记忆、快照、检索、托管指令导出、外部记忆建议、记忆管理及记忆评估基础。

### 修改后的能力

- `runtime-agent-coordination`：规划器和编码代理指令将引用相同的内存快照和证据元数据。
- `settings`：在不更改现有运行时提供程序设置的情况下，添加或规划内存设置界面。
- `mission-trace`：在适当位置记录内存和指令 hashes/versions。

## 影响

- 在 `apps/api` 中为记忆项、快照、检索、写入策略、哈希和证据元数据进行后端 model/API 设计。
- 为 Planner、Claude Code、Codex 和 Review Agent 生成指令。
- 管理 `AGENTS.md` / `CLAUDE.md` 的编译与用户自定义块的保留。
- 用于记忆审查和快照可见性的前端设置 UI。
- 针对确定性导出、快照一致性、提示注入阻断、检索精度和记忆证据的测试。
- 实现开始时，在 `docs/change-log.md` 和 `docs/project-state.md` 中更新文档。

## 明确非目标

- 完整知识图谱记忆。
- 强制向量数据库。
- RRF 融合排序。
- 无需用户审核的自动长期学习。
- 多用户共享记忆。
- 提供商市场。
- 云密钥管理器。
- 生产部署。
- 用记忆替换目标注册表、计划验证器或护栏。
- 允许 Claude Code 或 Codex 私有记忆覆盖 AgentHub 规范记忆。
