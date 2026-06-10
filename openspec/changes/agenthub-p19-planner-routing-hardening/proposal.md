## 为什么

P18c 暴露了一个关键的规划器路由缺口：API 规划器读取了图书馆管理应用请求的活跃内存规则，但返回了 `assistant_reply` 而非 `task_plan`，因此 AgentHub 仅创建了一条编排器聊天消息，从未创建 TaskRun。出现此问题的原因是 API 规划器提示词、Claude CLI 规划器提示词、确定性兜底逻辑以及规划器证据已逐渐演变为各自独立的行为来源。

在恢复 P18c 实时合规之前需要先完成 P19，因为 AgentHub 必须可靠地将明确的编码请求路由到经过验证的计划中，同时仍保留正常的聊天、澄清、拒绝、审批、目标注册表、PlanValidator 以及确定性兜底安全机制。

## 变更内容

- 创建一个由 API 规划器提供者和 Claude CLI 规划器共享的规范规划器提示词合约。
- 重写 API 提供者系统提示词，以匹配严格的 Claude CLI 规划器预期：
  - 构建/实现/创建软件请求必须返回 `task_plan`；
  - `task_plan` 必须包含完整的 `planDraft`；
  - 常规问候和能力询问返回 `assistant_reply`；
  - 不安全请求返回 `refusal` 或 `approval_required`；
  - 包含针对图书馆管理应用请求和问候的小样本示例。
- 通过让所有规划器提供者使用相同的规范提示词构建器和结构化合约描述，消除提供者特定的提示词漂移。
- 更改路由逻辑，使 LLM 非任务结果不会盲目短路安全的可执行请求：
  - 纯聊天的 `assistant_reply` 仍然仅创建编排器回复；
  - `clarification`、`refusal` 和 `approval_required` 保持不执行状态；
  - 对于确定性规划认为可执行的请求，`assistant_reply` 会继续进入确定性兜底或修复循环；
  - 兜底任务会通过规划器 source/reason 元数据以可审计方式标记。
- 增加规划器路由错误可观测性：
  - 记录 LLM 非任务结果与确定性可执行信号冲突的情况；
  - 记录 LLM 任务规划模式/PlanValidator 失败信息及错误摘要；
  - 在 Task、任务追踪和日志中暴露规划器证据，但不包含机密信息。
- 保留固定的确定性规划器作为兜底和回归基线，而非 AgentHub 的主要能力边界。
- 不添加硬编码的图书馆管理应用模板。

## 能力

### 新能力

- `planner-routing-hardening`：定义规范的规划器提示行为、LLM优先路由兜底、错误路由证据，以及针对非固定演示模板的明确编码请求的回归预期。

### 修改后的能力

- `orchestrator`：编排器路由必须将 LLM 视作主要规划器，同时在 LLM 返回非任务结果或无效计划时，为可执行请求保留确定性兜底。
- `real-coding-assistant`：当目标、路径、角色和命令策略均可验证时，真实编码请求不得局限于已知的演示模块。

## 影响

- 影响 `apps/api/app/planner_contracts.py`、
  `apps/api/app/planner_providers.py`、`apps/api/app/llm_planner.py`、
  `apps/api/app/planning.py`、`apps/api/app/mission_trace.py` 以及规划器
  证据 models/responses（在需要时）。
- 新增针对 API 提示词契约、Claude CLI/API 提示词一致性、
  助手回复误路由兜底、纯聊天保留、不安全非任务
  保留、PlanValidator 错误证据以及 P18c 库管理应用
  路由的测试。
- 可能更新 `docs/change-log.md`、`docs/project-state.md` 以及后续 P18c
  冻结证据（在实现后）。
- 不替换 Target Registry、PlanValidator、Scheduler、Guardrails、
  ClaudeCodeAdapter、CodexAdapter 或确定性兜底。
