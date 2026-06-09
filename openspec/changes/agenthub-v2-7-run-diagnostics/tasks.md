## 1. OpenSpec 与边界确认

- [ ] 1.1 创建 V2.7 Run Diagnostics OpenSpec，定义范围、非目标、诊断模型、UI/API 验收和安全约束。
- [ ] 1.2 审查 V2.1-V2.6 相关设计与现有 TaskRunEvent、MissionTrace、Provider Gateway、Scheduler、Preview、Deploy 证据来源。
- [ ] 1.3 明确 V2.7 只做诊断投影和 UI/API，不实现新 adapter、不改变执行语义、不新增 WebSocket/Docker/PR/外部 IM。
- [ ] 1.4 验证 `git diff --check` 和 `openspec validate agenthub-v2-7-run-diagnostics --strict`。

## 2. 诊断模型与分类器

- [ ] 2.1 定义 RunDiagnostics 响应结构：summary、primaryFailure、contributingFactors、timeline、healthSummary、suggestions。
- [ ] 2.2 实现 failure category 映射，覆盖 provider auth/quota/unavailable、adapter timeout/interrupted/error、queue stale/blocked、lock timeout、worktree dirty、validation failed、approval denied、preview failed、deploy failed/blocked、artifact collection failed、unknown。
- [ ] 2.3 保留 raw error code 作为辅助字段，但 UI 主文案使用分类后的用户可读原因。
- [ ] 2.4 添加分类器单元测试，覆盖多原因时 primary failure、contributing factors 和 unknown fallback。
- [ ] 2.5 验证相关 API 测试、`pnpm check:demo-api` 或更窄等效命令、`git diff --check`。

## 3. Run Timeline 构建

- [ ] 3.1 从 TaskRun、TaskRunEvent、scheduler/provider/artifact/preview/deploy 证据构建按时间排序的 timeline。
- [ ] 3.2 支持 queued、scheduler_check、dependency_wait、lock_wait、approval_wait、validation、provider_check、worker_claim、adapter_start、adapter_stream、adapter_finish、artifact_collection、diff、review、preview、deploy、finalize、recovery phase。
- [ ] 3.3 为每个 timeline item 提供 stable id、timestamp、phase、status、title、description、source、安全 metadata 和可选 artifact reference。
- [ ] 3.4 添加 timeline 测试，覆盖成功运行、provider 失败、timeout、preview 后处理失败和 recovery/stale 运行。
- [ ] 3.5 验证相关 API 测试、`pnpm check:demo-api` 或更窄等效命令、`git diff --check`。

## 4. Health Summary 与下一步建议

- [ ] 4.1 构建 provider health，展示 provider id、adapter type、auth/config、availability、fallback 和真实 provider 成功状态。
- [ ] 4.2 构建 queue health，展示 queued 时长、worker claim、lease、heartbeat、stale/recovery 状态。
- [ ] 4.3 构建 lock health，展示 target id、lock owner、等待时长和 lock timeout。
- [ ] 4.4 构建 preview/deploy health，展示 build/dev server/health check、deployment provider、status、blocked/failed/ready 和 source artifact。
- [ ] 4.5 根据 failure category 生成 next-step suggestions，包含 action id、label、description、kind、enabled 和 disabled reason。
- [ ] 4.6 添加 health summary 与 suggestion 测试，覆盖可重试、需设置 provider、等待审批、查看 artifact、选择 fallback、manual handoff 等建议。
- [ ] 4.7 验证相关 API 测试、`pnpm check:demo-api` 或更窄等效命令、`git diff --check`。

## 5. 安全 API

- [ ] 5.1 暴露 TaskRun 诊断 API 或将诊断嵌入现有 TaskRun 详情响应，并保持向后兼容。
- [ ] 5.2 暴露 Session 级 run diagnostics summary，用于 mission panel 或 workspace overview。
- [ ] 5.3 对 metadata、日志、路径、provider 输出和 artifact references 做脱敏与长度限制。
- [ ] 5.4 确保没有诊断响应包含 raw secrets、API keys、tokens、受保护 host paths 或 `.env` 内容。
- [ ] 5.5 添加 API 测试覆盖权限边界、缺失证据 unknown、脱敏、稳定字段和旧前端兼容。
- [ ] 5.6 验证相关 API 测试、`pnpm check:demo-api` 或更窄等效命令、`git diff --check`。

## 6. 前端 Run Diagnostics UI

- [ ] 6.1 在 Task card / task run detail 中显示诊断摘要、失败分类、severity、retryability 和下一步。
- [ ] 6.2 在右侧 panel 或 mission panel 中展示 Run Timeline，支持快速扫描各 phase 状态。
- [ ] 6.3 展示 provider、queue、lock、preview、deploy health summary。
- [ ] 6.4 将 preview/deploy 失败卡片链接到同一个诊断视图，不覆盖编码 run 的主失败原因。
- [ ] 6.5 为建议动作接入已有重试、打开设置、打开 artifact、请求审批、选择 fallback 或 manual handoff 入口；未实现动作必须禁用并说明原因。
- [ ] 6.6 添加前端测试覆盖 provider quota/auth、timeout、worktree dirty、lock timeout、validation failed、approval denied、preview failed、deploy blocked/failed 的渲染。
- [ ] 6.7 验证相关 web 测试、`pnpm check` 或更窄等效命令、`git diff --check`。

## 7. 冻结审查与文档

- [ ] 7.1 更新 `docs/change-log.md` 和 `docs/project-state.md`，记录 V2.7 实现范围和真实限制。
- [ ] 7.2 创建 `docs/v2-7-run-diagnostics-freeze-review.md`，记录诊断分类、UI/API 行为、脱敏策略、测试结果和后续工作。
- [ ] 7.3 运行完整验证：`pnpm check`、`pnpm test`、`pnpm demo:api:test`、`git diff --check`、`openspec validate agenthub-v2-7-run-diagnostics --strict`。
- [ ] 7.4 标记 V2.7 tasks 完成并停止，不自动开始 V2.8 或其他平台能力。
