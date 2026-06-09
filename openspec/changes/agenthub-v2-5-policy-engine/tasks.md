## 1. OpenSpec 与边界确认

- [x] 1.1 创建 V2.5 Policy Engine OpenSpec，定义中文范围、非目标、策略 outcome、类别和安全约束。
- [x] 1.2 审查现有 Guardrails、Target Registry、Project Command Policy、Provider Gateway、Deployment Provider 和 Approval 入口。
- [x] 1.3 明确 V2.5 首版只做统一策略合同和测试，不新增任意 shell agent、不绕过 PlanValidator、不放开生产部署。
- [x] 1.4 验证 `git diff --check` 和 `openspec validate agenthub-v2-5-policy-engine --strict`。

## 2. Policy Engine 合同

- [x] 2.1 新增 `apps/api/app/policy_engine.py`，定义 PolicyDecision、PolicyOutcome、PolicyCategory、RiskLevel、ApprovalType 等合同。
- [x] 2.2 支持 outcome：`allow`、`deny`、`require_approval`、`require_elevated_approval`。
- [x] 2.3 支持 category：command、path、network、cost、destructive_change、deploy、platform_maintenance。
- [x] 2.4 evidence 必须脱敏，不暴露 secrets、tokens、API keys、`.env` 内容或未授权 host paths。
- [x] 2.5 增加合同测试并验证。
- [x] 2.6 提交：`feat: add policy engine contract`。

## 3. 现有边界适配

- [x] 3.1 command policy 复用 `evaluate_project_command()`，匹配允许，缺失或不匹配拒绝。
- [x] 3.2 path policy 复用 target allowed/denied paths 和 guardrails 语义。
- [x] 3.3 network policy 默认要求审批，不能默认放开外网。
- [x] 3.4 deploy policy 保留 mock/local staging/manual/blocked 行为，不新增生产部署。
- [x] 3.5 platform maintenance 返回高级审批，不能被普通 approval 绕过。
- [x] 3.6 增加适配测试并验证。
- [x] 3.7 提交：`feat: evaluate runtime policies`。

## 4. Approval Timeout 与 Evidence

- [x] 4.1 增加 approval timeout helper，超时默认 deny。
- [x] 4.2 输出 requestedAction、approvalType、riskLevel、reason 和 safeMetadata。
- [x] 4.3 确保 policy evidence 可进入 Run Diagnostics / MissionTrace，但不要求本阶段大改 UI。
- [x] 4.4 增加 timeout 和 evidence 脱敏测试并验证。
- [ ] 4.5 提交：`feat: record policy evidence decisions`。

## 5. 冻结审查

- [ ] 5.1 更新 `docs/change-log.md` 和 `docs/project-state.md`，记录 V2.5 实现范围和限制。
- [ ] 5.2 创建 `docs/v2-5-policy-engine-freeze-review.md`。
- [ ] 5.3 运行完整验证：`pnpm check`、`pnpm test`、`pnpm demo:api:test`、`git diff --check`、`openspec validate agenthub-v2-5-policy-engine --strict`。
- [ ] 5.4 标记 V2.5 tasks 完成并停止，不自动开始 V2.6。
- [ ] 5.5 提交：`test: freeze v2.5 policy engine`。
