## 1. OpenSpec 与边界确认

- [ ] 1.1 创建 V2.4 Project Profile Boundary OpenSpec，定义中文范围、非目标、profile 合同、命令策略和安全约束。
- [ ] 1.2 审查现有 Project Analyzer、External Workspace、Target Registry、PlanValidator、Project Command Policy 和 Preview 接入点。
- [ ] 1.3 明确 V2.4 只做 target-scoped ProjectProfile 边界，不新增任意 shell agent、不绕过 PlanValidator、不实现生产部署。
- [ ] 1.4 验证 `git diff --check` 和 `openspec validate agenthub-v2-4-project-profile-boundary --strict`。

## 2. ProjectProfile 合同

- [ ] 2.1 新增或扩展 ProjectProfile 数据结构，覆盖 profile id、project type、framework、package manager、allowed/denied paths、commands、preview strategy、confidence、status 和 warnings。
- [ ] 2.2 将 analyzer 输出规范化为 ProjectProfile，保持现有 API 字段向后兼容。
- [ ] 2.3 增加 Vite/React、Next.js/React、FastAPI/Python、Generic Repo profile 测试。
- [ ] 2.4 验证相关 API 单元测试、`pnpm check` 或更窄等效命令、`git diff --check`。
- [ ] 2.5 提交：`feat: add project profile contract`。

## 3. Target Registry 与 External Target 接入

- [ ] 3.1 在 external target registration / analysis response 中暴露 ProjectProfile 摘要。
- [ ] 3.2 确保 `TargetProject` 能携带 profile id、preview strategy、confidence 和 warnings 等审计信息。
- [ ] 3.3 保持 allowedPaths、deniedPaths、allowedAgents 和 platform maintenance approval 逻辑不回退。
- [ ] 3.4 增加 external workspace / target registry 测试。
- [ ] 3.5 验证相关测试、`pnpm check` 或更窄等效命令、`git diff --check`。
- [ ] 3.6 提交：`feat: attach project profiles to targets`。

## 4. Profile 驱动命令策略

- [ ] 4.1 让 Project Command Policy 使用 target/profile 配置命令作为允许来源。
- [ ] 4.2 对 Generic Repo 保持保守：未显式配置的命令必须拒绝，不能开放任意 shell。
- [ ] 4.3 记录命令允许/拒绝原因，方便 Run Diagnostics 和 mission trace 展示。
- [ ] 4.4 增加 command policy 测试，覆盖匹配、不匹配、缺失、generic 显式命令和未知命令类型。
- [ ] 4.5 验证相关测试、`pnpm check` 或更窄等效命令、`git diff --check`。
- [ ] 4.6 提交：`feat: derive command policy from project profiles`。

## 5. Planner / Instruction 上下文

- [ ] 5.1 在 planner target summary 或 instruction target context 中加入 profile 摘要。
- [ ] 5.2 确保 profile 摘要不包含 secrets、受保护 host path 或未授权命令。
- [ ] 5.3 保证 LLM task_plan 仍直接进入 PlanValidator，profile 不绕过 target/path/role 验证。
- [ ] 5.4 增加 planner/instruction builder 窄测试。
- [ ] 5.5 验证相关测试、`pnpm check` 或更窄等效命令、`git diff --check`。
- [ ] 5.6 提交：`feat: include project profile context in planning`。

## 6. 冻结审查

- [ ] 6.1 更新 `docs/change-log.md` 和 `docs/project-state.md`，记录 V2.4 实现范围和限制。
- [ ] 6.2 创建 `docs/v2-4-project-profile-boundary-freeze-review.md`，记录 profile 合同、测试、验证结果和未完成能力。
- [ ] 6.3 运行完整验证：`pnpm check`、`pnpm test`、`pnpm demo:api:test`、`git diff --check`、`openspec validate agenthub-v2-4-project-profile-boundary --strict`。
- [ ] 6.4 标记 V2.4 tasks 完成并停止，不自动开始 V2.5。
- [ ] 6.5 提交：`test: freeze v2.4 project profile boundary`。
