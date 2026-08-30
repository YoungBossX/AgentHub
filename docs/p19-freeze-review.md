# P19 规划器路由加固冻结评审

**复核日期：** 2026-08-29

**历史实现日期：** 2026-06-07

**结论：** P19 的实现、路由回归、P18c 任务创建和 provider 边界证据足以冻结。原
`docs/p19-freeze-review.md` 受当时 `docs/` ignore 规则影响没有进入 Git；本文依据当前代码、
OpenSpec、受跟踪历史记录和 fresh tests 重建，但不称为原稿恢复。

## 冻结范围

P19 只加固 Planner/Conversation Router：

- API planner 与 Claude CLI planner 使用同一规范提示合约；
- 明确的软件构建请求优先返回带完整 `planDraft` 的 `task_plan`；
- 问候/能力询问保持 `assistant_reply`；
- clarification/refusal/approval_required 保持非执行；
- 安全外部前端请求被误分类为 `assistant_reply` 时，进入有审计证据的确定性 fallback；
- 所有可执行 LLM plan 仍需 schema 与 PlanValidator 验证；
- Target Registry、allowed/denied paths、Scheduler、Guardrails 与 provider runtime 保持硬边界。

P19 没有加入图书管理硬编码模板、任意主机路径写入、新 adapter、provider 市场、生产部署
或云密钥管理。

## 规范提示统一

`planner_conversation_system_prompt()` 是 API 与 Claude CLI planner 的共享提示源。当前调用点
覆盖 Claude CLI、OpenAI Responses、Anthropic Messages 和兼容 API payload 构造；定向测试
验证它们渲染同一契约。

共享提示包含：

- `assistant_reply`、`task_plan`、`clarification`、`refusal`、
  `approval_required`、`unsupported` 六种 outcome；
- `PlannerResponse` 的 plan/task 字段、角色、意图类型、制品类型、风险和审批要求；
- 目标必须来自 Target Registry、文件必须在 allowed paths 内、不得命中 denied paths；
- 问候到 `assistant_reply` 的少样本；
- 图书/库存/CRUD 风格软件请求到 `task_plan` 的少样本；
- planner 不执行代码、不调用 coding agent、不部署。

传输 JSON schema 最少要求 `outcomeType`；进入执行前，Pydantic `ConversationOutcome`、
`PlannerResponse` 与 PlanValidator 继续做完整验证。`task_plan` 缺 `planDraft`，或非任务 outcome
携带 `planDraft`，均不能成为可执行计划。

## 路由与 fallback 行为

对 LLM 的 `assistant_reply`，系统先区分纯聊天、已有 active planning task、安全外部请求和
缺失目标：

| 输入/结果 | 行为 |
|---|---|
| 纯问候或能力询问 | 只创建 orchestrator chat reply，不创建 Task/TaskRun |
| clarification/refusal/approval_required | 保持非执行 |
| 安全编码请求 + active external frontend target | 创建 scoped fallback frontend Task |
| 安全编码请求 + 无 target | 要求 target setup/clarification，不写主机路径 |
| unsafe/system/platform/broad request | 不回退成普通 frontend task |
| 无效 `task_plan` | 记录验证失败；不得从无效 plan 创建任务 |

fallback Task 的 `plannerEvidence` 保存：

- `plannerSource=fallback`
- `fallbackReason=non_task_coding_outcome`
- `llmOutcomeType=assistant_reply`
- `deterministicExecutable=true`
- provider id/type/source/model/preset（存在时）
- validation result、安全错误摘要和创建的 Task IDs

Mission trace 读取同一 `plannerEvidence`。错误摘要会编辑 secret/token/password/API key 和
受保护绝对路径，不能输出原始凭据。

## 新型应用与 P18c 路由证据

当前回归证明登录、todo、notes、mini-CRM 和 Breakout 仍是稳定基线，但外部目标 fallback
不依赖这些固定模板。只要请求被识别为安全前端编码请求且 Session 有 active external target，
图书、库存或其他 CRUD 应用可以生成限定于该 target 的任务。

fresh P18c 有界演练记录：

| 字段 | 值 |
|---|---|
| Session | `e65ba76a-5abe-440b-a34d-f0b7dca8ed0c` |
| Target | `external-p18c-library-app` |
| Task | `71811fb2-276a-41b9-ae01-c66b5829a947` |
| Planner | `orchestrator_external_target_v1` |
| Planner source | `fallback`；LLM planner disabled |
| Task role/intent | `frontend` / `frontend_change` |
| Task scope | 目标允许路径；默认无 backend/database |

这次 fresh live smoke 证明“已准备 external target 的 P18c 请求会创建 Task”，并进入真实 Codex
coding provider。完整 TaskRun、Diff 和验证证据见
[`p18c-freeze-review.md`](p18c-freeze-review.md) 与
[`p18c-bounded-rehearsal-evidence.json`](p18c-bounded-rehearsal-evidence.json)。它没有证明真实
LLM planner 成功；本轮 planner 是明确标记的 fallback，因此不把它计为 LLM planning 成功。

针对 P19 特有的“LLM 返回 `assistant_reply`”情形，当前回归
`test_p18c_library_request_misclassified_as_assistant_reply_routes_to_task` 通过，验证了
`non_task_coding_outcome` 证据和 scoped task 创建。

## Provider 运行边界

P19 自身不执行 coding provider，但 OpenSpec 5.4 要求若后续真实 provider 运行则记录证据。
本轮 P18c 已满足该边界：

- 首次 Codex TaskRun `e933edce-b7c2-4f0b-8b04-fd6296e20a74` 因 Corepack 签名问题超时；
- 最终 Codex adapter run `codex-3f1b6528-7816-4fd7-b5b4-0e9fa360fb53` 产生
  `turn.completed`，scope validation 为 `passed`；
- TaskRun `1c83525d-2488-4772-8d0b-2cc293a4163c` 在 provider 完成后的 Git GBK 解码阶段
  失败，持久化终态保持 `ADAPTER_EXECUTION_ERROR`；没有伪造 `completed`；
- UTF-8 修复后从同一外部 Git 基线补采 Diff artifact
  `bc542c97-0761-4e52-8ff4-367d694b83aa` 和 validation artifact
  `4a17b1b6-e755-4c7b-b802-aa0bce1c2337`。

这证明 planner routing 已不再是 P18c 的阻断因素；provider/runtime/finalizer 状态仍按独立证据
报告。

## 验证

### Fresh current-worktree 验证

| 检查 | 结果 |
|---|---|
| `test_planner_providers.py test_planning.py test_llm_planner.py` | 121 passed；1247 条既有 `datetime.utcnow()` warnings |
| 测试库前置 | 在隔离工作树根执行 `python -m app.db`，初始化可清理的本地 SQLite 后运行 |
| P18c library misroute regression | 包含在 121 项中，PASS |
| `openspec validate agenthub-p19-planner-routing-hardening --strict` | PASS |
| 当前 P18c routing/live smoke | Task 创建并进入真实 provider；证据见 P18c 冻结评审 |

首次 fresh 测试在本地测试库未初始化时出现 10 个 `no such table: targetlock`，均发生于 response
background worker，尚未进入 P19 断言；初始化当前 schema 后同一测试集 121/121 通过。该前置失败
作为测试环境证据保留，不计为 P19 路由失败。

### 历史基线交叉验证

在 detached commit `adbadc6aaa342324e843896aa1d1ffaf9d19f913` 初始化其本地 SQLite 后，
同一三文件规划测试集 fresh 运行 115/115 通过。受跟踪历史变更日志还记录了 2026-06-07 的：

- `pnpm check` PASS；
- `pnpm test` PASS（58 Web + 440 API + 5 demo API）；
- `pnpm demo:api:test` PASS；
- `git diff --check` PASS；
- P19 strict OpenSpec PASS。

本轮没有把这些历史 pnpm 结果表述为当前重跑；当前 Corepack 仍受签名 key/网络路径限制。

## 剩余风险

- 真实 LLM planner 仍可能忽略提示；schema、PlanValidator、deterministic fallback 和审计证据是
  必需的防线。
- `_is_pure_chat_request` 是有限的精确匹配，更多自然语言闲聊可能落入 unsupported/setup
  reply；这影响体验，不授予执行权限。
- 新型应用 fallback 依赖 active external target 和安全意图启发式；没有 target 时不会自动写
  Desktop/host path。
- transport JSON schema 允许 additional properties，最终安全性依赖 Pydantic/PlanValidator，
  不能仅以 provider 结构化输出成功作为可执行证据。
- fallback 可掩盖 planner 模型质量下降，因此必须继续观察 `fallbackReason`、provider metadata
  和 validation errors。
- 本轮真实 coding provider 的 TaskRun 后处理失败属于 P18c/runtime 证据，不改变 P19 路由已
  创建 scoped Task 的结论。

## 冻结决定

P19 的共享提示、非任务路由、验证证据、target 边界、新型应用回归、P18c task-creation smoke
和 provider 边界均有可追溯证据。P19 保持 **Complete**；P18c 已在本轮独立完成 24/24。
在 2026-08-29 P19 独立复核结束时，整个项目仍受当时尚未闭合的 P18b 4.1/4.2 约束，
因此该阶段不能只凭 P19 冻结宣称全项目完成；后续当前状态以 `docs/project-state.md` 为准。
