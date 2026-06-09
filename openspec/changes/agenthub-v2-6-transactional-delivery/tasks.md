## 1. OpenSpec 与边界确认

- [x] 1.1 创建 V2.6 Transactional Delivery OpenSpec，定义中文范围、非目标、状态、checkpoint、validation、accept、rollback 和 retry 边界。
- [x] 1.2 审查现有 checkpoint、diff、review、command evidence、recovery retry、run diagnostics 和 run engine finalizer。
- [x] 1.3 明确 V2.6 不新增 adapter、不重做 durable worker、不改 planner 核心、不做 PR/export/生产部署。
- [x] 1.4 验证 `git diff --check` 和 `openspec validate agenthub-v2-6-transactional-delivery --strict`。

## 2. Delivery 合同与 Checkpoint Evidence

- [x] 2.1 新增 `apps/api/app/transactional_delivery.py`，定义 delivery state、delivery decision、artifact state 和 retry mode。
- [x] 2.2 复用 TaskRun metrics / checkpoint 信息生成 delivery checkpoint evidence。
- [x] 2.3 缺少 checkpoint 时 rollback 必须拒绝。
- [x] 2.4 增加 checkpoint / state 合同测试并验证。
- [x] 2.5 提交：`feat: add transactional delivery contract`。

## 3. Validation 与 Review Gate

- [x] 3.1 实现 validation gate helper，检查 command evidence、diff/review evidence 和 policy decision。
- [x] 3.2 validation failed 进入 review_required，不得宣称 completed delivery。
- [x] 3.3 记录 `delivery.review_required` / `delivery.validation_failed` evidence。
- [x] 3.4 增加 validation/review gate 测试并验证。
- [x] 3.5 提交：`feat: gate delivery validation`。

## 4. Accept / Rollback / Retry

- [x] 4.1 实现 accept helper，记录 diff/review/command evidence artifact state。
- [x] 4.2 实现 rollback helper，基于 checkpoint 恢复或拒绝，且记录事件。
- [x] 4.3 retry helper 显式区分 current_state 与 checkpoint。
- [x] 4.4 增加 accept/rollback/retry 测试并验证。
- [x] 4.5 提交：`feat: add delivery accept rollback retry`。

## 5. Run Engine / Diagnostics 接入

- [x] 5.1 在合适的 finalizer 或 service 边界写入 delivery gate evidence。
- [x] 5.2 validation failure 不应启动 preview/deploy ready 证据。
- [x] 5.3 Run Diagnostics 可识别 delivery validation / review_required / rollback 事件。
- [x] 5.4 增加窄集成测试并验证。
- [ ] 5.5 提交：`feat: integrate transactional delivery evidence`。

## 6. 冻结审查

- [ ] 6.1 更新 `docs/change-log.md` 和 `docs/project-state.md`。
- [ ] 6.2 创建 `docs/v2-6-transactional-delivery-freeze-review.md`。
- [ ] 6.3 运行完整验证：`pnpm check`、`pnpm test`、`pnpm demo:api:test`、`git diff --check`、`openspec validate agenthub-v2-6-transactional-delivery --strict`。
- [ ] 6.4 标记 V2.6 tasks 完成并停止。
- [ ] 6.5 提交：`test: freeze v2.6 transactional delivery`。
