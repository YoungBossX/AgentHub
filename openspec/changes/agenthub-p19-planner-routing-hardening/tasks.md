## 1. 规范规划器提示词合约

- [x] 1.1 提取一个由 API 规划器提供者和 Claude CLI 规划器共享的通用规划器提示构建器。
- [x] 1.2 重写 API 提供者提示，要求对安全的构建/实现/创建/开发/修改软件请求使用 `task_plan`。
- [x] 1.3 内联完整的 `ConversationOutcome` 和 `PlanDraft` 字段契约，包括角色、意图类型、制品类型、风险、审批、目标、计划文件、依赖项和验证期望。
- [x] 1.4 添加少量示例：问候语 -> `assistant_reply`，以及图书馆管理应用/库存类请求 -> `task_plan`。
- [x] 1.5 添加测试，证明 API 和 Claude CLI 提供者渲染相同的通用契约且不会发生偏离。
- [x] 1.6 验证目标规划器提示测试、`git diff --check` 和 `openspec validate agenthub-p19-planner-routing-hardening --strict`。

## 2. 以 LLM 为先的确定性兜底

- [x] 2.1 重构 `planning.py`，使得有效的非任务 LLM 输出不会在确定性规划之前始终硬返回。
- [x] 2.2 保留纯聊天行为：问候和能力询问仍生成编排器回复，且不产生 Task/TaskRun.。
- [x] 2.3 保留 `clarification`、`refusal` 和 `approval_required` 作为非执行输出，除非后续的显式审批流程创建了任务。
- [x] 2.4 对于可执行编码请求的 `assistant_reply`，继续进入确定性兜底或有限修复循环。
- [x] 2.5 使用 `plannerSource=fallback`、原因 `non_task_coding_outcome`、提供者元数据、原始输出类型和创建的任务 ID 标记兜底创建的任务。
- [x] 2.6 添加测试，确保被误分类为 `assistant_reply` 的安全外部前端请求会创建经过审计的兜底任务。
- [x] 2.7 添加测试，证明 unsafe/system/platform 请求和纯聊天不会兜底为前端任务。
- [x] 2.8 验证目标规划测试、`pnpm check`、`git diff --check` 以及 OpenSpec 严格验证。

## 3. 规划器误路由与验证证据

- [x] 3.1 为 LLM 输出类型、确定性可执行性、兜底原因、提供者 id/type/source/model/preset、验证结果和安全错误摘要添加规划器证据字段。
- [x] 3.2 记录来自 `task_plan` 输出的模式验证和 PlanValidator 失败信息，不暴露密钥或受保护路径。
- [x] 3.3 在任务计划 JSON 和任务追踪中暴露规划器路由错误证据，前提是现有响应模式支持。
- [x] 3.4 为 assistant_reply 路由错误证据和无效 `task_plan` 验证证据添加测试。
- [x] 3.5 验证目标证据测试、`pnpm check`、`git diff --check` 和 OpenSpec 严格验证。

## 4. 新型应用路由回归

- [x] 4.1 添加回归覆盖，确保已修复模块仍作为兜底基线，而非能力限制。
- [x] 4.2 添加 P18c 库管理应用路由测试，使用预置的外部前端目标和 LLM `assistant_reply` 误分类。
- [x] 4.3 验证生成的任务保留原始请求、保持目标范围、默认避免 backend/database，并记录兜底证据。
- [x] 4.4 确认缺失或不安全的目标请求不会写入任意 desktop/host 路径，而是要求目标设置或澄清。
- [x] 4.5 验证定向的新应用测试、`pnpm check`、`pnpm test`、`pnpm demo:api:test`、`git diff --check` 以及 OpenSpec 严格验证。

## 5. 冻结审查与恢复标准

- [x] 5.1 使用 P19 规划器路由加固状态更新 `docs/change-log.md` 和 `docs/project-state.md`。
- [x] 5.2 创建 `docs/p19-freeze-review.md`，记录提示词统一、兜底行为、证据字段、测试及剩余风险。
- [x] 5.3 使用加固后的规划器路径重新运行 P18c 库管理应用路由冒烟测试，直至任务创建环节。
- [x] 5.4 若真实编码提供程序运行，则记录 TaskRun 证据；若提供程序运行时失败，则记录确切的提供程序阻塞原因，不得声称符合实时合规要求。
- [x] 5.5 验证 `pnpm check`、`pnpm test`、`pnpm demo:api:test`、`git diff --check` 和 `openspec validate agenthub-p19-planner-routing-hardening --strict`。
- [x] 5.6 确认 P18c 保持暂停状态，直至 P19 冻结证据表明规划器路由不再是阻塞因素。
