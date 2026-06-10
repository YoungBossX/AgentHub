## 为什么

P18 使记忆可审计，P18b 证明了确定性记忆的有效性，但 AgentHub 仍需有限的实际智能体证据，证明长期记忆确实会影响 ClaudeCodeAdapter 或 CodexAdapter 的执行。P18c 创建了一个单一的非平凡库管理应用冒烟测试，用于检验真实编码智能体是否能在用户不重复规则的情况下遵循活跃记忆。

## 变更内容

- 新增一个以“图书馆管理应用”任务为核心的实时内存合规性冒烟测试。
- 要求在会话开始前存在活跃的长期内存规则。
- 验证规划器、编码代理、review/eval、TaskRun 证据以及任务追踪是否使用相同的 `memorySnapshotId`。
- 当 auth/quota/runtime 允许时，运行真实的 ClaudeCodeAdapter 或 CodexAdapter 任务；若不可用则记录确切的阻塞原因。
- 评估生成的应用是否遵循关于项目位置、Vite + React + TypeScript 前端默认配置、localStorage 持久化、变更日志更新、目标边界以及提供者证据的通用内存规则。
- 生成包含会话、运行、内存、差异、审查、构建、preview/staging 以及合规性证据的 `docs/p18c-freeze-review.md`。
- 保留 P18/P18b 边界：内存指导代理行为，而目标注册表、计划验证器、护栏、运行时配置和调度器策略则强制执行安全性。

## 能力

### 新能力

- `live-memory-compliance`: 针对有界编码任务中长时记忆效应的实时智能体冒烟与合规性评估。

### 修改后的能力

- 无。

## 影响

- 可添加评估辅助工具、冒烟脚本、测试及冻结文档。
- 在实现过程中，可在 `~/Desktop/agenthub-rehearsals/` 下创建或注册外部前端目标。
- 仅在实现冒烟测试期间运行真实的 ClaudeCodeAdapter 或 CodexAdapter，绝不在本规划任务期间运行。
- 不添加 backend/database 托管、生产部署、新的记忆检索算法、向量搜索、知识图谱、提供商市场或任何护栏绕过机制。
