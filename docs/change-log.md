# AgentHub 变更日志

## GitHub 首页文案中文化与诚实化

**日期:** 2026-06-10

### 变更

- `index.html` 首屏从英文泛化标题调整为中文主张“让 AI 编程可验证交付”，突出 AgentHub 的证据链价值。
- 将按钮、终端演示、统计区、功能卡片、流程和 CTA 改为中文优先文案。
- 移除或收敛过度承诺表述：不再使用 `100% Real Git Diffs & Previews`，不再声明真实 Agent 失败会自动降级到 Mock，不再暗示第三方部署成功。
- 补充更贴近当前实现的能力表达：文件快照 Diff、显式 fallback、Run/Artifact 证据链、诚实部署状态卡片。

### 验证

| 命令 | 结果 |
|---|---|
| `rg -n "Multi-Agent Coding Platform|Explore Features|100<span|Real Git Diffs|自动降级|未来支持真实部署" index.html` | 通过，无旧营销文案残留 |
| `git diff --check -- index.html docs/change-log.md` | 通过，仅 Windows 换行提示 |

## GitHub 提交范围放行

**日期:** 2026-06-10

### 变更

- 调整 `.gitignore`，允许 `openspec` 目录作为比赛过程证据进入 Git 跟踪。
- 保持 `docs` 目录默认忽略，仅明确放行 `docs/change-log.md`，避免一次性提交全部内部工作流文档。

### 验证

| 检查 | 结果 |
|---|---|
| `git check-ignore -v docs/change-log.md openspec/changes/agenthub-im-coding-mvp/proposal.md openspec/changes/agenthub-im-coding-mvp/specs/orchestrator/spec.md` | 三个路径均未被忽略 |

## 预览拒绝连接与死端口治理

**日期:** 2026-06-10

### 变更

- Vite 预览进程启动后会捕获 stdout/stderr 到诊断日志，失败时把最近输出写入 Preview artifact metadata、provider evidence 和 `artifact.preview.failed` 事件。
- 预览健康检查失败、进程提前退出或 API 重启后遗留的陈旧 `process_id`，会被标记为 failed/unhealthy，并清理进程引用，避免把不可达端口重新显示为可用。
- 右侧产物面板不再 iframe 嵌入 unhealthy/failed 预览，也不会允许打开不可达预览 URL；界面会展示诊断原因，并优先选择仍然 healthy 的预览 artifact。
- 在右侧面板刷新 failed/unhealthy 预览且没有 healthy 预览可用时，会重新启动一个新的预览，避免用户继续落到 `127.0.0.1:<port>` connection refused。

### 验证

| 命令 | 结果 |
|---|---|
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_previews.py tests/test_failure_recovery.py tests/test_cross_provider_rehearsal.py -q` | 通过，11 个测试 |
| `cd apps/web && pnpm test src/components/preview-card.test.tsx src/components/task-card-list.test.tsx -- --runInBand` | 通过，2 个测试文件 / 23 个测试 |
| `cd apps/api && ../../.venv/bin/python -m compileall app` | 通过 |
| `pnpm --filter @agenthub/web check` | 通过 |
| `git diff --check -- apps/api/app/previews.py apps/api/tests/test_previews.py apps/api/tests/test_failure_recovery.py apps/api/tests/test_cross_provider_rehearsal.py apps/web/src/components/preview-card.tsx apps/web/src/components/preview-card.test.tsx apps/web/src/components/task-card-list.tsx apps/web/src/components/task-card.tsx apps/web/src/components/workspace-shell.tsx docs/change-log.md` | 通过 |

## 显式 ScriptedMock fallback 调度修复

**日期:** 2026-06-10

### 变更

- RunWorker 执行 `force-codex-failure` 创建的 queued run 时，会在队列/锁检查后触发 Codex forced failure，不再依赖真实 Codex CLI 可用性。
- 已明确标记为 `scripted_mock` 的 fallback run 会直接使用 `ScriptedMockAdapter`，不再经过 provider resolver 被重新选择为真实 Codex/Claude provider。
- 恢复集成测试改为显式驱动 RunWorker，覆盖“强制 Codex 失败 -> ScriptedMock fallback -> Diff/Preview/Deploy”的新调度路径。

### 验证

| 命令 | 结果 |
|---|---|
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_failure_recovery.py -q` | 通过 |
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_task_runs.py::test_retry_with_scripted_mock_fallback_after_codex_failure tests/test_task_runs.py::test_force_codex_failure_queues_visible_run_through_scheduler tests/test_task_runs.py::test_background_execution_claims_and_refreshes_lease tests/test_scheduler.py::test_failed_codex_coding_task_exposes_fallback_available_state -q` | 通过，4 个测试 |
| `pnpm test` | 通过，Web 94 个测试 / API 622 个测试 / Demo API 5 个测试 |

## README 当前可用路径说明更新

**日期:** 2026-06-10

### 变更

- README 新增“实际新建一个全栈应用”流程，说明从空文件夹创建 frontend/backend 项目边界、绑定当前 Session、执行前后端 Agent 的通用路径。
- README 更新项目边界和当前可靠性能力，补充非 Git 外部项目 Diff/Review、target 写锁恢复、provider 诊断和 Review 中文证据面板说明。

### 验证

| 命令 | 结果 |
|---|---|
| `pnpm check` | 通过 |
| `pnpm test` | 通过，Web 94 个测试 / API 622 个测试 / Demo API 5 个测试 |
| `git diff --check` | 通过 |

## Review 证据面板中文化

**日期:** 2026-06-10

### 变更

- 右侧证据面板中的 Review Agent 标题、摘要、风险/严重级别、建议项和适配器标签改为中文展示。
- 对历史已生成的英文 Review artifact 增加前端展示层翻译，刷新页面即可看到中文，不需要重新执行任务。
- 补充组件测试覆盖“缺少验证证据”类 Review finding 的中文显示。

### 验证

| 命令 | 结果 |
|---|---|
| `cd apps/web && pnpm test src/components/preview-card.test.tsx -- --runInBand` | 通过，1 个测试文件 / 8 个测试 |
| `pnpm --filter @agenthub/web check` | 通过 |
| `git diff --check -- apps/web/src/components/preview-card.tsx apps/web/src/components/preview-card.test.tsx docs/change-log.md` | 通过 |

## 非 Git 新项目 Diff/Review 证据链修复

**日期:** 2026-06-10

### 变更

- 非 Git 外部项目 TaskRun 创建时会在 `preRunCheckpoint` 记录允许路径内的文件快照，用于执行后生成 Diff。
- `collect_task_run_diff` 在没有 Git `baseRef` 时支持基于文件快照生成统一 Diff artifact，继续复用现有 Review、ArtifactVersion、右侧证据面板链路。
- 对修复前已创建、没有文件快照的外部非 Git run，支持空基线补采 Diff，便于对已经生成的项目补出 Diff/Review。
- Diff/Review 收尾失败会写入 `artifact.diff.failed` / `artifact.review.failed` 事件，并在 Run Diagnostics 中归类为 artifact collection failed，避免 completed run 静默丢证据。

### 验证

| 命令 | 结果 |
|---|---|
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_diffs.py tests/test_task_runs.py::test_finalize_completed_task_run_runs_artifact_steps tests/test_task_runs.py::test_finalize_completed_task_run_records_artifact_failures_without_blocking_pipeline tests/test_task_runs.py::test_auto_start_next_pipeline_task_runs_external_downstream_task tests/test_run_diagnostics.py -q` | 通过，23 个测试 |
| `cd apps/api && ../../.venv/bin/python -m compileall app` | 通过 |
| `openspec validate agenthub-generic-new-project-runtime --strict` | 通过 |

## 会话主栏上下文卡片移除

**日期:** 2026-06-10

### 变更

- 移除会话主栏中的上下文/PMO 摘要卡片，避免遮挡聊天记录和底部 AI 对话输入栏。
- WorkspaceShell 不再为该卡片拉取 session ledger，减少主会话页的无用请求。
- 删除已无入口的 `MissionPanel` 组件及其专用测试。

### 验证

| 命令 | 结果 |
|---|---|
| `cd apps/web && pnpm test src/components/workspace-shell.test.tsx -- --runInBand` | 通过，1 个测试文件 / 10 个测试 |
| `pnpm --filter @agenthub/web check` | 通过 |

## 外部全栈任务自动衔接与 Setup 可见化

**日期:** 2026-06-10

### 变更

- 外部全栈 fallback planner 生成的 backend 任务现在会标记 `autoStart: true`，在 frontend 依赖完成后可自动进入后端执行链路。
- TaskRun 自动下游启动器现在支持 `orchestrator_external_target_v1`，并显式跳过触发它的 completed task，避免误重启上游任务。
- 新项目 provisioning plan/API response 新增结构化 `setupSteps`，包含角色、命令、工作目录、原因和审批标记。
- 运行设置页在新建全栈项目成功后展示依赖准备命令和对应目录，避免把 `node_modules` / Python 依赖缺失隐藏到 agent 执行阶段。

### 验证

| 命令 | 结果 |
|---|---|
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_planning.py::test_fullstack_requests_use_active_provisioned_targets_for_multiple_domains tests/test_task_runs.py::test_auto_start_next_pipeline_task_runs_external_downstream_task tests/test_project_provisioning.py::test_project_provisioning_api_returns_dry_run_plan tests/test_project_provisioning.py::test_project_provisioning_apply_scaffolds_registers_targets_and_activates_session -q` | 通过，6 个测试 |
| `cd apps/web && pnpm test src/lib/api.test.ts src/components/runtime-settings-page-client.test.tsx -- --runInBand` | 通过，2 个测试文件 / 42 个测试 |
| `cd apps/api && ../../.venv/bin/python -m compileall app` | 通过 |
| `pnpm check` | 通过 |
| `openspec validate agenthub-generic-new-project-runtime --strict` | 通过 |

## Provider 连接失败诊断修复

**日期:** 2026-06-10

### 变更

- 将 `Unable to connect`、`ConnectionRefused`、`connection refused`、`ECONNREFUSED` 等真实 CLI/API 连接失败文本归类为 provider unavailable。
- Provider Gateway 错误分类器现在会把 Claude/Codex 连接失败纳入可重试、可熔断的 provider 不可用错误，而不是 unknown。
- Run Diagnostics 现在会把 Claude Code API 连接失败显示为 provider unavailable，避免误导为 quota/rate limit。
- 修复 Run Diagnostics 对 UUID 中 `429` 片段的误判，避免把普通 trace/message id 识别成 provider quota。
- 新项目 Vite React 模板改用 `moduleResolution: Bundler`，补充 `@types/node` 与 `src/vite-env.d.ts`，并将 `tsBuildInfoFile` 放入 `node_modules/.tmp`，避免 TypeScript 6 / Vite 8 安装后 build 失败或污染项目根目录。

### 验证

| 命令 | 结果 |
|---|---|
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_run_diagnostics.py::test_connection_refused_provider_failure_is_not_reported_as_quota -q` | 通过 |
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_provider_gateway_contract.py::test_provider_error_classifier_treats_connection_refused_as_unavailable -q` | 通过 |
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_project_provisioning.py::test_project_provisioning_apply_scaffolds_registers_targets_and_activates_session -q` | 通过 |

## 前端新项目 Provisioning 接线

**日期:** 2026-06-10

### 变更

- 新增前端 API client，调用 `POST /workspaces/{workspaceId}/project-provisioning/apply`，请求字段为 `userRequest`、`selectedRootPath`、`preferredSlug`、`sessionId`。
- 在工作区 target settings 中为已选择的空文件夹新增通用“新建全栈项目”入口，保留原有外部项目注册和前端/后端单目标保存能力。
- Provisioning 成功后刷新 workspace targets，并按 response target IDs 或 session response 更新当前会话 active frontend/backend targets。
- 设置页 target 相关错误现在优先显示后端 `detail`。

### 验证

| 命令 | 结果 |
|---|---|
| `pnpm --filter web test -- apps/web/src/components/workspace-shell.test.tsx apps/web/src/lib/api.test.ts apps/web/src/components/runtime-settings-page-client.test.tsx` | 通过，14 个测试文件 / 94 个测试 |

## Target 写锁恢复优化

**日期:** 2026-06-10

### 变更

- 修复 adapter stream 直接写入 completed/failed/interrupted 终态时未同步释放 target 写锁和 session queue entry 的问题。
- 创建 TaskRun 前会先恢复由终态 holder 遗留的 stale target lock，避免已完成任务继续阻塞新任务。
- 前端 TaskRun mutation 现在会显示后端返回的具体错误 detail；普通网络失败仍保留 FastAPI 后端不可访问提示。

### 验证

| 命令 | 结果 |
|---|---|
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_target_locks.py tests/test_task_runs.py::test_adapter_completed_event_releases_target_lock tests/test_task_runs.py::test_create_task_run_recovers_terminal_holder_target_lock tests/test_task_runs.py::test_background_execution_waits_for_target_lock_without_starting_adapter -q` | 通过，7 个测试 |
| `pnpm --filter @agenthub/web test -- src/lib/api.test.ts -t "surfaces task run mutation error details"` | 通过 |
| `pnpm --filter @agenthub/web test -- src/components/workspace-shell.test.tsx -t "backend sync warning|concrete task run API errors"` | 通过 |

## 实际开发测试执行链路修复

**日期:** 2026-06-09

### 变更

- 修复 Provider Gateway 在 TaskRun 执行时没有优先使用运行设置 / 已存 provider assignment 的问题，确保前端、后端任务按用户配置解析到对应 coding provider。
- CodexAdapter 启动本地 Codex CLI 时增加 `--skip-git-repo-check`，允许在已注册但不是 Git 仓库根目录的新项目目标内执行。
- 扩展 LLM 失败或误路由后的外部目标兜底：当请求明显是新建前端 / 全栈开发任务且工作区已有外部 frontend/backend target 时，创建可执行任务而不是停留在聊天回复。
- 外部 `agenthub-rehearsals` 根目录目标的 coding agent 指令现在会根据用户请求推断专用子目录，避免后续新项目复用或覆盖已有演练项目。

### 验证

| 命令 | 结果 |
|---|---|
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_planning.py::test_fullstack_new_project_request_without_active_target_falls_back_to_external_tasks tests/test_planning.py::test_llm_assistant_reply_for_safe_external_frontend_request_falls_back_to_task tests/test_planning.py::test_p18c_library_request_misclassified_as_assistant_reply_routes_to_task tests/test_planning.py::test_llm_assistant_reply_for_platform_request_does_not_fallback_to_frontend -q` | 通过，4 个测试 |
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_task_runs.py::test_rehearsal_root_instruction_points_new_project_to_dedicated_subdirectory tests/test_task_runs.py::test_external_target_context_reaches_instruction_builder tests/test_task_runs.py::test_external_backend_instruction_uses_external_target_metadata -q` | 通过，3 个测试 |

## OpenSpec Delta Header 恢复

**日期:** 2026-06-09

### 变更

- 恢复 `openspec/changes/**/specs/**/spec.md` 中 OpenSpec delta 语法标题的英文机器标记。
- 保留需求标题、场景标题和正文的中文内容，仅将 `Requirements`、`Requirement:` 和 `Scenario:` 等 OpenSpec 解析关键字恢复为英文。
- 清理中文化后残留在标题中的全角冒号字节，确保 spec 文件保持有效 UTF-8。

### 验证

| 检查 | 结果 |
|---|---|
| 中文化 delta header 残留扫描 | 通过 |
| spec Markdown UTF-8 解码检查 | 通过 |
| `openspec validate --all --strict` | 通过，28 个 change |

## 项目工作区准备边界

**日期:** 2026-06-09

### 变更

- 新增共享的 Agent/Target 兼容性匹配，统一支持 `external-frontend-*` 与 `external-backend-*` 目标 ID，避免 PlanValidator、Agent Directory 和 AgentSelectionPolicy 规则漂移。
- 新增 dry-run 项目准备合约和 API，用于区分已有项目与新项目，并生成计划中的前端/后端 target 边界。
- 为新建 Vite React 前端和 FastAPI 后端生成默认 ProjectProfile、可验证命令和需要审批的安装命令。
- 扩展 PlannerResponse，可携带可选 `projectSetup` 元数据，让后续 Planner 能表达“先准备项目边界，再分派 coding tasks”。

### 验证

| 命令 | 结果 |
|---|---|
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_agent_target_compatibility.py tests/test_plan_validator_target_compatibility.py tests/test_project_provisioning.py tests/test_project_profiles.py tests/test_project_command_policy.py tests/test_external_workspaces.py tests/test_planner_contracts.py -q` | 通过，50 个测试 |
| `POST /workspaces/{workspace_id}/project-provisioning/plan` 健康管理系统请求 | 返回新项目 frontend/backend target 草案 |

## 文档中文化覆盖

**日期:** 2026-06-09

### 变更

- 使用 DeepSeek V4 Flash 将 `docs` 和 `openspec` 下的 Markdown 文档覆盖翻译为简体中文。
- 保留 Markdown 结构、代码块、命令、路径、URL、模型名、适配器名和 OpenSpec 关键字。
- 保留 `.openspec.yaml` 元数据文件不翻译，以避免破坏 OpenSpec 的 `schema` 和 `created` 字段。

### 验证

| 检查 | 结果 |
|---|---|
| Markdown 文件完成数 | 167/167 |
| 占位符残留扫描 | 通过 |
| Markdown 代码围栏奇偶检查 | 通过 |
| `.openspec.yaml` 元数据 | 保持原样 |

## V2.6-5 事务性交付证据集成

**日期:** 2026-06-09

### 变更

- 添加了一个辅助函数，用于将交付决策事件持久化为 TaskRunEvent。
- 更新了运行诊断阶段映射，使得 `delivery.review_required` 出现在验证阶段下，回滚事件出现在恢复阶段下。
- 添加了交付事件持久化和诊断时间线映射的测试。

### 验证

| 命令 | 结果 |
|---|---|
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_transactional_delivery.py tests/test_run_diagnostics.py -q` | 通过，21 个测试 |
| `pnpm check` | 通过 |
| `git diff --check` | 通过 |
| `openspec validate agenthub-v2-6-transactional-delivery --strict` | 通过 |

## V2.6-4 交付接受回滚重试

**日期:** 2026-06-09

### 变更

- 添加了交付制品状态、接受决策、回滚决策和显式重试模式证据辅助函数。
- 添加了测试，证明接受记录 diff/review/command/policy 证据 ID，回滚记录检查点路径，并且回滚会拒绝缺失的检查点。

### 验证

| 命令 | 结果 |
|---|---|
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_transactional_delivery.py -q` | 通过，12 个测试 |
| `pnpm check` | 通过 |
| `git diff --check` | 通过 |
| `openspec validate agenthub-v2-6-transactional-delivery --strict` | 通过 |

## V2.6-3 交付验证门禁

**日期:** 2026-06-09

### 变更

- 添加了交付验证证据和门禁辅助函数，将失败的命令、diff/review 或策略证据分类为 `review_required`。
- 添加了测试，证明干净的证据通过，而失败的命令证据、高风险审查证据和被拒绝的策略证据需要审查。

### 验证

| 命令 | 结果 |
|---|---|
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_transactional_delivery.py -q` | 通过，9 个测试 |
| `pnpm check` | 通过 |
| `git diff --check` | 通过 |
| `openspec validate agenthub-v2-6-transactional-delivery --strict` | 通过 |

## V2.6-2 事务性交付契约

**日期:** 2026-06-09

### 变更

- 添加了一个事务性交付契约，包含交付状态、重试模式、检查点证据、待定验证、回滚预检和重试模式决策。
- 添加了测试，证明检查点证据从 TaskRun 指标中读取，并且当不存在检查点时回滚被拒绝。

### 验证

| 命令 | 结果 |
|---|---|
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_transactional_delivery.py tests/test_recovery.py -q` | 通过，9 个测试 |
| `pnpm check` | 通过 |
| `git diff --check` | 通过 |
| `openspec validate agenthub-v2-6-transactional-delivery --strict` | 通过 |

## V2.5-4 策略证据与超时

**日期:** 2026-06-09

### 变更

- 添加了一个审批超时决策辅助函数，默认拒绝并保留安全的策略元数据。
- 添加了一个稳定的策略证据事件负载辅助函数，用于未来的 MissionTrace 和运行诊断集成。

### 验证

| 命令 | 结果 |
|---|---|
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_policy_engine.py -q` | 通过，12 个测试 |
| `pnpm check` | 通过 |
| `git diff --check` | 通过 |
| `openspec validate agenthub-v2-5-policy-engine --strict` | 通过 |

## V2.5-3 运行时策略评估辅助函数

**日期:** 2026-06-09

### 变更

- 添加了策略引擎辅助函数，用于命令、路径、网络、部署和平台维护决策，使用现有的目标注册表、护栏和项目命令策略语义。
- 保持辅助函数无副作用，并未替换当前的执行、审批或部署路径。

### 验证

| 命令 | 结果 |
|---|---|
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_policy_engine.py tests/test_guardrails.py tests/test_project_command_policy.py -q` | 通过，29 个测试 |
| `pnpm check` | 通过 |
| `git diff --check` | 通过 |
| `openspec validate agenthub-v2-5-policy-engine --strict` | 通过 |

## V2.5-2 策略引擎契约

**日期:** 2026-06-09

### 变更

- 添加了一个独立的策略引擎契约，包含策略类别、结果、风险级别、审批类型、决策证据和元数据编辑。
- 添加了允许、拒绝、需要审批、需要提升审批和 secret/protected-path 编辑的测试。

### 验证

| 命令 | 结果 |
|---|---|
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_policy_engine.py -q` | 通过，5 个测试 |
| `pnpm check` | 通过 |
| `git diff --check` | 通过 |
| `openspec validate agenthub-v2-5-policy-engine --strict` | 通过 |

## V2.4-5 ProjectProfile 指令上下文

**日期:** 2026-06-09

### 变更

- 将 ProjectProfile 元数据添加到编码代理目标指令上下文中，包括配置文件 ID、状态、预览策略和已配置的配置文件命令。
- 从目标摘要重建了配置文件上下文，不暴露机密或更改 PlanValidator/Target 注册表强制执行。

### 验证

| 命令 | 结果 |
|---|---|
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_task_runs.py::test_external_target_context_reaches_instruction_builder tests/test_task_runs.py::test_external_backend_instruction_uses_external_target_metadata -q` | 通过，2 个测试 |
| `pnpm check` | 通过 |
| `git diff --check` | 通过 |
| `openspec validate agenthub-v2-4-project-profile-boundary --strict` | 通过 |

## V2.4-4 配置文件命令策略覆盖

**日期:** 2026-06-09

### 变更

- 新增直接的项目命令策略覆盖验证，确保已配置的 target/profile 命令被允许，而缺失、不匹配、未知及未配置的通用仓库命令被拒绝。
- 确认通用仓库配置文件不会打开任意 shell 命令，仅允许显式配置的验证命令。

### 验证

| 命令 | 结果 |
|---|---|
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_project_command_policy.py tests/test_external_evidence.py -q` | 通过，11 个测试 |
| `pnpm check` | 通过 |
| `git diff --check` | 通过 |
| `openspec validate agenthub-v2-4-project-profile-boundary --strict` | 通过 |

## V2.4-3 项目配置文件目标注册表

**日期:** 2026-06-09

### 变更

- 将派生的项目配置文件摘要附加到外部目标 API 响应和工作区目标注册表响应中。
- 保留现有目标允许路径、拒绝路径、命令、审批和代理角色行为，同时使项目配置文件元数据可审计。

### 验证

| 命令 | 结果 |
|---|---|
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_external_workspaces.py tests/test_target_registry.py tests/test_project_profiles.py tests/test_project_analyzer.py -q` | 通过，31 个测试 |
| `pnpm check` | 通过 |
| `git diff --check` | 通过 |
| `openspec validate agenthub-v2-4-project-profile-boundary --strict` | 通过 |

## V2.4-2 项目配置文件契约

**日期:** 2026-06-09

### 变更

- 新增项目配置文件契约，用于规范化项目类型、框架、包管理器、allowed/denied 路径、命令、预览策略、置信度、状态和警告。
- 扩展外部项目分析器，附加项目配置文件摘要，同时保持现有分析字段的兼容性。
- 为 `projectProfile` 添加分析 API 输出，以便后续的目标注册、规划和命令策略工作能够使用统一的配置文件结构。

### 验证

| 命令 | 结果 |
|---|---|
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_project_profiles.py tests/test_project_analyzer.py -q` | 通过，11 个测试 |
| `pnpm check` | 通过 |
| `git diff --check` | 通过 |
| `openspec validate agenthub-v2-4-project-profile-boundary --strict` | 通过 |

## V2.2-4 提供者健康探针

**日期:** 2026-06-09

### 变更

- 为编码提供者新增 ProviderHealthProbe，使用安全的 `--version` 探针检查 Claude Code/Codex CLI 启动路径，以及 ScriptedMock 的 Vite 演示应用边界。
- 新增 `provider.health_checked` 事件和 TaskRun 指标记录辅助工具。
- 确保健康证据被编辑，且 ScriptedMock 的可用性不会使真实提供者显示为健康状态。
- 扩展提供者网关测试，覆盖健康、不可用、未知、编辑、ScriptedMock 演示边界以及健康证据持久化场景。

### 验证

| 命令 | 结果 |
|---|---|
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_provider_gateway_contract.py -q` | 通过，13 个测试 |
| `pnpm check` | 通过 |
| `pnpm demo:api:test` | 通过，5 个测试 |
| `git diff --check` | 通过 |
| `openspec validate agenthub-v2-2-provider-gateway --strict` | 通过 |

## V2.7 运行诊断后端投影

**日期:** 2026-06-09

### 变更

- 新增 TaskRun 的后端运行诊断投影，包含分类后的失败原因、影响因素、时间线条目、健康摘要和下一步建议。
- 暴露安全的只读诊断 API，用于单个 TaskRun 和会话摘要，不改变执行、提供者、调度器、预览或部署语义。
- 为诊断元数据添加编辑和截断功能，确保诊断响应不会返回密钥、令牌、受保护路径和主机路径。
- 新增后端测试，覆盖分类、时间线制品、健康摘要、建议、API 编辑、未知遗留证据和会话摘要。

### 验证

| 命令 | 结果 |
|---|---|
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_run_diagnostics.py -q` | 通过，7 个测试 |
| `pnpm check:demo-api` | 通过 |
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_task_runs.py -q` | 失败，71 通过 / 5 失败，位于 pre-existing/concurrent 运行调度期望中，超出此工作进程范围 |

## V2.2-3 提供者解析与注册表

**日期:** 2026-06-09

### 变更

- 新增基于现有 Claude Code、Codex 和 ScriptedMock 提供者配置派生的编码 ProviderRegistry，不添加适配器或包含 Planner 提供者。
- 新增 ProviderResolver 支持默认、显式和运行时编码提供者选择、兼容性检查、不可用提供者拒绝以及脚本化模拟兜底候选。
- 通过 `provider.resolved` 添加了提供者解析 event/metrics 的记录。
- 扩展了 Provider Gateway 测试，涵盖注册表元数据、解析路径、兜底候选、Planner 隔离以及 TaskRunEvent 证据。

### 验证

| 命令 | 结果 |
|---|---|
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_provider_gateway_contract.py -q` | 通过，8 个测试 |
| `pnpm check` | 通过 |
| `pnpm demo:api:test` | 通过，5 个测试 |
| `git diff --check` | 通过 |
| `openspec validate agenthub-v2-2-provider-gateway --strict` | 通过 |

## V2.2-2 Provider Gateway 契约

**日期：** 2026-06-09

### 变更

- 新增了一个仅编码的 Provider Gateway 契约模块，涵盖提供者元数据、解析计划、健康度、容量、速率限制占位符、熔断、错误分类、兜底证据、网关结果、事件名称以及安全的证据编辑。
- 新增了回归覆盖，证明网关证据保留了原始提供者故障以及脚本化模拟兜底，编辑了 secrets/protected 路径，并将 Planner 提供者排除在编码网关之外。

### 验证

| 命令 | 结果 |
|---|---|
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_provider_gateway_contract.py -q` | 通过，3 个测试 |
| `pnpm check` | 通过 |
| `pnpm demo:api:test` | 通过，5 个测试 |
| `git diff --check` | 通过 |
| `openspec validate agenthub-v2-2-provider-gateway --strict` | 通过 |

## V2.1-2 持久化运行执行边界

**日期：** 2026-06-09

### 变更

- 将 TaskRun 执行编排提取到 `apps/api/app/run_engine.py` 中，同时保留了现有的 BackgroundTasks 启动路径。
- 为后续的中断和超时工作添加了一个轻量级的 `run_supervisor.py` 生命周期注册表骨架。
- 将自动启动、手动运行创建和重试调度路由到一个共享的执行调度辅助函数。
- 新增了回归覆盖，证明运行端点使用了共享调度器和执行 registers/unregisters 以及监督者边界。

### 验证

| 命令 | 结果 |
|---|---|
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_task_runs.py -q` | 通过，65 个测试 |
| `pnpm check:api` | 通过 |
| `git diff --check` | 通过 |

## 运行时开发冒烟跟进

**日期：** 2026-06-09

### 变更

- 修复了规划跟进行为，使得历史 `failed`、`cancelled` 和 `completed` 任务不会阻塞同一会话中后续的用户请求。
- 新增了一个回归测试，证明先前失败的任务不再阻止新的外部前端请求创建兜底任务。
- 为 201/202 AgentHub 开发冒烟创建了一个桌面操作记录。

### 验证

| 命令 | 结果 |
|---|---|
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_planning.py::test_failed_prior_task_does_not_block_new_external_frontend_request -q` | 通过 |
| `git diff --check` | 通过 |

## P24-2 部署请求与状态证据

**日期：** 2026-06-08

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/api/app/deployments.py` | 添加了手动外部交接和不可用的外部部署提供者，这些提供者会持久化诚实的 handoff/blocked 证据。 |
| `apps/api/tests/test_deployments.py` | 为手动交接、被阻塞的外部提供者卡片、本地暂存兼容性以及无虚假成功添加了部署证据测试。 |
| `docs/project-state.md` | 记录了 P24-2 部署 request/status 证据状态。 |
| `openspec/changes/agenthub-p24-deployment-provider-status-cards/tasks.md` | 在验证后将 P24-2 任务标记为完成。 |

### 验证

| 命令 | 结果 |
|---|---|
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_deployments.py::test_manual_external_provider_persists_handoff_evidence tests/test_deployments.py::test_unavailable_external_provider_persists_blocked_evidence tests/test_deployments.py::test_local_staging_provider_builds_serves_and_persists_ready_artifact tests/test_deployments.py::test_deploy_api_creates_and_lists_mock_deployments tests/test_deployments.py::test_deploy_api_creates_blocked_external_provider_card -q` | 通过，5 个测试 |
| `pnpm check:demo-api` | 通过 |
| `git diff --check` | 通过 |

## P24-3 部署状态卡片 UI

**日期：** 2026-06-08

### 变更

- 升级了部署卡片，以显示本地化的 provider/status 元数据、提供者类型、环境、源 preview/diff/review 引用、日志和状态历史。
- 添加了明确的“被阻塞的外部提供者”和“手动交接”卡片状态，以便第三方部署请求看起来不像成功的生产部署。
- 仅当部署证据包含 URL 时，才添加“打开 URL”操作。
- 为就绪模拟、被阻塞的外部提供者和手动交接部署卡片状态添加了前端覆盖。

### 验证

| 命令 | 结果 |
|---|---|
| `pnpm --filter @agenthub/web test -- deploy-card.test.tsx preview-card.test.tsx task-card-list.test.tsx api.test.ts --runInBand` | 通过 |
| `pnpm check` | 通过 |

## P24-4 部署上下文与跟进

**日期：** 2026-06-08

### 变更

- 为提供者、提供者类型、环境、状态、URL、目标 ID、源 preview/diff/review ID、日志
摘要及状态历史。
- 在选定的制品上下文、制品引用或最新部署上下文进入之前，对类似机密的部署文本 log/status 进行脱敏处理。
- 新增部署卡片“作为上下文”操作，以便后续消息能复用对话路由器/规划器中的现有制品上下文路径。
- 为部署上下文元数据、脱敏处理以及后续上下文选择添加了前后端测试。

### 验证

| 命令 | 结果 |
|---|---|
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_task_runs.py -k "artifact_reference_context or deployment_artifact_reference" -q` | 通过 |
| `pnpm --filter @agenthub/web test -- task-card-list.test.tsx deploy-card.test.tsx api.test.ts --runInBand` | 通过 |

## P24 冻结审查

**日期：** 2026-06-08

### 变更

- 新增 `docs/p24-freeze-review.md` 文档，记录了 P24 范围、受限演练、验证以及延期的第三方部署限制。
- 在 OpenSpec 中将 P24 演练和冻结审查任务标记为完成。

### 验证

| 命令 | 结果 |
|---|---|
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_deployments.py -k "test_deploy_api_can_select_local_staging_provider or test_deploy_api_creates_blocked_external_provider_card" -q` | 通过 |

## P25-1 上下文项模型与标准化

**日期：** 2026-06-08

### 变更

- 新增后端上下文项标准化辅助函数，将显式的 `contextItems`、遗留的选定制品上下文以及引用的消息上下文映射到一个受限列表中。
- 为标题、摘要、选定文本、注释、元数据、受保护路径以及类似机密的字符串添加了脱敏和大小限制。
- 新增确定性测试，涵盖遗留兼容性、脱敏、截断、上下文项限制以及不支持的项类型。

### 验证

| 命令 | 结果 |
|---|---|
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_context_items.py -q` | 通过 |
| `pnpm check:api` | 通过 |

## P25-2 规划器上下文交接

**日期：** 2026-06-08

### 变更

- 将标准化的 `contextItems` 添加到会话上下文包以及规范/提供者可见的上下文中。
- 新增 `contextHandoff` 规划器证据，包含上下文项数量、项类型、制品 ID、版本 ID、部署 ID、来源、有效性和脱敏状态。
- 在任务追踪条目中暴露上下文交接元数据。
- 新增后端测试，证明上下文感知的 LLM 任务规划会记录上下文证据，并且上下文包交接在提供者可见的同时不会泄露受保护数据。

### 验证

| 命令 | 结果 |
|---|---|
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_planning.py -k "contextHandoff or Breakout" tests/test_task_runs.py::test_artifact_reference_context_supports_workbench_version_context -q` | 通过 |
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_task_runs.py::test_artifact_reference_context_supports_workbench_version_context -q` | 通过 |
| `pnpm check:api` | 通过 |

## P25-3 上下文托盘 UI

**日期：** 2026-06-08

### 变更

- 将编辑器中的单个选定制品/引用消息标签替换为紧凑的多项上下文托盘。
- 为暂存的上下文新增移除、上移、下移和清空控件。
- 通过将现有制品和引用消息操作映射为托盘项，保留了这些操作。
- 新增共享的编辑器负载构建器，在发送标准化的 `contextItems` 的同时，保留遗留的 `selectedArtifact` 和 `quotedMessage` 字段。
- 新增前端测试，涵盖多个上下文项、reorder/remove 控件以及负载结构。

### 验证

| 命令 | 结果 |
|---|---|
| `pnpm --filter @agenthub/web test -- message-composer.test.tsx task-card-list.test.tsx api.test.ts --runInBand` | 通过 |
| `pnpm check:web` | 通过 |

## P25-4 次级交互操作

**日期：** 2026-06-08

### 变更

- 新增 artifact/deployment 次级交互按钮，用于询问关于某个项的信息、基于该项进行修订，以及将其发送给编排器。
- 次级操作会将选定的项暂存到上下文托盘中并预填草稿；在用户发送消息之前不会执行任务。
- 新增路由回归测试，证明带有上下文项的纯聊天不会创建任务。
- 新增前端覆盖，涵盖新的操作标签和意图负载。

### 验证

| 命令 | 结果 |
|---|---|
| `pnpm --filter @agenthub/web test -- task-card-list.test.tsx message-composer.test.tsx --runInBand` | 通过 |
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_planning.py -k "pure_chat_with_context_items or contextHandoff" -q` | 通过 |
| `pnpm check` | 通过 |

## P25 冻结审查

**日期：** 2026-06-08

### 变更

- 新增 `docs/p25-freeze-review.md` 文档，记录了 P25 范围、受限上下文演练、验证和限制。
- 新增一个确定性冻结演练测试，针对组合了部署、差异、制品版本和引用消息上下文的负载。
- 在 OpenSpec 中将 P25 演练和冻结任务标记为完成。

### 验证

| 命令 | 结果 |
|---|---|
| `pnpm --filter @agenthub/web test -- message-composer.test.tsx --runInBand` | 通过 |
| `openspec validate agenthub-p24-deployment-provider-status-cards --strict` | 通过 |

---

## P24-1 部署提供商注册表

**日期:** 2026-06-08

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/api/app/deployment_providers.py` | 为本地预发布、手动外部移交、Vercel、Netlify 和自定义静态主机添加了安全的部署提供商元数据。 |
| `apps/api/app/schemas.py` | 添加了部署提供商注册表响应模式。 |
| `apps/api/app/main.py` | 添加了 `/deployment-providers` API 路由。 |
| `apps/api/tests/test_deployment_providers.py` | 为默认值、基于环境变量的可用性和密钥编辑添加了注册表测试。 |
| `docs/project-state.md` | 记录了 P24-1 部署提供商注册表状态。 |
| `openspec/changes/agenthub-p24-deployment-provider-status-cards/tasks.md` | 验证后将 P24-1 任务标记为完成。 |

### 验证

| 命令 | 结果 |
|---|---|
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_deployment_providers.py tests/test_deployments.py::test_deploy_provider_result_records_standard_metadata -q` | 通过，5 个测试 |
| `pnpm check:demo-api` | 通过 |
| `git diff --check` | 通过 |
| `openspec validate agenthub-p24-deployment-provider-status-cards --strict` | 通过 |

---

## P23-6 聊天上下文中的制品引用

**日期:** 2026-06-08

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/api/app/models.py` | 为可审计的消息级上下文添加了 `Message.context_json`。 |
| `apps/api/app/db.py` | 为消息上下文添加了 SQLite 兼容列。 |
| `apps/api/app/schemas.py` | 在消息创建请求中添加了 `context`。 |
| `apps/api/app/main.py` | 在消息创建时持久化了消息上下文。 |
| `apps/api/app/artifact_references.py` | 为 markdown/text/code 制品、版本 ID、选中文本、安全摘要和元数据编辑添加了 P23 制品引用支持。 |
| `apps/api/app/context_pack.py` | 将创建消息的上下文合并到会话上下文包和选中的制品元数据中。 |
| `apps/api/tests/test_task_runs.py` | 为工作台制品版本上下文和编辑添加了后端覆盖。 |
| `apps/api/tests/test_models.py` | 更新了消息 model/schema 对上下文的期望。 |
| `apps/web/src/lib/api.ts` | 为聊天发送添加了消息上下文负载支持。 |
| `apps/web/src/lib/api.test.ts` | 为消息上下文负载添加了前端 API 覆盖。 |
| `apps/web/src/components/workspace-shell.tsx` | 在后续消息中发送选中的 artifact/version 和引用的消息上下文。 |
| `docs/project-state.md` | 记录了 P23-6 制品引用上下文状态。 |
| `openspec/changes/agenthub-p23-artifact-preview-editing-workbench/tasks.md` | 验证后将 P23-6 任务标记为完成。 |

### 验证

| 命令 | 结果 |
|---|---|
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_task_runs.py::test_artifact_reference_context_supports_workbench_version_context tests/test_task_runs.py::test_artifact_reference_context_rejects_unsupported_artifact_type tests/test_models.py::test_p0_model_boundary_and_required_fields tests/test_models.py::test_message_create_request_populates_by_alias tests/test_models.py::test_message_create_request_defaults_are_preserved -q` | 通过，5 个测试 |
| `pnpm --filter @agenthub/web test -- api.test.ts message-composer.test.tsx workspace-shell.test.tsx preview-card.test.tsx --runInBand` | 通过，84 个测试 |
| `pnpm check` | 通过 |
| `git diff --check` | 通过 |
| `openspec validate agenthub-p23-artifact-preview-editing-workbench --strict` | 通过 |

---

## P23-5 制品编辑器与版本历史 UI

**日期:** 2026-06-08

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/web/src/lib/api.ts` | 添加了制品工作台编辑输入和保存 API 辅助函数。 |
| `apps/web/src/lib/api.test.ts` | 添加了将制品编辑保存为新版本的客户端覆盖。 |
| `apps/web/src/components/preview-card.tsx` | 为可编辑的工作台制品添加了编辑、保存、取消、内容编辑器、摘要输入和版本历史控件。 |
| `apps/web/src/components/preview-card.test.tsx` | 添加了对保存、取消、版本历史和只读未知制品兜底的覆盖。 |
| `apps/web/src/components/workspace-shell.tsx` | 将制品编辑保存连接到工作台 API 和刷新路径。 |
| `apps/web/src/components/workspace-shell.test.tsx` | 为 shell 测试添加了保存 API 模拟覆盖。 |
| `docs/project-state.md` | 记录了 P23-5 制品编辑器 UI 状态。 |
| `openspec/changes/agenthub-p23-artifact-preview-editing-workbench/tasks.md` | 验证后将 P23-5 任务标记为完成。 |

### 验证

| 命令 | 结果 |
|---|---|
| `pnpm --filter @agenthub/web test -- preview-card.test.tsx api.test.ts workspace-shell.test.tsx --runInBand` | 通过，83 个测试 |
| `pnpm check` | 通过 |
| `git diff --check` | 通过 |
| `openspec validate agenthub-p23-artifact-preview-editing-workbench --strict` | 通过 |

---

## P23-4 制品工作台 UI

**日期:** 2026-06-08

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/web/src/lib/api.ts` | 添加了制品工作台响应类型和会话工作台 API 辅助函数。 |
| `apps/web/src/lib/api.test.ts` | 新增会话制品工作台加载的客户端覆盖。 |
| `apps/web/src/components/preview-card.tsx` | 扩展右侧制品面板，增加对 text/markdown/code/unknown 制品和版本元数据的工作台渲染器支持。 |
| `apps/web/src/components/preview-card.test.tsx` | 新增工作台 Markdown 渲染和未知兜底的 UI 覆盖。 |
| `apps/web/src/components/workspace-shell.tsx` | 加载会话工作台元数据，并与现有证据卡片合并，避免重复 diff/review/preview/deploy 制品。 |
| `apps/web/src/components/workspace-shell.test.tsx` | 为 Shell 测试新增默认工作台 API 模拟。 |
| `docs/project-state.md` | 记录 P23-4 制品工作台 UI 状态。 |
| `openspec/changes/agenthub-p23-artifact-preview-editing-workbench/tasks.md` | 验证后将 P23-4 任务标记为完成。 |

### 验证

| 命令 | 结果 |
|---|---|
| `pnpm --filter @agenthub/web test -- preview-card.test.tsx api.test.ts workspace-shell.test.tsx --runInBand` | 通过，81 个测试 |
| `pnpm check` | 通过 |
| `git diff --check` | 通过 |
| `openspec validate agenthub-p23-artifact-preview-editing-workbench --strict` | 通过 |

---

## P23-3 安全制品编辑 API

**日期：** 2026-06-08

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/api/app/models.py` | 为 ArtifactVersion 字段新增父版本、内容、内容哈希和编辑器来源。 |
| `apps/api/app/db.py` | 为现有 ArtifactVersion 表新增 SQLite 兼容列。 |
| `apps/api/app/artifact_versions.py` | 扩展存储的制品版本辅助函数，以保留已编辑制品的内容元数据。 |
| `apps/api/app/artifact_workbench.py` | 新增安全制品编辑辅助函数，可在不写入仓库的情况下创建新版本。 |
| `apps/api/app/main.py` | 新增工作台编辑 API 路由。 |
| `apps/api/app/schemas.py` | 新增编辑请求模式，并扩展工作台版本响应元数据。 |
| `apps/api/tests/test_artifact_workbench_edit_api.py` | 新增 API 测试，覆盖可编辑保存、不支持拒绝、无差异创建和不可变先前版本。 |
| `apps/api/tests/test_models.py` | 新增 model/schema 兼容性覆盖，用于 ArtifactVersion 编辑列。 |
| `docs/project-state.md` | 记录 P23-3 安全制品编辑 API 状态。 |
| `openspec/changes/agenthub-p23-artifact-preview-editing-workbench/tasks.md` | 验证后将 P23-3 任务标记为完成。 |

### 验证

| 命令 | 结果 |
|---|---|
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_artifact_workbench_edit_api.py tests/test_artifact_workbench_api.py tests/test_artifact_workbench.py tests/test_diffs.py::test_artifact_versions_support_followup_v2_parent_chain tests/test_models.py::test_p0_model_boundary_and_required_fields tests/test_models.py::test_sqlite_schema_compatibility_adds_artifact_version_edit_columns -q` | 通过，15 个测试 |
| `pnpm check:demo-api` | 通过 |
| `git diff --check` | 通过 |
| `openspec validate agenthub-p23-artifact-preview-editing-workbench --strict` | 通过 |

---

## P23-2 制品工作台 API

**日期：** 2026-06-08

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/api/app/artifact_workbench.py` | 新增基于数据库的制品工作台列表、制品详情和版本元数据查找辅助函数。 |
| `apps/api/app/main.py` | 新增会话制品工作台、制品工作台详情、版本列表和版本详情 API 路由。 |
| `apps/api/app/schemas.py` | 新增工作台专用的制品和版本响应模式，包含安全元数据和内容哈希。 |
| `apps/api/tests/test_artifact_workbench_api.py` | 新增 API 覆盖，涵盖列表、详情、版本查找、未知制品兜底、编辑和 404 行为。 |
| `docs/project-state.md` | 记录 P23-2 制品工作台 API 状态。 |
| `openspec/changes/agenthub-p23-artifact-preview-editing-workbench/tasks.md` | 验证后将 P23-2 任务标记为完成。 |

### 验证

| 命令 | 结果 |
|---|---|
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_artifact_workbench_api.py tests/test_artifact_workbench.py tests/test_diffs.py::test_artifact_versions_support_followup_v2_parent_chain -q` | 通过，9 个测试 |
| `pnpm check:demo-api` | 通过 |
| `git diff --check` | 通过 |
| `openspec validate agenthub-p23-artifact-preview-editing-workbench --strict` | 通过 |

---

## P23-1 制品版本元数据基础

**日期：** 2026-06-08

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/api/app/artifact_workbench.py` | 新增制品渲染器分类、可编辑标志、安全元数据编辑、内容哈希和版本元数据辅助函数。 |
| `apps/api/tests/test_artifact_workbench.py` | 新增后端覆盖，涵盖 supported/unknown 渲染器、可编辑规则、编辑、内容哈希、版本元数据和遗留制品。 |
| `docs/project-state.md` | 记录 P23-1 制品元数据基础状态。 |
| `openspec/changes/agenthub-p23-artifact-preview-editing-workbench/tasks.md` | 验证后将 P23-1 任务标记为完成。 |

### 验证

| 命令 | 结果 |
|---|---|
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_artifact_workbench.py tests/test_diffs.py::test_artifact_versions_support_followup_v2_parent_chain -q` | 待处理 |
| `pnpm check:demo-api` | 待处理 |
| `git diff --check` | 待处理 |
| `openspec validate agenthub-p23-artifact-preview-editing-workbench --strict` | 待处理 |

---

## P22 冻结审查

**日期：** 2026-06-08

### 修改的文件

| 文件 | 变更 |
|---|---|
| `docs/p22-freeze-review.md` | 记录了 P22 排练证据、验证计划、限制和冻结状态。 |
| `docs/project-state.md` | 记录了 P22 冻结状态。 |
| `docs/change-log.md` | 添加了此冻结审查条目。 |
| `openspec/changes/agenthub-p22-agent-directory-custom-agent-foundation/tasks.md` | 验证后将 P22 冻结审查任务标记为完成。 |

### 验证

| 命令 | 结果 |
|---|---|
| `pnpm check` | 通过 |
| `pnpm test` | 通过，78 个 Web 测试，466 个 API 测试，5 个演示 API 测试 |
| `pnpm demo:api:test` | 通过，5 个测试 |
| `git diff --check` | 通过 |
| `openspec validate agenthub-p22-agent-directory-custom-agent-foundation --strict` | 通过 |

---

## P22-6 草稿代理 UI

**日期：** 2026-06-08

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/web/src/lib/api.ts` | 添加了安全的草稿代理创建输入和 API 辅助函数。 |
| `apps/web/src/lib/api.test.ts` | 增加了对安全草稿创建负载和验证错误展示的覆盖。 |
| `apps/web/src/components/agent-directory-settings-page-client.tsx` | 添加了一个仅包含元数据的安全草稿表单，包含 save/cancel 控件，并在保存后仅在本地显示草稿。 |
| `apps/web/src/components/agent-directory-settings-page-client.test.tsx` | 增加了对保存、取消、验证错误以及缺少任意 shell/tool 权限控件的覆盖。 |
| `apps/web/src/app/settings/agents/page.tsx` | 将后端 URL 传递给客户端页面以用于草稿创建。 |
| `docs/project-state.md` | 记录了 P22-6 草稿 UI 状态。 |
| `openspec/changes/agenthub-p22-agent-directory-custom-agent-foundation/tasks.md` | 验证后将 P22-6 草稿代理 UI 任务标记为完成。 |

### 验证

| 命令 | 结果 |
|---|---|
| `pnpm --filter @agenthub/web test -- agent-directory-settings-page-client.test.tsx api.test.ts --runInBand` | 通过，78 个测试 |
| `pnpm check` | 待处理 |
| `git diff --check` | 待处理 |
| `openspec validate agenthub-p22-agent-directory-custom-agent-foundation --strict` | 待处理 |

---

## P22-5 代理目录 UI

**日期：** 2026-06-08

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/web/src/lib/api.ts` | 添加了代理目录响应类型和 `getWorkspaceAgentDirectory`。 |
| `apps/web/src/lib/api.test.ts` | 增加了对加载包含兼容性元数据的目录条目的覆盖。 |
| `apps/web/src/app/settings/agents/page.tsx` | 添加了专用的代理目录设置页面。 |
| `apps/web/src/components/agent-directory-settings-page-client.tsx` | 添加了联系人样式的代理目录卡片、provider/status/capability/target 元数据、兼容性原因和过滤器。 |
| `apps/web/src/components/agent-directory-settings-page-client.test.tsx` | 增加了对卡片、过滤器、unavailable/draft 状态和元数据展示的 UI 覆盖。 |
| `apps/web/src/components/session-sidebar.tsx` | 在聊天侧边栏中添加了一个指向代理目录的设置链接，而不在聊天中暴露详细配置。 |
| `apps/web/src/components/workspace-shell.test.tsx` | 更新了设置导航覆盖以包含代理目录链接。 |
| `docs/project-state.md` | 记录了 P22-5 UI 状态。 |
| `openspec/changes/agenthub-p22-agent-directory-custom-agent-foundation/tasks.md` | 验证后将 P22-5 代理目录 UI 任务标记为完成。 |

### 验证

| 命令 | 结果 |
|---|---|
| `pnpm --filter @agenthub/web test -- agent-directory-settings-page-client.test.tsx workspace-shell.test.tsx api.test.ts --runInBand` | 通过，73 个测试 |
| `pnpm check` | 待处理 |
| `git diff --check` | 待处理 |
| `openspec validate agenthub-p22-agent-directory-custom-agent-foundation --strict` | 待处理 |

---

## P22-4 运行时配置兼容性集成

**日期：** 2026-06-08

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/api/app/agent_directory.py` | 打破了运行时导入循环，以便兼容性辅助函数可以安全地共享。 |
| `apps/api/app/agent_runtime_config.py` | 复用了代理目录兼容性检查，用于前端、后端和审查运行时选择，同时保留独立的 Planner 提供者验证。 |
| `apps/api/tests/test_agent_runtime_config.py` | 增加了对兼容的目录支持运行时选择、草稿拒绝、仅验证拒绝而不持久化以及现有 Planner 运行时兼容性的覆盖。 |
| `docs/project-state.md` | 记录了 P22-4 运行时配置集成状态。 |
| `openspec/changes/agenthub-p22-agent-directory-custom-agent-foundation/tasks.md` | 验证后将 P22-4 运行时配置集成任务标记为完成。 |

### 验证

| 命令 | 结果 |
|---|---|
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_agent_runtime_config.py tests/test_agent_directory.py tests/test_agent_selection_policy.py -q` | 待处理 |
| `pnpm check:demo-api` | 待处理 |
| `git diff --check` | 待处理 |
| `openspec validate agenthub-p22-agent-directory-custom-agent-foundation --strict` | 待处理 |

---

## P22-3 安全草稿代理管理

**日期：** 2026-06-08

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/api/tests/test_agent_profile_drafts.py` | 为工作区范围的草稿列表、save/no-op 行为以及不持久化拒绝不安全草稿增加了确定性覆盖。 |
| `apps/api/tests/test_agent_directory.py` | 增加了覆盖，确保草稿目录条目在验证前保持不兼容状态。 |
| `docs/project-state.md` | 记录了 P22-3 安全草稿状态。 |
| `openspec/changes/agenthub-p22-agent-directory-custom-agent-foundation/tasks.md` | 验证后将 P22-3 安全草稿任务标记为完成。 |

### 验证

| 命令 | 结果 |
|---|---|
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_agent_profile_drafts.py tests/test_agent_directory.py -q` | 待处理 |
| `pnpm check:demo-api` | 待处理 |
| `git diff --check` | 待处理 |
| `openspec validate agenthub-p22-agent-directory-custom-agent-foundation --strict` | 待处理 |

---

## P22-2 代理兼容性策略

**日期：** 2026-06-08

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/api/app/agent_directory.py` | 增加了对提供商可用性、适配器、角色、目标、模式、能力、write/review 安全性和草稿状态的兼容性检查。 |
| `apps/api/app/main.py` | 增加了工作区范围的代理目录兼容性检查端点。 |
| `apps/api/app/schemas.py` | 增加了兼容性 request/response 模式以及目录条目上的兼容性元数据。 |
| `apps/api/tests/test_agent_directory.py` | 增加了对兼容前端选择和不兼容草稿原因的覆盖。 |
| `openspec/changes/agenthub-p22-agent-directory-custom-agent-foundation/tasks.md` | 验证后将 P22-2 兼容性策略任务标记为完成。 |

### 验证

| 命令 | 结果 |
|---|---|
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_agent_directory.py tests/test_agent_runtime_config.py tests/test_agent_selection_policy.py -q` | 通过，27 个测试 |
| `pnpm check:demo-api` | 通过 |
| `git diff --check` | 通过 |
| `openspec validate agenthub-p22-agent-directory-custom-agent-foundation --strict` | 通过 |

---

## P22-1 代理目录后端

**日期：** 2026-06-08

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/api/app/agent_directory.py` | 从配置文件、提供商、运行时配置和草稿元数据中派生出代理目录服务条目。 |
| `apps/api/app/main.py` | 增加了工作区范围的代理目录 API 响应辅助函数和端点。 |
| `apps/api/app/schemas.py` | 增加了代理目录响应模式。 |
| `apps/api/tests/test_agent_directory.py` | 增加了对内置条目、草稿条目、运行时选择的角色、提供商可用性、未知工作区拒绝和无密钥元数据的覆盖。 |
| `openspec/changes/agenthub-p22-agent-directory-custom-agent-foundation/tasks.md` | 验证后将 P22-1 后端目录任务标记为完成。 |

### 验证

| 命令 | 结果 |
|---|---|
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_agent_directory.py tests/test_agent_profile_drafts.py tests/test_provider_configs.py tests/test_agent_runtime_config.py -q` | 通过，27 个测试 |
| `pnpm check:demo-api` | 通过 |
| `git diff --check` | 通过 |
| `openspec validate agenthub-p22-agent-directory-custom-agent-foundation --strict` | 通过 |

---

## P21 冻结审查

**日期：** 2026-06-08

### 修改的文件

| 文件 | 变更 |
|---|---|
| `docs/p21-freeze-review.md` | 记录了 P21 PMO 演练证据、验证结果和限制。 |
| `docs/project-state.md` | 记录了最终的 P21 冻结状态。 |
| `docs/change-log.md` | 添加了此冻结审查条目。 |
| `openspec/changes/agenthub-p21-main-agent-orchestrator-pmo/tasks.md` | 将 P21 冻结审查任务标记为完成。 |

### 验证

| 命令 | 结果 |
|---|---|
| `pnpm check` | 通过 |
| `pnpm test` | 通过，70 个 Web 测试，460 个 API 测试，5 个演示 API 测试 |
| `pnpm demo:api:test` | 通过，5 个测试 |
| `git diff --check` | 通过 |
| `openspec validate agenthub-p21-main-agent-orchestrator-pmo --strict` | 通过 |

---

## P21-5 PMO 工作区 UI

**日期：** 2026-06-08

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/web/src/lib/api.ts` | 为批准、拒绝和澄清操作添加了 PMO 计划决策 API 辅助函数。 |
| `apps/web/src/components/task-card-list.tsx` | 在任务卡片上添加了 PMO 决策显示和计划 approve/reject/clarification 控件。 |
| `apps/web/src/components/mission-panel.tsx` | 添加了基于当前任务的紧凑型 PMO 就绪状态和下一步操作摘要。 |
| `apps/web/src/components/workspace-shell.tsx` | 将 PMO 计划决策控件连接到后端操作和任务刷新。 |
| `apps/web/src/components/task-card-list.test.tsx` | 添加了 PMO 决策卡片和操作回调的覆盖。 |
| `apps/web/src/components/mission-panel.test.tsx` | 添加了任务面板 PMO 就绪状态和下一步操作摘要的覆盖。 |
| `openspec/changes/agenthub-p21-main-agent-orchestrator-pmo/tasks.md` | 标记 P21-5 UI 任务在针对性验证后完成。 |

### 验证

| 命令 | 结果 |
|---|---|
| `pnpm --filter @agenthub/web test -- task-card-list.test.tsx mission-panel.test.tsx --runInBand` | 通过，70 项测试 |
| `pnpm check` | 通过 |

---

## P21-4 PMO 任务追踪证据

**日期:** 2026-06-08

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/api/app/mission_trace.py` | 添加了经过编辑的 PMO 协调证据，用于计划决策、阻塞项、兜底方案和冲突摘要。 |
| `apps/api/app/schemas.py` | 在任务追踪响应中添加了 `pmoEvidence`。 |
| `apps/api/tests/test_pmo_decisions.py` | 增加了覆盖范围，确保 PMO 证据包含 decision/blocker/fallback/conflict 记录，同时不泄露机密或受保护的主机路径。 |
| `openspec/changes/agenthub-p21-main-agent-orchestrator-pmo/tasks.md` | 标记 P21-4 任务追踪证据任务在针对性验证后完成。 |

### 验证

| 命令 | 结果 |
|---|---|
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_pmo_decisions.py -q` | 通过，14 项测试 |
| 任务追踪回归子集 | 通过，4 项测试 |
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_llm_planner.py::test_api_planner_provider_output_flows_through_plan_validator -q` | 通过，1 项测试 |

---

## P21-3 PMO 图谱就绪状态与后续行动

**日期:** 2026-06-08

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/api/app/mission_trace.py` | 添加了 PMO 派生的任务图谱就绪状态分组，以及针对就绪任务、阻塞项、计划审查、重试、兜底方案和审批的更丰富的后续行动。 |
| `apps/api/app/schemas.py` | 在任务追踪响应中添加了 `taskGraphReadiness`。 |
| `apps/api/tests/test_pmo_decisions.py` | 增加了对 PMO 就绪状态分组以及从当前 task/run/scheduler 状态推导后续行动的覆盖范围。 |
| `openspec/changes/agenthub-p21-main-agent-orchestrator-pmo/tasks.md` | 标记 P21-3 图谱就绪状态和后续行动任务在针对性验证后完成。 |

### 验证

| 命令 | 结果 |
|---|---|
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_pmo_decisions.py -q` | 通过，13 项测试 |
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_task_runs.py::test_session_mission_trace_exposes_tasks_artifacts_and_blockers tests/test_task_runs.py::test_provider_assignment_is_visible_in_mission_trace tests/test_task_runs.py::test_runtime_config_resolution_is_visible_in_mission_trace tests/test_llm_planner.py::test_llm_planner_input_includes_followup_mission_trace -q` | 通过，4 项测试 |

---

## P21-2 PMO 计划决策操作

**日期:** 2026-06-08

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/api/app/main.py` | 添加了狭窄的批准、拒绝和请求澄清的任务计划决策端点，这些端点更新 PMO 元数据而不创建 TaskRun。 |
| `apps/api/app/schemas.py` | 添加了严格的 PMO 计划决策请求模式，拒绝原始计划修改字段。 |
| `apps/api/tests/test_pmo_decisions.py` | 增加了对批准、拒绝、澄清、不创建 TaskRun 以及拒绝原始修改的 API 覆盖范围。 |
| `openspec/changes/agenthub-p21-main-agent-orchestrator-pmo/tasks.md` | 标记 P21-2 计划决策操作任务在针对性验证后完成。 |

### 验证

| 命令 | 结果 |
|---|---|
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_pmo_decisions.py -q` | 通过，11 项测试 |

---

## P21-1 PMO 决策元数据基础

**日期:** 2026-06-08

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/api/app/pmo_decisions.py` | 添加了稳定的 PMO 计划决策元数据辅助函数，用于待审查、已批准、已拒绝和需要澄清状态。 |
| `apps/api/app/mission_trace.py` | 在任务追踪任务条目中暴露了任务 `pmoDecision` 元数据。 |
| `apps/api/tests/test_pmo_decisions.py` | 添加了针对 PMO 决策元数据、不支持的原始修改拒绝以及任务追踪可见性的确定性测试。 |
| `openspec/changes/agenthub-p21-main-agent-orchestrator-pmo/tasks.md` | 标记 P21-1 元数据基础任务在针对性验证后完成。 |

### 验证

| 命令 | 结果 |
|---|---|
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_pmo_decisions.py -q` | 通过，7 项测试 |

---

## P20-5 制品导航工作台

**日期:** 2026-06-08

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/web/src/components/task-card-list.tsx` | 将制品卡片重命名为面向用户的证据卡片，本地化制品操作，并澄清了部署证据的措辞。 |
| `apps/web/src/components/preview-card.tsx` | 改进了制品面板的空状态以及针对 Diff、Review、Preview 和 Deployment 制品的导航文案。 |
| `apps/web/src/components/task-card-list.test.tsx` | 更新了制品 navigation/context 测试，以使用更清晰的证据卡片标签。 |
| `apps/web/src/components/preview-card.test.tsx` | 增加了对制品工作台空状态的覆盖范围。 |
| `openspec/changes/agenthub-p20-daily-agent-workspace-ux/tasks.md` | 标记 P20-5 实现任务已完成，待验证。 |

### 验证

| 命令 | 结果 |
|---|---|
| `pnpm --filter @agenthub/web test -- task-card-list.test.tsx preview-card.test.tsx --runInBand` | 通过，68 项测试 |

---

## P20-4 智能体、目标、记忆与证据摘要

**日期：** 2026-06-08

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/web/src/components/mission-panel.tsx` | 新增了紧凑的 frontend/backend 目标、记忆快照、最新证据、适配器、文件及部署 provider/status 摘要。 |
| `apps/web/src/components/workspace-shell.tsx` | 将选定的会话传递到 mission/context 面板，以便在不修改 API 的情况下总结目标和记忆状态。 |
| `apps/web/src/components/workspace-shell.test.tsx` | 新增了对目标、记忆快照、部署提供商、适配器及最新证据摘要渲染的覆盖。 |
| `openspec/changes/agenthub-p20-daily-agent-workspace-ux/tasks.md` | 将 P20-4 实现任务标记为完成，待验证。 |

### 验证

| 命令 | 结果 |
|---|---|
| `pnpm --filter @agenthub/web test -- workspace-shell.test.tsx --runInBand` | 通过，67 项测试 |

---

## P20-3 只读计划审查界面

**日期：** 2026-06-08

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/web/src/components/task-card-list.tsx` | 在只读计划审查界面内，新增了用户可读的规划器证据，包括兜底、验证结果、提供商 ID、错误代码及安全错误摘要。 |
| `apps/web/src/components/task-card-list.test.tsx` | 新增了对规划器兜底和验证证据渲染的覆盖，与现有计划审查元数据一同展示。 |
| `openspec/changes/agenthub-p20-daily-agent-workspace-ux/tasks.md` | 将 P20-3 实现任务标记为完成，待验证。 |

### 验证

| 命令 | 结果 |
|---|---|
| `pnpm --filter @agenthub/web test -- task-card-list.test.tsx --runInBand` | 通过，67 项测试 |

---

## P20-2 对话模式与上下文显示

**日期：** 2026-06-07

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/web/src/components/workspace-shell.tsx` | 新增了本地 Direct/Group 对话模式显示和消息上下文状态，未更改后端路由。 |
| `apps/web/src/components/message-composer.tsx` | 新增了引用消息和选定制品的可见待处理上下文，以及统一的清除上下文行为。 |
| `apps/web/src/components/message-composer.test.tsx` | 新增了对消息和制品上下文显示的覆盖。 |
| `apps/web/src/components/workspace-shell.test.tsx` | 新增了覆盖，确保模式变更和引用上下文暂存不会创建消息或 TaskRun。 |
| `openspec/changes/agenthub-p20-daily-agent-workspace-ux/tasks.md` | 将 P20-2 实现任务标记为完成，待验证。 |

### 验证

| 命令 | 结果 |
|---|---|
| `pnpm --filter @agenthub/web test -- workspace-shell.test.tsx message-composer.test.tsx --runInBand` | 通过，67 项测试 |

---

## P20-1 会话导航优化

**日期：** 2026-06-07

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/web/src/components/session-sidebar.tsx` | 新增了会话 search/filtering、筛选计数、选定会话的任务摘要及空搜索状态。 |
| `apps/web/src/components/workspace-shell.test.tsx` | 新增了对会话筛选和空搜索的覆盖，同时保持选定会话的焦点。 |
| `openspec/changes/agenthub-p20-daily-agent-workspace-ux/tasks.md` | 将 P20-1 实现任务标记为完成，待验证。 |

### 验证

| 命令 | 结果 |
|---|---|
| `pnpm --filter @agenthub/web test -- workspace-shell.test.tsx --runInBand` | 通过，63 项测试 |

---

## 本地文件夹选择器目标注册

**日期：** 2026-06-07

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/api/app/local_folders.py` | 新增了本地文件夹浏览辅助函数，用于工作区启动、父级导航、子文件夹列表及受保护文件夹筛选。 |
| `apps/api/app/main.py` | 新增了工作区作用域的外部目标文件夹浏览端点。 |
| `apps/api/app/schemas.py` | 新增了本地文件夹列表响应模式。 |
| `apps/api/app/target_registry.py` | 为外部前端和后端目标新增了显式的选定文件夹项目类型映射。 |
| `apps/api/tests/test_external_workspaces.py` | 新增了后端覆盖，用于文件夹列表和选定文件夹作用域注册。 |
| `apps/api/tests/test_guardrails.py` | 新增了覆盖，确保选定文件夹作用域允许普通文件，同时受保护路径仍被阻止。 |
| `apps/web/src/lib/api.ts` | 新增了本地文件夹列表 API 辅助函数和类型。 |
| `apps/web/src/lib/api.test.ts` | 新增了 API 辅助函数覆盖，用于文件夹列表查询行为。 |
| `apps/web/src/components/runtime-settings-page-client.tsx` | 将运行时设置连接到加载本地文件夹，并使用 `allowedPaths: ["*"]` 注册选定文件夹，包括 frontend/backend 目标类型选择。 |
| `allowedPaths: ["*"]` | 新增了文件夹选择器对话框、frontend/backend 目标类型选择，并从外部目标注册流程中移除了手动允许路径输入。 |
| `apps/web/src/components/workspace-target-settings.tsx` | 新增了覆盖，用于选择本地文件夹并注册选定文件夹作用域。 |
| `openspec/changes/agenthub-local-folder-picker-target-registration/*` | 已添加并完成此任务的聚焦 OpenSpec 变更制品。 |

### 验证

| 命令 | 结果 |
|---|---|
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_external_workspaces.py tests/test_guardrails.py::test_target_path_policy_allows_selected_folder_scope_except_protected_paths -q` | 通过，9 个测试 |
| `cd apps/web && pnpm test src/components/runtime-settings-page-client.test.tsx src/lib/api.test.ts` | 通过，31 个测试 |
| `pnpm check` | 通过 |
| `git diff --check` | 通过 |
| `openspec validate agenthub-local-folder-picker-target-registration --strict` | 通过 |

---

## P18c 实时内存合规性冻结

**日期：** 2026-06-07

### 修改的文件

| 文件 | 变更 |
|---|---|
| `docs/p18c-freeze-review.md` | 添加了 P18c 实时库管理应用内存合规性冻结审查，包含提供者、会话、快照、制品、指标、后续跟进和限制证据。 |
| `docs/project-state.md` | 记录了最终的 P18c 实时冒烟状态、指标、证据 ID 和已知限制。 |
| `docs/change-log.md` | 添加了此最终 P18c 冻结状态条目。 |
| `openspec/changes/agenthub-p18c-live-memory-compliance-library-app/tasks.md` | 将 P18c 冻结审查文档任务标记为完成，因为它们已通过验证。 |

### 证据摘要

| 项目 | 值 |
|---|---|
| 会话 | `9dd8ff1d-be15-4114-b47c-4d3664838e53` |
| TaskRun | `09d77fb3-f81a-44e0-9b47-3f403ac58579` |
| `memorySnapshotId` | `3a77e409-daae-428a-b739-6bc187105c70` |
| 实际编码提供者 | `codex` / `local-codex-cli` |
| 差异 / 审查 | `7a6dd596-3d9d-4810-b1fb-c7a66d3ac67f`, `a9ac0c07-547a-4bbd-b2a1-6aa867524304` |
| 通过的 check/test/build | `801bad3c-a9f7-479f-8e09-59e1eaadf9e8`, `c1a86bc8-7eba-48c5-a377-c65a0f488941`, `34d4070e-cd5d-450f-bd79-ca449f6b9511` |
| 预览 / 预发布 | `53d8cd5e-0322-449e-a10d-9456633a23e2`, `20d26ddf-736e-49d6-abe0-25e7b0b843db` |
| 合规性摘要 | 通过，在外部目标路径规范化后无最终违规。 |
| 任务成功增量 | 未知 / 不确定，因为没有可比较的实时无内存控制。 |

### 限制

- 配置的 DeepSeek 规划器未运行，因为 `DEEPSEEK_API_KEY` 对 API 进程环境不可见。
- 审查证据使用了确定性脚本化审查；未用于声称实时编码提供者成功。
- Preview/staging URL 在冒烟过程中已验证，在一次性冒烟进程退出后可能无法保持存活。

---

## P18c 外部预览和预发布证据

**日期：** 2026-06-07

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/api/app/previews.py` | 使预览根目录解析具有目标感知能力，以便外部 Vite 目标从注册的外部项目根目录（而非演示工作区根目录）启动预览。 |
| `apps/api/tests/test_previews.py` | 添加了回归覆盖，确保外部 Vite 目标预览从外部目标根目录启动。 |
| `openspec/changes/agenthub-p18c-live-memory-compliance-library-app/tasks.md` | 在收集实时证据后将 P18c-3.5 标记为完成。 |

### 证据

| 项目 | 值 |
|---|---|
| TaskRun | `09d77fb3-f81a-44e0-9b47-3f403ac58579` |
| 适配器 / 提供者 | `codex` / `local-codex-cli` |
| 差异制品 | `7a6dd596-3d9d-4810-b1fb-c7a66d3ac67f` |
| 审查制品 | `a9ac0c07-547a-4bbd-b2a1-6aa867524304` |
| 检查 / 测试 / 构建证据 | `801bad3c-a9f7-479f-8e09-59e1eaadf9e8`, `c1a86bc8-7eba-48c5-a377-c65a0f488941`, `34d4070e-cd5d-450f-bd79-ca449f6b9511` |
| 预览证据 | `53d8cd5e-0322-449e-a10d-9456633a23e2`，在冒烟期间于 `http://127.0.0.1:60413` 处健康 |
| 预发布证据 | `20d26ddf-736e-49d6-abe0-25e7b0b843db`，在冒烟期间于 `http://127.0.0.1:60425` 处就绪 |

### 验证

| 命令 | 结果 |
|---|---|
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_previews.py -q` | 通过，7 个测试 |
| P18c preview/staging 冒烟 | 通过：在冒烟过程中预览 healthy/reachable 和本地预发布 ready/reachable。 |

---

## P18c 实时内存后续跟进证据

**日期：** 2026-06-07

### 后续跟进记录

| 步骤 | 证据 |
|---|---|
| 初始验证失败 | `pnpm check`、`pnpm test` 和 `pnpm build` 失败，因为新的外部 Vite 项目没有 `node_modules`；制品 `4b881975-1155-4ef1-94c8-86b1b3438289`、`15bebd6f-a0a7-489a-b889-bc44626f6b22` 和 `91fda1a8-bb9d-4d05-9aac-71b21452fb77`。 |
| 用户批准的依赖安装 | 在用户明确允许为外部 P18c 项目安装后，`pnpm install` 仅在 `/Users/luotianhang/Desktop/agenthub-rehearsals/p18c-library-app` 中运行。 |
| 后续验证成功 | `pnpm check`、`pnpm test` 和 `pnpm build` 通过；制品 `801bad3c-a9f7-479f-8e09-59e1eaadf9e8`、`c1a86bc8-7eba-48c5-a377-c65a0f488941` 和 `34d4070e-cd5d-450f-bd79-ca449f6b9511`。 |
| Preview/staging 后续跟进 | 外部目标预览最初需要 AgentHub 路径解析支持；提交 `15e4702` 使预览具有目标感知能力，之后预览 `53d8cd5e-0322-449e-a10d-9456633a23e2` 和预发布 `20d26ddf-736e-49d6-abe0-25e7b0b843db` 在冒烟期间成功。 |
没有使用 ScriptedMock 结果来声称符合实时代码规范。编码 TaskRun 的成功证据仍然是真实的 Codex 运行结果 `09d77fb3-f81a-44e0-9b47-3f403ac58579`。

---

## LLM 路由器外部前端兜底

**日期：** 2026-06-07

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/api/app/planning.py` | 当 LLM 对话路由器错误地返回 `assistant_reply` 而非任务计划时，为安全的外部前端编码请求添加了兜底路径。 |
| `apps/api/tests/test_planning.py` | 添加了回归测试覆盖，确保兜底机制会创建一个带有显式规划器兜底证据的自动启动前端任务，而现有的非任务聊天结果仍保持不执行状态。 |

### 验证

| 命令 | 结果 |
|---|---|
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_planning.py::test_llm_assistant_reply_creates_orchestrator_message_without_task tests/test_planning.py::test_api_planner_assistant_reply_creates_orchestrator_message_without_task tests/test_planning.py::test_non_task_conversation_outcomes_do_not_create_tasks tests/test_planning.py::test_conversation_task_plan_creates_validated_task tests/test_planning.py::test_orchestrator_can_create_auto_start_external_frontend_task tests/test_planning.py::test_llm_assistant_reply_for_safe_external_frontend_request_falls_back_to_task -q` | 通过，8 个测试 |

---

## P18c 内存规则简化

**日期：** 2026-06-07

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/api/app/live_memory_compliance.py` | 将狭窄的、仅限英文演示范围的 P18c 内存规则替换为更广泛的中文长期内存规则，并在种子化过程中归档了已废弃的活跃 P18c 规则。 |
| `apps/api/tests/test_live_memory_compliance.py` | 添加了测试覆盖，确保活跃的 P18c 规则使用新的中文措辞，并且在准备新会话之前，已废弃的活跃规则已被归档。 |
| `openspec/changes/agenthub-p18c-live-memory-compliance-library-app/*` | 更新了 P18c 提案、设计和规范语言，使实时代理冒烟测试评估通用的 project/default 行为，而非仅限演示特定的措辞。 |

### 验证

| 命令 | 结果 |
|---|---|
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_live_memory_compliance.py -q` | 通过，13 个测试 |
| `pnpm check` | 通过 |
| `git diff --check` | 通过 |
| `openspec validate agenthub-p18c-live-memory-compliance-library-app --strict` | 通过 |

---

## P18c-3 实时代理提供者阻塞

**日期：** 2026-06-07

### 证据

| 项目 | 值 |
|---|---|
| 会话 | `b11777d4-3dea-47e0-8a71-da8e5749c38a` |
| 消息 | `f9ded109-47ac-4ff8-9569-c450c189b67e` |
| 任务 | `0d85e40e-9626-496b-bdff-234415e47ac1` |
| TaskRun | `1f44056b-b1d9-420b-9bb3-98b984760d18` |
| `memorySnapshotId` | `a27dec94-85c9-4d4d-b5be-6564b8320125` |
| 适配器 / 提供者 | `claude_code` / `local-claude-code-cli` |
| 最终状态 | `failed` |
| 错误 | `CLAUDE_CODE_EXIT_ERROR`: `API Error: Unable to connect to API (ConnectionRefused)` |
| 制品 | 无 |

简化的内存规则使 P18c-3 能够从仅规划器失败进展到真实的前端任务和真实的 ClaudeCodeAdapter TaskRun。执行在 Claude Code 运行时连接错误处停止。未使用 ScriptedMock 来声称符合实时代码规范。

---

## P18c-2 会话和外部目标设置

**日期：** 2026-06-07

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/api/app/live_memory_compliance.py` | 添加了 P18c 设置证据模型和辅助函数，用于准备桌面排练根目录、register/reuse 外部前端目标、创建新会话，并捕获内存 snapshot/hash 证据。 |
| `apps/api/tests/test_live_memory_compliance.py` | 添加了 P18c 设置 target/session/snapshot 创建和目标复用的测试覆盖。 |
| `openspec/changes/agenthub-p18c-live-memory-compliance-library-app/tasks.md` | 标记 P18c-2 为完成。 |

### 验证

| 命令 | 结果 |
|---|---|
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_live_memory_compliance.py -q` | 通过 |
| P18c 设置冒烟测试 | 通过：准备了 `/Users/luotianhang/Desktop/agenthub-rehearsals/p18c-library-app`、目标 `external-p18c-library-app`、新会话、`memorySnapshotId`、6 个活跃内存规则 ID、AGENTS/CLAUDE 哈希值和上下文包哈希值。 |
| `pnpm check` | 通过 |
| `git diff --check` | 通过 |
| `openspec validate agenthub-p18c-live-memory-compliance-library-app --strict` | 通过 |

---

## P18c-1 内存合规性测试框架

**日期：** 2026-06-07

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/api/app/live_memory_compliance.py` | 添加了 P18c 库管理应用提示常量、活跃内存规则定义、内存规则种子化辅助函数、提供者证据模型、合规性证据模型、合规性报告输出和违规检查器。 |
| `apps/api/tests/test_live_memory_compliance.py` | 添加了确定性测试覆盖，涵盖合规证据、缺失的变更日志更新、平台路径修改、意外的 backend/database 创建、错误项目位置、缺失的前端栈、缺失的提供者证据、快照不匹配、提示边界和活跃规范内存规则创建。 |
| `openspec/changes/agenthub-p18c-live-memory-compliance-library-app/tasks.md` | 标记 P18c-1 完成。 |

### 验证

| 命令 | 结果 |
|---|---|
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_live_memory_compliance.py -q` | 通过 |
| `pnpm check` | 通过 |
| `pnpm test` | 通过 |
| `pnpm demo:api:test` | 通过 |
| `git diff --check` | 通过 |
| `openspec validate agenthub-p18c-live-memory-compliance-library-app --strict` | 通过 |

---

## P18b 记忆有效性演练

**日期：** 2026-06-05

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/api/app/memory_rehearsal.py` | 添加了 P18b 场景固件、control/treatment 评估器、结构化演练报告、提供者可用性证据以及聚合指标报告。 |
| `apps/api/tests/test_memory_rehearsal.py` | 增加了对场景稳定性、私有数据拒绝、control/treatment 比较、stale/untrusted 排除、确定性报告序列化、提供者不可用证据以及限制原因的覆盖。 |
| `docs/p18b-freeze-review.md` | 添加了 P18b 场景证据、指标、提供者可用性、验证和限制。 |
| `openspec/changes/agenthub-p18b-memory-effectiveness-rehearsal/*` | 添加并完成了 P18b OpenSpec 提案、设计、规范和任务清单。 |

### 验证

| 命令 | 结果 |
|---|---|
| `pnpm check` | 通过 |
| `pnpm test` | 通过 |
| `pnpm demo:api:test` | 通过 |
| `git diff --check` | 通过 |
| `openspec validate agenthub-p18b-memory-effectiveness-rehearsal --strict` | 通过 |

---

## P18 记忆与指令控制平面

**日期：** 2026-06-04

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/api/app/memory_instructions.py` | 为 AGENTS/CLAUDE 输出制品添加了确定性托管指令桥接。 |
| `apps/api/app/memory_snapshots.py` | 添加了会话记忆快照创建、刷新和元数据。 |
| `apps/api/app/memory_store.py` | 添加了规范记忆项模型服务、生命周期状态、版本和过滤器。 |
| `apps/api/app/memory_write_policy.py` | 添加了显式用户写入策略和提示注入防护。 |
| `apps/api/app/memory_retrieval.py` | 添加了带评分和元数据过滤器的 keyword/BM25-style 检索。 |
| `apps/api/app/external_memory_scan.py` | 添加了将外部 AGENTS/CLAUDE 扫描结果导入待处理建议并附带冲突检测的功能。 |
| `apps/api/app/memory_evals.py` | 添加了确定性记忆有效性指标辅助函数。 |
| `apps/web/src/app/settings/memory/page.tsx` / `apps/web/src/components/memory-settings-page-client.tsx` | 添加了记忆管理设置 UI。 |
| `docs/p18-freeze-review.md` | 添加了冻结审查、指标证据、验证和注意事项。 |
| `openspec/changes/agenthub-p18-memory-instruction-control-plane/tasks.md` | 标记 P18 实现、评估、非目标和冻结任务为完成。 |

### 验证

| 命令 | 结果 |
|---|---|
| `pnpm check` | 通过 |
| `pnpm test` | 通过 |
| `git diff --check` | 通过 |
| `openspec validate agenthub-p18-memory-instruction-control-plane --strict` | 通过 |

---

## 微妙的侧边栏渐变调优

**日期：** 2026-06-02

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/web/src/app/globals.css` | 降低了调色板饱和度，柔化了共享的 muted/background 颜色，以获得更均匀的参考风格灰色和淡青色色调。 |
| `apps/web/src/components/session-sidebar.tsx` | 将侧边栏调整为受参考 UI 启发的简单、统一的淡青色到白色渐变。 |
| `apps/web/src/components/contact-settings-page-client.tsx` | 使联系人设置面板与相同的微妙渐变系列相匹配。 |
| `docs/change-log.md` | 记录了渐变调优更新。 |

### 验证

| 命令 | 结果 |
|---|---|
| `pnpm --filter @agenthub/web check` | 通过。 |
| `pnpm --filter @agenthub/web test -- workspace-shell` | 通过：10 个文件 / 55 个测试。 |
| `git diff --check -- apps/web/src/app/globals.css apps/web/src/components/session-sidebar.tsx apps/web/src/components/contact-settings-page-client.tsx docs/change-log.md` | 通过。 |

---

## 项目状态治理刷新

**日期：** 2026-06-02

### 修改的文件

| 文件 | 变更 |
|---|---|
| `docs/project-state.md` | 记录了工作树中存在但不在原始 P17c OpenSpec 范围内的 P17c 后 UI/settings 更新。 |
| `README.md` | 澄清 AgentHub 仍然是一个本地单用户 Agent 编码工作区/多 Agent 编码平台原型，而非完整的多用户 IM 平台。 |
| `docs/change-log.md` | 记录了本次治理刷新。 |

### 验证

| 命令 | 结果 |
|---|---|
| `git diff --check` | 通过。 |
| `openspec validate agenthub-p17c-runtime-settings-page --strict` | 通过。 |
| `pnpm --filter @agenthub/web check` | 通过。 |
| `pnpm --filter @agenthub/web test -- runtime-settings-page-client workspace-shell` | 通过：10 个文件 / 55 个测试。 |

---

## 侧边栏设置页面导航

**日期：** 2026-06-02

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/web/src/components/session-sidebar.tsx` | 将“更改联系人设置”、“运行时设置”和其他设置改为引用式侧边栏链接，每个链接导航至各自的设置页面，同时将“新建会话”和可滚动的最近会话保留在侧边栏中。 |
| `apps/web/src/app/settings/contacts/page.tsx` | 新增了专用的“联系人设置”页面，该页面加载演示工作区和内置的 Agent 联系人。 |
| `apps/web/src/components/contact-settings-page-client.tsx` | 添加了客户端联系人设置视图，包含紧凑的 Agent 联系人列表和 Direct/Group 视觉模式切换开关。 |
| `apps/web/src/app/settings/other/page.tsx` | 为“其他设置”添加了专用的占位页面。 |
| `apps/web/src/components/agent-contact-list.tsx` | 收紧了内置 Agent 联系人视图，使其作为紧凑的设置页面列表运行。 |
| `apps/web/src/components/workspace-shell.test.tsx` | 更新了设置页面导航的侧边栏断言，同时将详细的设置内容保留在聊天工作区之外。 |
| `docs/change-log.md` | 记录了侧边栏设置页面导航的更新。 |

### 验证

| 命令 | 结果 |
|---|---|
| `pnpm --filter @agenthub/web check` | 通过。 |
| `pnpm --filter @agenthub/web test -- workspace-shell` | 通过：10 个文件 / 55 个测试。 |
| 浏览器冒烟测试 | 通过：侧边栏链接路由至 `/settings/contacts`、`/settings/runtime` 和 `/settings/other`；联系人页面显示 6 个内置联系人，运行时设置正常加载，其他设置显示占位页面。 |

---

## 运行时工作区目标设置

**日期：** 2026-06-02

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/web/src/lib/api.ts` | 为工作区目标、外部项目 analysis/registration 和会话目标选择添加了客户端 API 和类型。 |
| `apps/web/src/components/workspace-target-settings.tsx` | 在运行时设置中添加了一个紧凑的工作区设置面板，用于外部项目注册和按会话 frontend/backend 的目标选择。 |
| `apps/web/src/components/runtime-settings-page-client.tsx` | 将工作区 sessions/targets 与运行时配置一同加载，并连接了目标保存、外部项目分析和外部项目注册操作。 |
| `apps/web/src/components/runtime-settings-page-client.test.tsx` | 覆盖了工作区目标加载、会话目标保存和外部项目 analyze/register 流程。 |
| `apps/web/src/lib/api.test.ts` | 覆盖了新的工作区目标和外部项目客户端 API。 |
| `docs/change-log.md` | 记录了运行时工作区目标设置的更新。 |

### 验证

| 命令 | 结果 |
|---|---|
| `pnpm --filter @agenthub/web check` | 通过。 |
| `pnpm --filter @agenthub/web test -- runtime-settings-page-client api` | 通过：10 个文件 / 55 个测试。 |

---

## 工作区布局刷新

**日期：** 2026-06-02

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/web/src/app/globals.css` | 将工作区调色板转向参考设计的灰色桌面背景、白色表面、黑色主要操作和浅青色导航强调色。 |
| `apps/web/src/components/workspace-shell.tsx` | 将聊天工作区重构为圆角三面板应用外壳，将顶部标题内容移至中央会话面板，并将演示流水线重新样式化为紧凑的药丸形状。 |
| `apps/web/src/components/session-sidebar.tsx` | 将侧边栏重新样式化为柔和的导航轨道，包含紧凑的工作区元数据、更突出的新建会话操作和更清晰的会话行。 |
| `apps/web/src/components/agent-contact-list.tsx` | 将 Agent 联系人列表简化为更轻量的 IM 风格行，带有有界元数据药丸和紧凑模式控件。 |
| `apps/web/src/components/chat-thread.tsx` | 调整了聊天和编排器计划卡片，以匹配新的中性工作台表面和 8px 卡片节奏。 |
| `apps/web/src/components/mission-panel.tsx` | 将会话上下文条与更宽的中央工作区域对齐。 |
| `apps/web/src/components/message-composer.tsx` | 将编辑器与后续上下文条与刷新后的中央面板宽度和圆角对齐。 |
| `apps/web/src/components/preview-card.tsx` | 将右侧 artifact/preview 面板重新样式化为中性表面、黑色活动标签和更简单的空状态。 |
| `apps/web/src/components/task-card-list.tsx` | 使任务时间线卡片、标签和运行部分与刷新后的中性布局相匹配。 |
| `docs/change-log.md` | 记录了工作区布局刷新。 |

### 验证

| 命令 | 结果 |
|---|---|
| `pnpm --filter @agenthub/web check` | 通过。 |
| `pnpm --filter @agenthub/web test -- workspace-shell page` | 通过：10 个文件 / 51 个测试。 |
| `git diff --check -- apps/web/src/app/globals.css apps/web/src/components/workspace-shell.tsx apps/web/src/components/session-sidebar.tsx apps/web/src/components/agent-contact-list.tsx apps/web/src/components/chat-thread.tsx apps/web/src/components/mission-panel.tsx apps/web/src/components/message-composer.tsx apps/web/src/components/preview-card.tsx apps/web/src/components/task-card-list.tsx docs/change-log.md` | 通过。 |
| 浏览器冒烟测试 | 通过：`http://127.0.0.1:3000` 渲染了刷新后的三面板工作区，没有出现首次冒烟测试中看到的标题文本折叠或水平滚动条。 |

---

## 非任务对话结果规范化

**日期：** 2026-06-02

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/api/app/llm_planner.py` | 在模式验证前，通过丢弃意外的 `planDraft`/`codingAgentProvider` 噪声，规范化了非任务对话结果负载，同时保持 `task_plan` 严格。 |
| `apps/api/tests/test_planner_contracts.py` | 增加了对包含意外非任务计划元数据的助手回复的覆盖。 |
| `docs/change-log.md` | 记录了非任务对话结果规范化修复。 |

### 验证

| 命令 | 结果 |
|---|---|
| `bash scripts/check-api.sh` | 通过。 |
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_planner_contracts.py::test_parse_conversation_outcome_output_ignores_non_task_plan_draft_noise tests/test_planner_contracts.py::test_parse_conversation_outcome_output_accepts_task_plan_wrapper tests/test_planner_contracts.py::test_parse_llm_plan_output_rejects_missing_required_fields -q` | 通过：3 个测试。 |
| `bash scripts/test-api.sh` | 通过：385 个测试。 |
| `pnpm --filter @agenthub/web check` | 通过。 |

---

## 宽松规划器助手回复规范化

**日期：** 2026-06-02

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/api/app/llm_planner.py` | 将安全的宽松助手 JSON（例如 `{ "reply": "..." }`）规范化为 `assistant_reply` 对话结果，而不是将其视为旧的规划器响应。 |
| `apps/api/tests/test_planner_contracts.py` | 增加了对宽松助手回复的解析器覆盖，同时保持任务计划输出严格。 |
| `docs/change-log.md` | 记录了规划器助手回复规范化修复。 |

### 验证

| 命令 | 结果 |
|---|---|
| `bash scripts/check-api.sh` | 通过。 |
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_planner_contracts.py::test_parse_conversation_outcome_output_normalizes_loose_assistant_reply tests/test_planner_contracts.py::test_parse_llm_plan_output_rejects_missing_required_fields tests/test_llm_planner.py::test_api_planner_invalid_output_creates_no_task -q` | 通过：4 个测试。 |
| `bash scripts/test-api.sh` | 通过：384 个测试。 |
| `pnpm --filter @agenthub/web check` | 通过。 |

---

## 规划器兜底透明化

**日期：** 2026-06-02

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/api/app/planning.py` | 修改了聊天兜底回复，使其在 LLM 提供商调用失败时包含规划器失败详情，并本地化了 unsupported/unregistered-target 兜底文案。 |
| `apps/api/tests/test_planning.py` | 增加了覆盖，确保失败的规划器调用会暴露错误摘要，而不是通用的固定回复。 |
| `apps/api/tests/test_chat_events.py` | 更新了本地化兜底回复的消息持久化覆盖。 |
| `apps/web/src/components/workspace-shell.test.tsx` | 更新了本地化兜底回复的 UI 消息刷新覆盖。 |
| `docs/change-log.md` | 记录了规划器兜底透明化改进。 |

### 验证

| 命令 | 结果 |
|---|---|
| `bash scripts/check-api.sh` | 通过。 |
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_planning.py::test_failed_llm_router_exposes_error_summary_in_chat_fallback tests/test_planning.py::test_disabled_llm_router_returns_friendly_chat_fallback_without_task tests/test_planning.py::test_unsupported_broad_saas_request_is_handled_honestly tests/test_chat_events.py -q` | 通过：5 个测试。 |
| `bash scripts/test-api.sh` | 通过：383 个测试。 |
| `pnpm --filter @agenthub/web test -- workspace-shell` | 通过：10 个文件，51 个测试。 |

---

## 运行时规划器 API 路由修复

**日期：** 2026-06-02

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/api/app/planner_providers.py` | 使运行时 `providerPresetId`、`model`、`baseUrl`、`apiKeyEnv` 和 `timeoutSeconds` 在解析规划器 API 提供商时覆盖全局禁用的规划器默认值。 |
| `apps/api/app/planning.py` | 将完整的规划器运行时配置传递到 LLM 对话路由器中。 |
| `apps/api/app/agent_runtime_config.py` | 在运行时配置解析证据中包含了规划器 API preset/model/base URL/env 元数据，而不暴露原始密钥。 |
| `apps/api/tests/test_planner_providers.py` | 覆盖了在全局规划器默认值保持禁用时解析运行时 DeepSeek 风格 API 预设的情况。 |
| `apps/api/tests/test_planning.py` | 覆盖了无提及路由将规划器运行时 preset/model/baseUrl/apiKeyEnv 传递到解析器的情况。 |
| `docs/change-log.md` | 记录了运行时规划器 API 路由修复。 |

### 验证

| 命令 | 结果 |
|---|---|
| `bash scripts/check-api.sh` | 通过。 |
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_planner_providers.py::test_resolve_planner_provider_supports_runtime_api_preset_over_disabled_default tests/test_planning.py::test_runtime_config_selects_planner_provider_for_no_mention_message tests/test_planning.py::test_disabled_llm_router_returns_friendly_chat_fallback_without_task -q` | 通过：3 个测试。 |
| `bash scripts/test-api.sh` | 通过：382 个测试。 |
| `pnpm --filter @agenthub/web check` | 通过。 |

---

## 运行时配置文件提供程序警告清理

**日期：** 2026-06-02

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/api/app/agent_runtime_config.py` | 当角色配置文件的旧适配器元数据与所选运行时提供程序适配器不同时，停止发出警告；运行时提供程序仍然是执行的事实来源。 |
| `apps/api/tests/test_agent_runtime_config.py` | 增加了覆盖范围，确保前端代理配置文件与 Claude Code 提供程序组合时，不会出现适配器不匹配的警告。 |
| `docs/change-log.md` | 记录了运行时 profile/provider 警告清理。 |

### 验证

| 命令 | 结果 |
|---|---|
| `bash scripts/check-api.sh` | 通过。 |
| `bash scripts/test-api.sh` | 通过：381 个测试。 |
| `git diff --check` | 通过。 |

---

## 运行时设置保存 CORS 修复

**日期：** 2026-06-02

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/api/app/main.py` | 将 `PUT` 和 `OPTIONS` 添加到 API CORS 允许列表中，以便浏览器保存到 `/runtime-config` 时能通过预检请求。 |
| `apps/api/tests/test_agent_runtime_config.py` | 为运行时配置保存端点添加了一个 CORS 预检回归测试。 |
| `docs/change-log.md` | 记录了运行时设置保存修复。 |

### 验证

| 命令 | 结果 |
|---|---|
| `bash scripts/check-api.sh` | 通过。 |
| `bash scripts/test-api.sh` | 通过：381 个测试。 |
| `git diff --check` | 通过。 |

---

## 运行时提供程序可用性检查

**日期：** 2026-06-02

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/api/app/provider_health.py` | 为 Planner API 预设、本地 Claude/Codex CLI 提供程序和 ScriptedMock 添加了一个只读的提供程序健康检查辅助函数。 |
| `apps/api/app/schemas.py` | 添加了运行时提供程序检查 request/response 模式。 |
| `apps/api/app/main.py` | 添加了 `POST /workspaces/{workspace_id}/runtime-config/check-provider`。 |
| `apps/api/tests/test_agent_runtime_config.py` | 覆盖了缺少 Planner API 密钥、无需认证的 ScriptedMock 以及本地 CLI 版本探测的情况。 |
| `apps/web/src/lib/api.ts` | 添加了运行时提供程序检查客户端 API。 |
| `apps/web/src/lib/api.test.ts` | 覆盖了提供程序检查客户端 request/response. |
| `apps/web/src/components/runtime-settings-page-client.tsx` | 将提供程序检查结果接入运行时设置 draft/config 状态。 |
| `apps/web/src/components/agent-runtime-settings.tsx` | 添加了每个角色的 `检测` 按钮和可见的可用性状态标签。 |
| `检测` | 覆盖了从设置页面检查提供程序的功能。 |
| `apps/web/src/components/runtime-settings-page-client.test.tsx` | 记录了提供程序可用性检查功能。 |

### 验证

| 命令 | 结果 |
|---|---|
| `bash scripts/check-api.sh` | 通过。 |
| `bash scripts/test-api.sh` | 通过：379 个测试。 |
| `pnpm --filter @agenthub/web check` | 通过。 |
| `pnpm --filter @agenthub/web test -- runtime-settings-page-client api` | 通过：10 个文件，51 个测试。 |
| `pnpm check` | 通过。 |
| `pnpm test` | 通过：Web 10 个文件 / 51 个测试；API 379 个测试；演示 API 5 个测试。 |
| `git diff --check` | 通过。 |
| 浏览器演练 | 通过：运行时设置页面显示四个每个角色的 `检测` 按钮，并带有简体中文设置文案。 |

---

## 运行时设置中文文案

**日期：** 2026-06-02

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/web/src/app/settings/runtime/page.tsx` | 将运行时设置页面的标题和导航文案改为中文。 |
| `apps/web/src/components/agent-runtime-settings.tsx` | 将主要角色标签、表单标签、状态标签、验证文案和 Planner API 控件本地化为中文，同时保留提供程序专有名词。 |
| `apps/web/src/components/runtime-settings-page-client.tsx` | 保持加载、保存、取消和错误状态消息为中文。 |
| `apps/web/src/components/runtime-settings-page-client.test.tsx` | 更新了运行时设置测试，以断言中文标签。 |
| `apps/web/src/components/workspace-shell.test.tsx` | 更新了聊天侧边栏设置断言，以使用中文设置标签。 |
| `docs/change-log.md` | 记录了中文文案更新。 |

### 验证

| 命令 | 结果 |
|---|---|
| `pnpm --filter @agenthub/web check` | 通过。 |
| `pnpm --filter @agenthub/web test -- runtime-settings-page-client workspace-shell` | 通过：10 个文件，49 个测试。 |
| `git diff --check` | 通过。 |
| 浏览器演练 | 通过：运行时设置页面显示中文的主标题、控件、状态标签和操作；旧的英文设置标签已不存在。 |

---

## 运行时设置页面简化

**日期：** 2026-06-02

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/web/src/app/settings/runtime/page.tsx` | 移除了额外的说明卡片，使设置页面专注于主表单。 |
| `apps/web/src/components/agent-runtime-settings.tsx` | 从运行时设置表单中移除了角色描述、capability/target 装饰和冗长的 API 密钥辅助文案。 |
| `apps/web/src/components/runtime-settings-page-client.test.tsx` | 更新了简化状态展示的覆盖范围。 |
| `docs/change-log.md` | 记录了此 UI 简化。 |

### 验证
| 命令 | 结果 |
|---|---|
| `pnpm --filter @agenthub/web check` | 通过。 |
| `pnpm --filter @agenthub/web test -- runtime-settings-page-client workspace-shell` | 通过：10 个文件，49 个测试。 |
| `git diff --check` | 通过。 |
| 浏览器预演 | 通过：主要角色和 Save/Cancel 保持可见；说明性文字已移除；设置页面仍可滚动。 |

---

## 运行时设置页面滚动修复

**日期：** 2026-06-02

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/web/src/app/settings/runtime/page.tsx` | 将设置页面滚动容器改为固定视口高度，使其能在应用级隐藏 body 溢出的布局下滚动。 |
| `docs/change-log.md` | 记录此 UI 修复。 |

### 验证

| 命令 | 结果 |
|---|---|
| `pnpm --filter @agenthub/web check` | 通过。 |
| `pnpm --filter @agenthub/web test -- runtime-settings-page-client workspace-shell` | 通过：10 个文件，49 个测试。 |
| `git diff --check` | 通过。 |
| 浏览器预演 | 通过：设置页面 `<main>` 可滚动；测量到 `scrollHeight` 大于 `clientHeight` 且滚动位置发生变化。 |

---

## 运行时设置导航响应性

**日期：** 2026-06-01

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/web/src/app/settings/runtime/page.tsx` | 使运行时设置路由立即渲染页面外壳，而不是在导航前等待后端工作区获取。 |
| `apps/web/src/components/runtime-settings-page-client.tsx` | 将演示 workspace/runtime 配置加载移至客户端设置组件，并附带显式加载消息。 |
| `docs/change-log.md` | 记录此 UI 响应性修复。 |

### 验证

| 命令 | 结果 |
|---|---|
| `pnpm --filter @agenthub/web check` | 通过。 |
| `pnpm --filter @agenthub/web test -- runtime-settings-page-client workspace-shell` | 通过：10 个文件，48 个测试。 |
| `git diff --check` | 通过。 |
| 浏览器预演 | 通过：点击聊天页面设置入口后，设置页面外壳很快可见；表单随后加载。 |

---

## P17c 运行时设置页面

**日期：** 2026-06-01

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/web/src/components/session-sidebar.tsx` | 移除内联运行时设置面板，添加紧凑型设置入口。 |
| `apps/web/src/app/settings/runtime/page.tsx` | 添加专用运行时设置路由。 |
| `apps/web/src/components/runtime-settings-page-client.tsx` | 在设置页面上加载运行时配置，并实现草稿、保存和取消行为。 |
| `apps/web/src/components/agent-runtime-settings.tsx` | 组织 Planner/Frontend/Backend/Review 设置并翻译提供商状态标签。 |
| `apps/web/src/components/workspace-shell.test.tsx` / `apps/web/src/components/runtime-settings-page-client.test.tsx` | 添加对聊天简化、save/cancel、草稿隔离和面向用户状态标签的覆盖。 |
| `docs/project-state.md` | 记录 P17c 运行时设置页面基线。 |
| `openspec/changes/agenthub-p17c-runtime-settings-page/tasks.md` | 标记所有 P17c 实现、验证、预演和完成任务为已完成。 |

### 验证

| 命令 | 结果 |
|---|---|
| `pnpm --filter @agenthub/web test -- workspace-shell` | 通过：9 个文件，44 个测试。 |
| `pnpm --filter @agenthub/web test -- runtime-settings-page-client` | 通过：10 个文件，48 个测试。 |
| `pnpm --filter @agenthub/web check` | 通过。 |
| `git diff --check` | 通过。 |
| `openspec validate agenthub-p17c-runtime-settings-page --strict` | 通过。 |

---

## P17b-2.2 规划器预设协议映射

**日期：** 2026-06-01

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/api/app/planner_providers.py` | 将规划器提供商预设映射到协议标识符。 |
| `apps/api/tests/test_planner_providers.py` | 添加对预设到协议映射的覆盖。 |
| `openspec/changes/agenthub-p17b-multi-provider-planner-api/tasks.md` | 标记 P17b-2.2 完成。 |
| `docs/change-log.md` | 记录此实现。 |

### 验证

| 命令 | 结果 |
|---|---|
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_planner_providers.py::test_planner_provider_presets_map_to_protocols -q` | 通过：1 个测试。 |
| `git diff --check` | 通过。 |
| `openspec validate agenthub-p17b-multi-provider-planner-api --strict` | 通过。 |

---

## P17b-2.1 规划器提供商预设

**日期：** 2026-06-01

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/api/app/planner_providers.py` | 为 OpenAI、DeepSeek、MiMo、Anthropic 和自定义 OpenAI 兼容 API 添加内置规划器提供商预设元数据。 |
| `apps/api/tests/test_planner_providers.py` | 添加预设注册表覆盖。 |
| `openspec/changes/agenthub-p17b-multi-provider-planner-api/tasks.md` | 标记 P17b-2.1 完成。 |
| `docs/change-log.md` | 记录此实现。 |

### 验证

| 命令 | 结果 |
|---|---|
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_planner_providers.py::test_planner_provider_preset_registry_lists_builtin_presets -q` | 通过：1 个测试。 |
| `git diff --check` | 通过。 |
| `openspec validate agenthub-p17b-multi-provider-planner-api --strict` | 通过。 |

---

## P17b-1.4 规划器协议注册表测试

**日期：** 2026-06-01
### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/api/tests/test_planner_providers.py` | 为规划器提供者协议添加了完整的注册表无密钥元数据覆盖。 |
| `openspec/changes/agenthub-p17b-multi-provider-planner-api/tasks.md` | 标记 P17b-1.4 完成。 |
| `docs/change-log.md` | 记录此实现。 |

### 验证

| 命令 | 结果 |
|---|---|
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_planner_providers.py -q` | 通过：17 个测试。 |
| `git diff --check` | 通过。 |
| `openspec validate agenthub-p17b-multi-provider-planner-api --strict` | 通过。 |

---

## P17b-1.3 保留现有规划器提供者

**日期：** 2026-06-01

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/api/tests/test_planner_providers.py` | 添加了回归覆盖，证明 `claude_cli`、`fake_test` 和 `disabled` 提供者解析仍然兼容。 |
| `openspec/changes/agenthub-p17b-multi-provider-planner-api/tasks.md` | 标记 P17b-1.3 完成。 |
| `docs/change-log.md` | 记录此实现。 |

### 验证

| 命令 | 结果 |
|---|---|
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_planner_providers.py::test_existing_planner_provider_resolution_stays_compatible -q` | 通过：1 个测试。 |
| `git diff --check` | 通过。 |
| `openspec validate agenthub-p17b-multi-provider-planner-api --strict` | 通过。 |

---

## P17b-1.2 规划器提供者能力标志

**日期：** 2026-06-01

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/api/app/planner_providers.py` | 向 PlannerProvider 协议元数据添加了能力标志。 |
| `apps/api/tests/test_planner_providers.py` | 添加了能力元数据和无密钥字段的覆盖。 |
| `openspec/changes/agenthub-p17b-multi-provider-planner-api/tasks.md` | 标记 P17b-1.2 完成。 |
| `docs/change-log.md` | 记录此实现。 |

### 验证

| 命令 | 结果 |
|---|---|
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_planner_providers.py::test_planner_provider_protocol_metadata_exposes_capability_flags -q` | 通过：1 个测试。 |
| `git diff --check` | 通过。 |
| `openspec validate agenthub-p17b-multi-provider-planner-api --strict` | 通过。 |

---

## P17b-1.1 规划器提供者协议元数据

**日期：** 2026-06-01

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/api/app/planner_providers.py` | 为 OpenAI Responses、OpenAI 兼容聊天、Anthropic Messages、Claude CLI、假测试和禁用的规划器协议添加了协议级别的 PlannerProvider 元数据。 |
| `apps/api/tests/test_planner_providers.py` | 添加了受支持规划器协议的注册表覆盖。 |
| `openspec/changes/agenthub-p17b-multi-provider-planner-api/*` | 添加了 P17b OpenSpec 制品并标记 P17b-1.1 完成。 |
| `docs/change-log.md` | 记录此实现。 |

### 验证

| 命令 | 结果 |
|---|---|
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_planner_providers.py::test_planner_provider_protocol_registry_lists_supported_protocols -q` | 通过：1 个测试。 |
| `git diff --check` | 通过。 |
| `openspec validate agenthub-p17b-multi-provider-planner-api --strict` | 通过。 |

---

## SQLite 外部目标模式兼容性

**日期：** 2026-05-31

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/api/app/db.py` | 为遗留的 `externalprojecttarget` 表添加了 SQLite 兼容性列，包括暂存部署元数据。 |
| `apps/api/tests/test_models.py` | 添加了一个遗留表回归测试，验证模式兼容性运行后外部目标查询是否正常工作。 |
| `docs/change-log.md` | 记录此错误修复。 |

### 验证

| 命令 | 结果 |
|---|---|
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_models.py::test_sqlite_schema_compatibility_adds_external_target_staging_columns tests/test_planning.py::test_llm_assistant_reply_creates_orchestrator_message_without_task -q` | 通过：2 个测试。 |
| `pnpm db:init` | 通过；更新了本地演示 SQLite 模式。 |
| `pnpm check:api` | 通过。 |
| `pnpm test:api` | 通过：320 个测试。 |
| `git diff --check` | 通过。 |

---

## P17-8 预演与冻结审查

**日期：** 2026-05-29

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/api/tests/test_planning.py` | 更新了运行时配置规划器提供者测试，以使用新的 ConversationOutcome 提供者路径。 |
| `docs/p17-freeze-review.md` | 添加了 P17 冻结证据、运行时边界、验证结果、注意事项和推荐标签。 |
| `docs/project-state.md` | 记录了 P17 冻结就绪状态和对话路由基线。 |
| `docs/change-log.md` | 记录此冻结审查。 |
| `openspec/changes/agenthub-p17-conversational-orchestrator-routing/tasks.md` | 验证后标记 P17-8、非目标和验证完成。 |

### 变更内容

P17 冻结审查确认 AgentHub 现在将无提及和 `@orchestrator` 消息首先视为对话结果：聊天保持为聊天，任务计划在调度前进行验证，且编码代理不会因正常对话而被调用。

### 验证

| 命令 | 结果 |
|---|---|
| P17 目标对话 router/schema/reply/plan/fallback/follow-up 测试 | 通过：44 个测试。 |
| `pnpm check` | 通过。 |
| `pnpm test` | 通过：Web 44 项测试，API 319 项测试，demo-api 5 项测试。 |
| `pnpm demo:api:test` | 通过：5 项测试。 |
| `git diff --check` | 通过。 |
| `openspec validate agenthub-p17-conversational-orchestrator-routing --strict` | 通过。 |

---

## P17-7 友好兜底

**日期：** 2026-05-29

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/api/app/planning.py` | 当 LLM 路由为 disabled/unavailable 时，添加了友好的纯聊天兜底，并用 `plannerSource: fallback` 标记了前端兜底任务。 |
| `apps/api/tests/test_planning.py` | 添加了对禁用路由的聊天兜底的覆盖，并审计了前端兜底元数据。 |
| `openspec/changes/agenthub-p17-conversational-orchestrator-routing/tasks.md` | 在定向验证后标记 P17-7 完成。 |
| `docs/change-log.md` | 记录此实现。 |

### 验证

| 命令 | 结果 |
|---|---|
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_planning.py::test_disabled_llm_router_returns_friendly_chat_fallback_without_task tests/test_planning.py::test_no_mention_message_routes_to_orchestrator_and_auto_starts_demo_task -q` | 通过：2 项测试。 |

---

## P17-6 后续路由上下文

**日期：** 2026-05-29

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/api/app/canonical_context.py` | 将 `missionTrace` 添加到 CanonicalSharedContext 提供者可见字段中。 |
| `apps/api/app/llm_planner.py` | 将任务追踪添加到规划器上下文，并允许后续会话保留当前任务证据。 |
| `apps/api/app/planning.py` | 允许包含现有任务的编排器消息进入 LLM 路由器，而不是将 LLM 路由限制为空会话。 |
| `apps/api/tests/test_llm_planner.py` | 为后续任务追踪上下文的规划器输入添加了覆盖。 |
| `apps/api/tests/test_planning.py` | 添加了覆盖，确保后续消息仍会调用 LLM 路由器。 |
| `openspec/changes/agenthub-p17-conversational-orchestrator-routing/tasks.md` | 在定向验证后标记 P17-6 完成。 |
| `docs/change-log.md` | 记录此实现。 |

### 验证

| 命令 | 结果 |
|---|---|
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_llm_planner.py::test_llm_planner_input_includes_followup_mission_trace -q` | 通过：1 项测试。 |
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_planning.py::test_followup_message_still_routes_through_llm_router -q` | 通过：1 项测试。 |

---

## P17-5 澄清、拒绝与审批结果

**日期：** 2026-05-29

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/api/tests/test_planning.py` | 添加了对澄清、拒绝和需要审批的 ConversationOutcome 回复不创建任务的覆盖。 |
| `openspec/changes/agenthub-p17-conversational-orchestrator-routing/tasks.md` | 在定向验证后标记 P17-5 完成。 |
| `docs/change-log.md` | 记录此实现。 |

### 验证

| 命令 | 结果 |
|---|---|
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_planning.py::test_non_task_conversation_outcomes_do_not_create_tasks -q` | 通过：3 项测试。 |

---

## P17-4 任务规划路径

**日期：** 2026-05-29

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/api/tests/test_planning.py` | 添加了对 `ConversationOutcome(task_plan)` 通过 LLM 路径生成已验证前端任务的覆盖。 |
| `openspec/changes/agenthub-p17-conversational-orchestrator-routing/tasks.md` | 在定向验证后标记 P17-4 完成。 |
| `docs/change-log.md` | 记录此实现。 |

### 验证

| 命令 | 结果 |
|---|---|
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_planning.py::test_conversation_task_plan_creates_validated_task tests/test_planning.py::test_llm_task_plan_bypasses_legacy_signal_gates -q` | 通过：2 项测试。 |

---

## P17-3 对话回复路径

**日期：** 2026-05-29

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/api/app/llm_planner.py` | 将提供者输出处理拆分为 ConversationOutcome 解析和任务规划持久化，以便非任务结果可以在任务创建前停止。 |
| `apps/api/app/planning.py` | 将非任务的 ConversationOutcome 回复持久化为 `orchestrator` 聊天消息，且不包含 TaskRun。 |
| `apps/api/tests/test_planning.py` | 添加了对 `你好` 生成编排器回复且不创建任务的覆盖。 |
| `openspec/changes/agenthub-p17-conversational-orchestrator-routing/tasks.md` | 在定向验证后标记 P17-3 完成。 |
| `docs/change-log.md` | 记录此实现。 |

### 验证

| 命令 | 结果 |
|---|---|
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_planning.py::test_llm_assistant_reply_creates_orchestrator_message_without_task tests/test_planning.py::test_no_mention_message_uses_configured_llm_planner_provider -q` | 通过：2 项测试。 |
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_llm_planner.py -q` | 通过：5 项测试。 |

---

## P17-2b LLM 优先的编排器入口

**日期：** 2026-05-29

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/api/app/llm_planner.py` | 为 LLM 规划器输出添加了 ConversationOutcome 解析，同时保持现有测试和模拟提供商的 PlannerResponse 兼容性。 |
| `apps/api/app/planner_providers.py` | 更新了 Claude CLI 规划器提示，要求返回单个 ConversationOutcome，并将 chat/routing 决策与编码执行分离。 |
| `apps/api/tests/test_planner_contracts.py` | 为任务计划和助手回复添加了 ConversationOutcome 解析器覆盖。 |
| `apps/api/tests/test_planner_providers.py` | 更新了针对 ConversationOutcome 契约的提示断言。 |
| `openspec/changes/agenthub-p17-conversational-orchestrator-routing/tasks.md` | 在定向验证后标记 P17-2b 完成。 |
| `docs/change-log.md` | 记录了本次实现。 |

### 验证

| 命令 | 结果 |
|---|---|
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_planner_contracts.py tests/test_planner_providers.py tests/test_llm_planner.py -q` | 通过：34 个测试。 |
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_planning.py::test_no_mention_message_uses_configured_llm_planner_provider tests/test_planning.py::test_runtime_config_selects_planner_provider_for_no_mention_message tests/test_planning.py::test_llm_task_plan_bypasses_legacy_signal_gates -q` | 通过：3 个测试。 |

---

## P17-2a 从主路由中淘汰旧版信号门

**日期：** 2026-05-29

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/api/tests/test_planning.py` | 添加了覆盖测试，证明 LLM `task_plan` 绕过旧版 safe/unsupported 信号门，直接到达 PlanValidator/task 持久化层。 |
| `openspec/changes/agenthub-p17-conversational-orchestrator-routing/tasks.md` | 在定向验证后标记 P17-2a 完成。 |
| `docs/change-log.md` | 记录了本次实现。 |

### 验证

| 命令 | 结果 |
|---|---|
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_planning.py::test_llm_task_plan_bypasses_legacy_signal_gates -q` | 通过：1 个测试。 |

---

## P17-1 ConversationOutcome 模式

**日期：** 2026-05-29

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/api/app/planner_contracts.py` | 为助手回复、任务计划、澄清、拒绝、需要审批、不支持、规划器提供者证据、验证结果和 fallback/error 元数据添加了 `ConversationOutcome` 契约。 |
| `apps/api/tests/test_planner_contracts.py` | 为助手回复、必需的任务计划草稿以及 planner/coding 提供者证据分离添加了模式测试。 |
| `openspec/changes/agenthub-p17-conversational-orchestrator-routing/tasks.md` | 在定向验证后标记 P17-1 完成。 |
| `docs/change-log.md` | 记录了本次实现。 |

### 验证

| 命令 | 结果 |
|---|---|
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_planner_contracts.py -q` | 通过：14 个测试。 |

---

## 聊天消息同步修复

**日期：** 2026-05-29

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/web/src/components/workspace-shell.tsx` | 在发送消息后刷新会话消息，使后端创建的 Orchestrator 回复立即显示。 |
| `apps/web/src/components/workspace-shell.test.tsx` | 添加了覆盖测试，验证后端创建的回复在发送后可见。 |
| `docs/change-log.md` | 记录了本次修复。 |

### 验证

| 命令 | 结果 |
|---|---|
| `pnpm --filter @agenthub/web test -- workspace-shell` | 通过：9 个测试文件，44 个测试。 |
| `pnpm --filter @agenthub/web check` | 通过。 |
| `git diff --check` | 通过。 |

---

## P16-7 预演与冻结审查

**日期：** 2026-05-29

### 修改的文件

| 文件 | 变更 |
|---|---|
| `docs/p16-freeze-review.md` | 添加了 P16 冻结决策、运行时配置证据、安全注意事项和推荐标签。 |
| `docs/project-state.md` | 记录了 P16 冻结就绪状态，并配置了 role/provider 目标。 |
| `docs/change-log.md` | 记录了本次冻结审查。 |
| `openspec/changes/agenthub-p16-agent-runtime-configuration/tasks.md` | 在验证后标记 P16-7、非目标和验证完成。 |

### 变更内容

P16 冻结审查确认运行时配置可以配置 Planner、前端和后端提供者默认值，同时保留 P6-P15b 基线和现有的 target/approval 安全模型。

### 验证

| 命令 | 结果 |
|---|---|
| `pnpm check` | 通过。 |
| `pnpm test` | 通过：Web 43 个测试，API 304 个测试，demo-api 5 个测试。 |
| `pnpm demo:api:test` | 通过：5 个测试。 |
| `git diff --check` | 通过。 |
| `openspec validate agenthub-p16-agent-runtime-configuration --strict` | 通过。 |

---

## P16-6 安全与策略执行

**日期：** 2026-05-29

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/api/app/agent_runtime_config.py` | 添加了 role/mode 策略验证，确保运行时配置不能将后端分配给平台维护模式。 |
| `apps/api/tests/test_agent_runtime_config.py` | 为后端平台维护模式添加了负向 API 验证覆盖。 |
| `apps/api/tests/test_task_runs.py` | 添加了执行覆盖测试，证明后端运行时配置不会绕过平台审批。 |
| `docs/project-state.md` | 记录了 P16-6 安全策略行为。 |
| `docs/change-log.md` | 已记录此实现。 |
| `openspec/changes/agenthub-p16-agent-runtime-configuration/tasks.md` | 验证后标记 P16-6 完成。 |

### 变更内容

运行时配置仍从属于现有的目标注册表、平台模式和审批策略。它可以选择安全的角色提供者，但无法将普通后端角色转变为未经批准的 AgentHub 平台维护。

### 验证

| 命令 | 结果 |
|---|---|
| P16-6 定向负向策略测试 | 通过：2 个测试。 |

---

## P16-5 运行时配置证据

**日期：** 2026-05-29

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/api/app/schemas.py` | 在 TaskRun 响应中添加了顶层 `providerAssignment` 和 `runtimeConfigResolution` 字段。 |
| `apps/api/app/main.py` | 在 TaskRun API 响应中返回了 provider/runtime 配置解析元数据。 |
| `apps/api/app/mission_trace.py` | 在任务追踪的任务运行条目中包含了运行时配置解析信息。 |
| `apps/api/app/planning.py` | 将运行时配置解析附加到规划器的证据中，用于运行时选择的规划器运行。 |
| `apps/api/tests/test_planning.py` | 为运行时选择的 Planner 提供者添加了规划器证据断言。 |
| `apps/api/tests/test_task_runs.py` | 添加了 TaskRun 响应和任务追踪运行时配置证据覆盖。 |
| `docs/project-state.md` | 记录了 P16-5 证据行为。 |
| `docs/change-log.md` | 已记录此实现。 |
| `openspec/changes/agenthub-p16-agent-runtime-configuration/tasks.md` | 验证后标记 P16-5 完成。 |

### 变更内容

运行时配置选择现在在 API 和任务追踪证据中可见，使得 Planner/Frontend/Backend 提供者解析可审计，同时不暴露密钥或受保护路径。

### 验证

| 命令 | 结果 |
|---|---|
| P16-5 定向 planner/task-run/mission-trace 测试 | 通过：3 个测试。 |

---

## P16-4 运行时配置解析

**日期：** 2026-05-29

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/api/app/agent_runtime_config.py` | 为工作区运行时配置添加了已启用的角色解析元数据。 |
| `apps/api/app/planner_providers.py` | 允许显式的运行时提供者 ID（如 `claude-cli-planner`）解析真实的 Claude CLI 规划器。 |
| `apps/api/app/planning.py` | 当存在已启用的 Planner 运行时配置时，将无提及的 Orchestrator 规划路由到该配置。 |
| `apps/api/app/provider_assignments.py` | 在传统的 matrix/default 选择之前添加了运行时配置提供者分配来源。 |
| `apps/api/app/task_runs.py` | 将已启用的 Frontend/Backend 运行时配置应用于 TaskRun adapter/provider 选择。 |
| `apps/api/tests/test_planner_providers.py` | 添加了运行时提供者 ID 解析器覆盖。 |
| `apps/api/tests/test_planning.py` | 添加了 Planner 运行时配置路由覆盖。 |
| `apps/api/tests/test_task_runs.py` | 添加了 Frontend/Backend 运行时适配器覆盖覆盖。 |
| `docs/project-state.md` | 记录了 P16-4 行为和下一步证据步骤。 |
| `docs/change-log.md` | 已记录此实现。 |
| `openspec/changes/agenthub-p16-agent-runtime-configuration/tasks.md` | 验证后标记 P16-4 完成。 |

### 变更内容

运行时配置现在影响实际的规划器和代码代理解析，同时保留显式适配器覆盖和不存在配置时的传统默认值。

### 验证

| 命令 | 结果 |
|---|---|
| P16-4 定向 planner/provider/task-run 测试 | 通过：5 个测试。 |

---

## P16-3 代理运行时设置 UI

**日期：** 2026-05-29

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/web/src/lib/api.ts` | 添加了代理运行时配置类型及 GET/PUT 客户端辅助函数。 |
| `apps/web/src/components/agent-runtime-settings.tsx` | 为 Planner、Frontend 和 Backend 角色添加了侧边栏运行时设置 UI。 |
| `apps/web/src/components/session-sidebar.tsx` | 为运行时设置面板添加了一个插槽。 |
| `apps/web/src/components/workspace-shell.tsx` | Loaded/saved 工作区运行时配置并连接了运行时设置面板。 |
| `apps/web/src/lib/api.test.ts` | 添加了运行时配置客户端辅助函数覆盖。 |
| `apps/web/src/components/workspace-shell.test.tsx` | 添加了运行时设置渲染覆盖。 |
| `docs/project-state.md` | 记录了 P16-3 行为和限制。 |
| `docs/change-log.md` | 已记录此实现。 |
| `openspec/changes/agenthub-p16-agent-runtime-configuration/tasks.md` | 验证后标记 P16-3 完成。 |

### 变更内容

AgentHub 现在拥有面向用户的运行时设置面板，用于从现有安全的 profile/provider 元数据配置 Planner、Frontend 和 Backend 代理默认值。UI 通过运行时配置 API 持久化，但尚未影响实际的提供者解析。

### 验证

| 命令 | 结果 |
|---|---|
| `pnpm --filter @agenthub/web check` | 通过。 |
| `pnpm --filter @agenthub/web test` | 通过：43 个测试。 |

---

## P16-2 运行时配置 API

**日期：** 2026-05-29

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/api/app/provider_configs.py` | 添加了 `claude-cli-planner` 提供者元数据，用于可配置的 Planner 代理选择。 |
| `apps/api/app/agent_runtime_config.py` | 新增针对 AgentProfile 和 ProviderConfig 元数据的运行时配置验证。 |
| `apps/api/app/schemas.py` | 新增运行时配置 request/response 和验证模式。 |
| `apps/api/app/main.py` | 新增运行时配置 GET、validate 和 PUT 工作区端点。 |
| `apps/api/tests/test_agent_runtime_config.py` | 新增运行时配置 API 默认值、验证、持久化和无效赋值测试。 |
| `apps/api/tests/test_models.py` | 更新了 `AgentRuntimeConfig` 的模型边界白名单。 |
| `apps/api/tests/test_provider_configs.py` | 更新了规划器提供者的提供者注册表预期。 |
| `docs/project-state.md` | 记录了 P16-2 行为及剩余限制。 |
| `docs/change-log.md` | 记录了本次实现。 |
| `openspec/changes/agenthub-p16-agent-runtime-configuration/tasks.md` | 验证后将 P16-2 标记为完成。 |

### 变更内容

现在可以通过 API 端点读取、验证和持久化工作区运行时配置。该 API 暴露了安全可选的 provider/profile 元数据，并在持久化之前阻止无效的 role/profile/provider/mode 组合。

### 验证

| 命令 | 结果 |
|---|---|
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_agent_runtime_config.py tests/test_provider_configs.py -q` | 通过：9 个测试。 |

---

## P16-1 Agent 运行时配置模型

**日期：** 2026-05-29

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/api/app/models.py` | 为 workspace/global-scoped 运行时角色默认值新增了 `AgentRuntimeConfig` 表模型。 |
| `apps/api/app/agent_runtime_config.py` | 新增了运行时角色配置数据类、默认有效配置、工作区配置 upsert、JSON 序列化以及不支持角色的验证。 |
| `apps/api/tests/test_agent_runtime_config.py` | 新增了 model/default/round-trip/serialization 测试。 |
| `docs/project-state.md` | 记录了 P16-1 行为及限制。 |
| `docs/change-log.md` | 记录了本次实现。 |
| `openspec/changes/agenthub-p16-agent-runtime-configuration/*` | 新增了 P16 OpenSpec 制品，并在验证后将 P16-1 标记为完成。 |

### 变更内容

AgentHub 现在可以为规划器、前端、后端和审查角色持久化工作区级别的运行时配置骨架。如果不存在配置，有效运行时配置会报告 `configSource=default` 并禁用覆盖，因此现有提供者行为保持不变。

### 验证

| 命令 | 结果 |
|---|---|
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_agent_runtime_config.py -q` | 通过：4 个测试。 |

---

## P15b-7 真实 LLM 规划器突破预演与冻结审查

**日期：** 2026-05-29

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/api/app/planning.py` | 在启用时，将无提及编排器规划连接到真实 LLM 规划器提供者；在规划器失败时保留确定性兜底；在直接分配计划中包含安全且明确引用的演示前端文件。 |
| `apps/api/app/planner_providers.py` | 收紧 Claude CLI 规划器提示，要求一个 PlannerResponse JSON 对象、有界任务、有效角色、有效制品类型以及稳定的依赖别名。 |
| `apps/api/app/planner_contracts.py` | 安全地规范化了冒烟测试期间出现的真实提供者 `version` 和 `guardrailNotes` 变体。 |
| `apps/api/app/plan_validator.py` | 允许配置的验证命令带有安全结果后缀，例如 `pnpm build succeeds`，同时仍拒绝不支持的命令。 |
| `pnpm build succeeds` | 在任务图验证之前规范化了安全的基于目标的依赖别名。 |
| `apps/api/app/llm_planner.py` | 允许计划的 `llm_v1` 审查任务由生成的审查制品满足。 |
| `apps/api/app/main.py` | 将已完成的上级依赖差异文件视为下游后续任务的安全脏工作区上下文。 |
| `llm_v1` | 新增了依赖别名规范化和安全命令注释验证覆盖。 |
| `apps/api/app/scheduler.py` | 新增了安全标量规范化覆盖。 |
| `apps/api/tests/test_llm_planner.py` | 更新了 Claude CLI 规划器提示断言。 |
| `apps/api/tests/test_planner_contracts.py` | 新增了真实规划器路由测试覆盖和安全引用的演示文件覆盖。 |
| `apps/api/tests/test_planner_providers.py` | 新增了已完成依赖差异的下游脏工作区继承覆盖。 |
| `apps/api/tests/test_planning.py` | 新增了生成的审查制品满足计划 `llm_v1` 审查任务的覆盖。 |
| `apps/api/tests/test_scheduler.py` | 新增了 P15b 冻结决策、首次失败运行证据、后续修复证据、build/preview/staging 证据、注意事项和推荐标签。 |
| `apps/api/tests/test_task_runs.py` | 记录了 P15b-7 行为、证据和剩余注意事项。 |
| `llm_v1` | 记录了本次冻结审查。 |
| `docs/p15b-freeze-review.md` | 在验证后将 P15b-7 和验证标记为完成。 |

### 变更内容

P15b 现在端到端地证明了真实 LLM 规划器路径：Breakout 请求被
由 Claude CLI 规划器提供者规划，规划源为 `real_llm`，然后
通过真实编码适配器执行。最初的 Claude Code 实现产生了 diff/review/preview 证据，但因 `pnpm build` 捕获到 TypeScript 严格性错误而导致本地暂存部署失败。后续修复使用了相同的 AgentHub task/run 路径；Claude Code 记录了一个真实的提供者运行时错误，然后 Codex 完成了修复，构建通过，预览健康，本地暂存部署准备就绪。

### 验证

| 命令 | 结果 |
|---|---|
| P15b-7 真实规划器 / 冒烟测试 | 后续修复后通过：暂存部署 `f26b64e1-0174-46be-8040-e978b7eacd22` 在 `http://127.0.0.1:65495` 就绪。 |
| P15b-7 定向规划器 / 调度器 / 任务运行测试 | 通过：31 个测试。 |
| `pnpm check` | 通过。 |
| `pnpm test` | 通过：web 41 个测试，API 289 个测试，demo-api 5 个测试。 |
| `pnpm demo:api:test` | 通过：5 个测试。 |
| `git diff --check` | 通过。 |
| `openspec validate agenthub-p15b-real-llm-planner-engine --strict` | 通过。 |

---

## P15b-6 规划器证据与任务追踪

**日期：** 2026-05-28

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/api/app/llm_planner.py` | 在创建的 `llm_v1` 个任务上记录了安全的规划器证据，包括提供者身份、来源、持续时间、验证结果、理由、计划 ID 和创建的任务 ID。 |
| `apps/api/app/mission_trace.py` | 在任务追踪条目中，为 real/fake LLM、disabled/fallback 和确定性规划路径暴露了规划器证据。 |
| `apps/api/tests/test_llm_planner.py` | 为 fake/test 规划器输出添加了规划器证据和任务追踪覆盖，且不泄露原始提供者输出。 |
| `docs/project-state.md` | 记录了 P15b-6 的行为和限制。 |
| `docs/change-log.md` | 记录了本次实现。 |
| `openspec/changes/agenthub-p15b-real-llm-planner-engine/tasks.md` | 验证后将 P15b-6 标记为完成。 |

### 变更内容

`llm_v1` 个任务计划在通过模式和政策验证后，现在保留可审计的规划器证据。任务追踪根据路径将规划器来源暴露为 real/fake、disabled/fallback 或确定性。证据仅为元数据；不包含原始提供者输出和凭据。

### 验证

| 命令 | 结果 |
|---|---|
| P15b-6 定向规划器证据 / 任务追踪测试 | 通过：6 个测试。 |

---

## P15b-5 针对真实 LLM 输出的 PlanValidator 强化

**日期：** 2026-05-28

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/api/app/plan_validator.py` | 强化了针对已注册目标策略、平台模式、AgentProfile capability/safety、验证命令策略和依赖键的任务图验证。 |
| `apps/api/app/llm_planner.py` | 将启用的 AgentProfile 元数据传递给 PlanValidator，用于 `llm_v1` 任务创建。 |
| `apps/api/tests/test_llm_planner.py` | 添加了对不安全 role/write 能力和不支持的验证命令输出的拒绝覆盖。 |
| `docs/project-state.md` | 记录了 P15b-5 的行为和限制。 |
| `docs/change-log.md` | 记录了本次实现。 |
| `openspec/changes/agenthub-p15b-real-llm-planner-engine/tasks.md` | 验证后将 P15b-5 标记为完成。 |

### 变更内容

真实的 LLM 候选任务图在任务持久化之前，现在会通过更严格的策略验证。验证检查已知目标、目标路径策略、平台 mode/approval 要求、AgentProfile 支持的 targets/modes、安全写入和安全审查标志、依赖键引用以及目标范围的验证命令策略。

不安全的计划会在 TaskRun 自动启动或持久化之前诚实地失败。

### 验证

| 命令 | 结果 |
|---|---|
| P15b-5 定向 LLM planner/contract/planning 测试 | 通过：40 个测试。 |

---

## P15b-4 结构化输出解析与验证

**日期：** 2026-05-28

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/api/app/llm_planner.py` | 为单个嵌入的规划器 JSON 对象添加了安全的 JSON 提取，并拒绝歧义的多个负载。 |
| `apps/api/tests/test_planner_contracts.py` | 添加了嵌入的 JSON 提取、歧义 JSON 拒绝、缺失字段拒绝和无静默归一化覆盖。 |
| `docs/project-state.md` | 记录了 P15b-4 的行为和限制。 |
| `docs/change-log.md` | 记录了本次实现。 |
| `openspec/changes/agenthub-p15b-real-llm-planner-engine/tasks.md` | 验证后将 P15b-4 标记为完成。 |

### 变更内容

规划器输出解析现在接受直接的 JSON 或从提供者 prose/fenced 输出中安全提取的一个外层 JSON 对象。多个外层 JSON 负载被视为歧义并被拒绝。提取的负载在任务图验证之前仍必须满足 `PlannerResponse` 模式。

解析器不会静默地将未知目标、角色、路径或不安全值重写为允许的值；这些值会原封不动地进入策略验证，并必须在那里被拒绝。

### 验证

| 命令 | 结果 |
|---|---|
| P15b-4 定向规划器 contract/LLM planner/provider 测试 | 通过：24 个测试。 |

---

## P15b-3 真实规划器提供者实现

**日期：** 2026-05-28

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/api/app/planner_providers.py` | 添加了 `claude_cli` 真实规划器提供者路径，约束了命令形态，超时处理，并规范化了 auth/quota/runtime/unavailable 错误。 |
| `apps/api/app/config.py` | 为真实规划器提供者超时控制添加了 `AGENTHUB_LLM_PLANNER_TIMEOUT_SEC`。 |
| `apps/api/tests/test_planner_providers.py` | 添加了 `claude_cli` 解析器、命令形态、成功、超时、缺少二进制文件和规范化错误覆盖。 |
| `docs/project-state.md` | 记录了 P15b-3 的行为和限制。 |
| `docs/change-log.md` | 记录了本次实现。 |
| `openspec/changes/agenthub-p15b-real-llm-planner-engine/tasks.md` | 验证后将 P15b-3 标记为完成。 |

### 变更内容

AgentHub 现在可以显式选择 `AGENTHUB_LLM_PLANNER_PROVIDER=claude_cli`
作为真实规划器提供者。该提供者以打印模式调用 Claude CLI，并附带
仅用于规划的提示词，捕获 stdout/stderr，应用超时，并记录
针对认证、配额、超时、可执行文件不可用、空输出
和运行时错误的规范化失败。

这仅添加了真实提供者路径。它不会运行真实规划器的冒烟测试，
不会声称规划成功，并且在冻结之前仍然需要结构化解析、
验证和后续演练。

### 验证

| 命令 | 结果 |
|---|---|
| P15b-3 目标规划器 provider/contract/LLM 规划器测试 | 通过：20 个测试。 |

---

## P15b-2 规划器请求/响应契约

**日期：** 2026-05-28

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/api/app/planner_contracts.py` | 添加了 `PlannerRequest`、`PlannerResponse`、规划器任务响应模式，以及提供者可见的编辑辅助函数。 |
| `apps/api/app/llm_planner.py` | 添加了 `build_llm_planner_request`，将现有规划器输入通过请求契约路由，并使用 `PlannerResponse` 对规划器输出进行模式验证。 |
| `apps/api/tests/test_planner_contracts.py` | 添加了请求上下文、受保护值编辑、响应模式、不完整响应拒绝以及解析集成覆盖。 |
| `apps/api/tests/test_llm_planner.py` | 将伪造规划器负载更新为正式响应契约。 |
| `docs/project-state.md` | 记录了 P15b-2 的行为和限制。 |
| `docs/change-log.md` | 记录了本次实现。 |
| `openspec/changes/agenthub-p15b-real-llm-planner-engine/tasks.md` | 验证后将 P15b-2 标记为完成。 |

### 变更内容

`llm_v1` 规划现在具有正式的请求和响应契约。请求
保留原始用户请求，包含规范上下文、目标
registry/project 分析器摘要、最近消息、制品引用、
支持的 roles/modes/capabilities 和护栏，然后编辑提供者可见的
类似秘密的值和受保护的绝对路径。

规划器输出现在在现有的 PlanValidator 路径之前，根据 `PlannerResponse` 进行检查。
这定义了后续真实提供者输出必须满足的必需 plan/task 字段。

### 验证

| 命令 | 结果 |
|---|---|
| P15b-2 目标规划器 contract/provider/planning 测试 | 通过：40 个测试。 |

---

## P15b-1 规划器提供者抽象

**日期：** 2026-05-28

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/api/app/planner_providers.py` | 添加了规划器提供者接口、result/error 元数据、禁用提供者、fake/test 提供者和显式提供者解析器。 |
| `apps/api/app/config.py` | 添加了默认值为禁用的 `AGENTHUB_LLM_PLANNER_PROVIDER` 设置。 |
| `apps/api/app/llm_planner.py` | 将规划器提供者结果元数据接入 LLM 规划器任务元数据和兜底元数据。 |
| `apps/api/app/planning.py` | 在确定性兜底规划中记录了所选规划器提供者元数据，并诚实地拒绝了未知的规划器提供者配置。 |
| `apps/api/tests/test_planner_providers.py` | 添加了提供者抽象、disabled/fake 提供者、选择、无效提供者和兜底元数据覆盖。 |
| `apps/api/tests/test_llm_planner.py` | 更新了 LLM 规划器测试以使用 fake/test 规划器提供者结果契约。 |
| `apps/api/tests/test_planning.py` | 更新了兜底元数据期望以包含规划器提供者身份和来源。 |
| `docs/project-state.md` | 记录了 P15b-1 的行为和限制。 |
| `docs/change-log.md` | 记录了本次实现。 |
| `openspec/changes/agenthub-p15b-real-llm-planner-engine/tasks.md` | 验证后将 P15b-1 标记为完成。 |

### 变更内容

AgentHub 现在拥有针对 `llm_v1` 的显式规划器提供者基础：
禁用和 fake/test 提供者、标准提供者 result/error 元数据、
通过 `AGENTHUB_LLM_PLANNER_PROVIDER` 进行的显式提供者选择，以及规划器
兜底元数据，用于记录提供者 ID、提供者类型、规划器来源和
状态。

这尚未添加真实的 LLM 规划器调用。未知的提供者配置
会被报告为无效提供者兜底，而不是静默地替换为
不同的提供者。

### 验证

| 命令 | 结果 |
|---|---|
| P15b-1 目标 planner/provider 测试 | 通过：35 个测试。 |

---

## P15-7 冻结审查

**日期：** 2026-05-28

### 修改的文件

| 文件 | 变更 |
|---|---|
| `docs/p15-freeze-review.md` | 添加了 P15 冻结决策、Breakout 证据、非目标、注意事项和推荐标签。 |
| `docs/project-state.md` | 记录了 P15 冻结状态。 |
| `docs/change-log.md` | 记录了本次冻结审查。 |
| `openspec/changes/agenthub-p15-real-coding-assistant-upgrade/tasks.md` | 验证完成后标记 P15-7、明确的非目标和验证完成。 |

### 变更内容

P15 冻结审查确认 AgentHub 已准备好作为真实编码助手升级版进行冻结。该阶段在保留先前基线的同时，允许通过透传指令和真实的 Claude Code 执行来处理有界的目标限定前端实现请求。

### 验证

| 命令 | 结果 |
|---|---|
| 最终 P15 验证套件 | 通过。 |

---

## P15-6 Breakout 游戏真实编码冒烟测试

**日期：** 2026-05-28

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/api/app/planning.py` | 在已注册的演示前端目标内，为有界的前端实现请求添加了通用的 `passthrough_v1` 路由。 |
| `apps/api/app/claude_code_adapter.py` | 允许 Claude Code 在 `Read`、`Edit` 和 `MultiEdit` 之外使用 `Write`，以便真实运行能在分配的工作树内创建新文件。 |
| `apps/api/app/guardrails.py` | 更新了文档化的 Claude Code 命令允许列表，以允许扩展后的写入工具集。 |
| `apps/api/app/diffs.py` | 在差异制品、统计信息、变更文件以及下游的 review/ledger 证据中包含了未跟踪的文件。 |
| `apps/api/tests/test_planning.py` | 为 `passthrough_v1` 路由添加了无提及的 Breakout 请求覆盖。 |
| `apps/api/tests/test_claude_code_adapter.py` | 更新了针对 `Write` 的 Claude Code 命令形态覆盖。 |
| `Write` | 更新了针对扩展后的 Claude Code 工具列表的运行时命令策略覆盖。 |
| `apps/api/tests/test_guardrails.py` | 添加了未跟踪文件差异收集覆盖。 |
| `apps/api/tests/test_diffs.py` | 记录了真实的 Claude Code Breakout 冒烟测试证据和注意事项。 |
| `docs/p15-breakout-smoke.md` | 记录了 P15-6 的行为、证据和限制。 |
| `docs/project-state.md` | 记录了本次实现。 |
| `docs/change-log.md` | 在目标验证和冒烟测试证据完成后标记 P15-6 完成。 |

### 变更内容

AgentHub 现在可以将有界的前端实现请求路由到 `passthrough_v1`，而无需将其重写为旧的演示模板。Breakout 冒烟测试使用了真实的 `ClaudeCodeAdapter` 执行，并生成了完整的运行、真实差异、脚本化审查、目标限定构建证据、健康的预览以及本地暂存部署。

该冒烟测试还修复了实际使用中发现的两个执行障碍：Claude Code 需要 `Write` 权限来创建新文件，并且差异收集需要包含未跟踪的代理创建文件。

### 验证

| 命令 / 冒烟测试 | 结果 |
|---|---|
| P15-6 目标限定 planning/adapter/guardrail/diff 测试 | 通过：6 个测试。 |
| 真实 Breakout 冒烟测试 | 通过，但有注意事项：浏览器点击自动化不可用。 |

---

## P15-5 规划器原理与任务审查元数据

**日期：** 2026-05-28

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/api/app/schemas.py` | 向任务响应中添加了 `planReviewMetadata`。 |
| `apps/api/app/main.py` | 从 `planJson`、`planDraft`、任务图、依赖关系、计划文件、验收标准和验证期望中派生出只读的计划审查元数据。 |
| `apps/api/tests/test_planning.py` | 为规划器模式、原理、目标、计划文件、任务图和只读元数据添加了 API 覆盖。 |
| `apps/web/src/lib/api.ts` | 为计划审查元数据添加了客户端类型支持。 |
| `apps/web/src/components/task-card-list.tsx` | 在任务卡片中渲染了紧凑的只读计划审查摘要。 |
| `apps/web/src/components/task-card-list.test.tsx` | 为规划器原理、任务图计数、目标、计划文件、验收、验证和只读状态添加了 UI 覆盖。 |
| `docs/project-state.md` | 记录了 P15-5 的行为和限制。 |
| `docs/change-log.md` | 记录了本次实现。 |
| `openspec/changes/agenthub-p15-real-coding-assistant-upgrade/tasks.md` | 在目标验证完成后标记 P15-5 完成。 |

### 变更内容

任务响应现在公开了一个只读的 `planReviewMetadata` 摘要，以便 UI 能够在不修改计划的情况下显示任务的规划方式。任务卡片时间线显示了规划器模式、目标、原理、分配的角色、计划文件、任务图计数、验收标准计数和验证期望计数。

元数据从现有计划数据派生，不会改变调度、适配器分发、任务执行或计划编辑行为。

### 验证

| 命令 | 结果 |
|---|---|
| P15-5 目标限定 API/UI 元数据测试 | 通过：46 个测试。 |

---

## P15-4 项目命令策略

**日期：** 2026-05-28

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/api/app/project_command_policy.py` | 添加了从目标注册表 check/test/build 命令派生的目标限定命令策略评估。 |
| `apps/api/app/external_evidence.py` | 已根据所选目标策略验证目标作用域的命令证据，并在制品 metadata/events. 中记录了 `targetId` |
| `apps/api/app/schemas.py` | 向命令证据 create/response 模式中添加了可选的 `targetId` |
| `apps/api/app/main.py` | 已通过命令证据 API 和响应映射传递了 `targetId` |
| `apps/api/tests/test_external_evidence.py` | 增加了对目标作用域命令证据验收、目标 ID 记录和错误命令拒绝的覆盖 |
| `docs/project-state.md` | 记录了 P15-4 的行为和限制 |
| `docs/change-log.md` | 记录了本次实现 |
| `openspec/changes/agenthub-p15-real-coding-assistant-upgrade/tasks.md` | 在定向验证后将 P15-4 标记为完成 |

### 变更内容

命令证据现在可以感知目标。当命令证据请求或任务计划识别出目标时，AgentHub 会在存储证据前，根据该目标注册的 `checkCommand`、`testCommand` 或 `buildCommand` 检查命令。存储的命令证据会如实记录 stdout、stderr、退出码、状态、命令类型、命令字符串和目标 ID。

没有目标的传统命令证据仍与现有的全局允许列表路径兼容。

### 验证

| 命令 | 结果 |
|---|---|
| P15-4 定向命令 evidence/review/instruction 测试 | 通过：9 个测试 |

---

## P15-3 宽松目标护栏

**日期：** 2026-05-28

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/api/app/guardrails.py` | 添加了目标感知路径评估，将注册的目标 allowed/denied 路径与现有受保护路径检查相结合 |
| `apps/api/app/main.py` | 更新了编排器自动启动安全检查，使用目标注册表路径策略替代旧的窄范围演示文件允许列表 |
| `apps/api/tests/test_guardrails.py` | 增加了对允许的目标文件、跨目标文件和受保护依赖路径的目标路径策略覆盖 |
| `apps/api/tests/test_planning.py` | 在注册的允许路径下，增加了对更广泛前端目标文件的自动启动策略覆盖 |
| `docs/project-state.md` | 记录了 P15-3 的行为和限制 |
| `docs/change-log.md` | 记录了本次实现 |
| `openspec/changes/agenthub-p15-real-coding-assistant-upgrade/tasks.md` | 在定向验证后将 P15-3 标记为完成 |

### 变更内容

注册的目标元数据现在驱动更广泛编码任务的安全边界。安全的前端自动运行可以覆盖 `demo-frontend` 允许路径内的有意义文件，例如 `apps/demo/src` 下的新组件，而无需回退到旧的仅限登录页面的文件列表。

更广泛的权限仍然限定在目标范围内。受保护路径、拒绝路径、跨目标 backend/platform 路径、绝对路径、遍历路径和普通平台代码修改仍然被阻止。

### 验证

| 命令 | 结果 |
|---|---|
| P15-3 定向护栏和规划测试 | 通过：5 个测试 |

---

## P15-2 透传指令模式

**日期：** 2026-05-28

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/api/app/instruction_builder.py` | 在确定性演示模板分支之前，为 `llm_v1` / `passthrough_v1` 计划添加了透传指令渲染 |
| `apps/api/tests/test_task_runs.py` | 添加了 Breakout 风格的指令覆盖证明，证明原始请求被保留，旧的演示槽重写被跳过 |
| `docs/project-state.md` | 记录了 P15-2 的行为和限制 |
| `docs/change-log.md` | 记录了本次实现 |
| `openspec/changes/agenthub-p15-real-coding-assistant-upgrade/tasks.md` | 在定向验证后将 P15-2 标记为完成 |

### 变更内容

提供者指令现在为 `llm_v1` 和 `passthrough_v1` 计划保留原始的 request/task 描述。共享的目标、上下文、契约、制品、验收、验证和护栏部分仍然通过现有的提供者特定包装器渲染，但旧的 login-page/button/demo-slot 指令不再覆盖透传计划。

### 验证

| 命令 | 结果 |
|---|---|
| P15-2 定向指令测试 | 通过：4 个测试 |

---

## P15-1 LLM 规划器 v1

**日期：** 2026-05-28

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/api/app/llm_planner.py` | 添加了 LLM 规划器输入构建器、结构化 JSON 解析器、PlanDraft/task 创建服务、target/role 验证和兜底元数据辅助函数 |
| `apps/api/app/planner_service.py` | 扩展了 PlanDraft 元数据，包含规划器模式、验收标准、验证期望、护栏说明和兜底原因 |
| `apps/api/app/plan_validator.py` | 允许针对注册的目标允许路径进行 LLM 规划器输出的验证，同时保留旧的演示默认值 |
| `apps/api/app/config.py` | 添加了 `AGENTHUB_LLM_PLANNER_ENABLED` 设置，默认禁用 |
| `apps/api/app/planning.py` | 在编排器确定性兜底计划上记录了显式的 `llm_v1` 兜底元数据 |
| `apps/api/tests/test_llm_planner.py` | 增加了对 LLM 规划器输入、有效输出、任务持久化和不安全输出拒绝的覆盖 |
| `apps/api/tests/test_planning.py` | 为 PlanDraft 规划器模式添加了回归断言，并禁用了 LLM 兜底元数据。 |
| `docs/project-state.md` | 记录了 P15-1 的行为和限制。 |
| `docs/change-log.md` | 记录了本次实现。 |
| `openspec/changes/agenthub-p15-real-coding-assistant-upgrade/tasks.md` | 在针对性验证后将 P15-1 标记为完成。 |

### 变更内容

P15 现在拥有一个 `llm_v1` 规划基础，而无需声称成功的实时 LLM 规划器。
新的规划器服务可以构建对提供者可见的规划上下文，
解析结构化的 JSON 输出，
通过 PlanValidator 验证 target/role/file 安全性，
并持久化已验证的任务。现有的确定性路径仍然是运行时默认选项，并且现在会记录未使用 `llm_v1` 的原因。

### 验证

| 命令 | 结果 |
|---|---|
| P15-1 针对性规划器测试 | 通过：7 个测试。 |

---

## P14-7 演练与冻结审查

**日期：** 2026-05-28

### 修改的文件

| 文件 | 变更 |
|---|---|
| `docs/p14-freeze-review.md` | 添加了 P14 冻结决策、演练证据、注意事项和推荐标签。 |
| `docs/project-state.md` | 记录了 P14-7 冻结结果和当前 P14 状态。 |
| `docs/change-log.md` | 记录了本次冻结审查。 |
| `openspec/changes/agenthub-p14-custom-agent-provider-foundation/tasks.md` | 在验证后将 P14-7、明确的非目标和验证标记为完成。 |

### 变更内容

P14 冻结审查确认了自定义 agent/provider 基础已完成，无需添加市场行为或不安全的自定义执行。
审查验证了内置配置文件、提供者感知选择、capability/target 拒绝、
Agent Contact UI 元数据、安全草稿元数据、确定性混合提供者证据
以及 P6-P13 基线保留。

### 验证

| 命令 | 结果 |
|---|---|
| P14 针对性后端演练测试 | 通过：11 个测试。 |
| P14 针对性前端 UI/API 测试 | 通过：9 个文件 / 40 个测试。 |

---

## P14-6 安全自定义 Agent 草稿

**日期：** 2026-05-28

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/api/app/models.py` | 为安全草稿配置文件添加了 `AgentProfileDraft` 元数据表。 |
| `apps/api/app/agent_profile_drafts.py` | 添加了带有安全验证的草稿 creation/listing 服务。 |
| `apps/api/app/agent_profiles.py` | 将草稿行转换为 AgentProfile 注册表响应。 |
| `apps/api/app/schemas.py` | 添加了草稿创建请求模式。 |
| `apps/api/app/main.py` | 添加了草稿 create/list 端点，并将草稿包含在工作区 AgentProfile 注册表响应中。 |
| `apps/api/tests/test_agent_profile_drafts.py` | 添加了仅审查草稿创建和不安全草稿拒绝的 API 覆盖。 |
| `apps/api/tests/test_models.py` | 更新了新元数据表的模型边界覆盖。 |
| `docs/project-state.md` | 记录了 P14-6 的行为和限制。 |
| `docs/change-log.md` | 记录了本次实现。 |
| `openspec/changes/agenthub-p14-custom-agent-provider-foundation/tasks.md` | 在针对性验证后将 P14-6 标记为完成。 |

### 变更内容

AgentHub 现在可以定义安全的自定义 AgentProfile 草稿元数据，而无需使草稿成为可执行的写入 Agent。
草稿配置文件被强制设置为仅审查或禁用状态，并包含在 AgentProfile 注册表中以供检查。

草稿创建会拒绝任意 shell 命令、不安全的工具权限、
不受限制的文件系统访问、写入能力、未知提供者以及
adapter/provider 不匹配。

### 验证

| 命令 | 结果 |
|---|---|
| 安全 draft/model/profile 针对性测试 | 通过：6 个测试。 |

---

## P14-5 Agent Contact UI 升级

**日期：** 2026-05-28

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/api/app/schemas.py` | 向 Agent 联系响应合约添加了提供者 ID、支持的目标和支持的模式。 |
| `apps/api/app/main.py` | 从 `/workspaces/{workspace_id}/agents` 返回了 P14 配置文件元数据，包括虚拟 review/fallback 联系人。 |
| `apps/api/tests/test_planning.py` | 为提供者和 target/mode 元数据添加了联系 API 断言。 |
| `apps/web/src/lib/api.ts` | 向 AgentContact 客户端类型添加了 provider/target/mode 字段。 |
| `apps/web/src/components/agent-contact-list.tsx` | 渲染了提供者徽章、支持的目标芯片、能力芯片和 unavailable/auth/draft/disabled 状态标签。 |
| `apps/web/src/lib/api.test.ts` | 更新了联系 API 客户端夹具覆盖，以包含提供者和目标元数据。 |
| `apps/web/src/app/page.test.tsx` | 更新了页面夹具 AgentContact 元数据。 |
| `apps/web/src/components/workspace-shell.test.tsx` | 为提供者和支持的目标显示添加了 UI 断言。 |
| `docs/project-state.md` | 记录了 P14-5 的行为和限制。 |
| `docs/change-log.md` | 记录了本次实现。 |
| `openspec/changes/agenthub-p14-custom-agent-provider-foundation/tasks.md` | 在针对性验证后将 P14-5 标记为完成。 |

### 变更内容

现有的 Agent Contact UI 现在公开了后端策略已使用的 P14 注册表元数据：提供者身份、适配器类型、支持的目标、
能力标签和可用性状态。视觉上的 直接聊天 / 群组
工作流模式及所有任务执行控制保持不变。

### 验证

| 命令 | 结果 |
|---|---|
| Web contact/API/page 定向测试 | 通过：40 个测试。 |
| 工作区代理联系 API 定向测试 | 通过：1 个测试。 |

---

## P14-4 代理选择策略

**日期：** 2026-05-28

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/api/app/agent_selection_policy.py` | 为 TaskRun 代理选择添加了目标、模式、能力、写入安全性和审查安全性的验证。 |
| `apps/api/app/task_runs.py` | 在 TaskRun 创建期间应用代理选择策略，并在 TaskRun 指标中记录选择元数据。 |
| `apps/api/app/agent_profiles.py` | 向后端配置文件添加了显式的平台维护支持元数据，同时保留了调度器审批关卡。 |
| `apps/api/tests/test_agent_selection_policy.py` | 为元数据、不支持的目标、缺失的能力以及不安全的审查分配添加了选择策略覆盖。 |
| `docs/project-state.md` | 记录了 P14-4 的行为和限制。 |
| `docs/change-log.md` | 记录了本次实现。 |
| `openspec/changes/agenthub-p14-custom-agent-provider-foundation/tasks.md` | 验证后将 P14-4 标记为完成。 |

### 变更内容

TaskRun 创建现在会根据任务的目标、所需模式、所需能力以及 write/review 安全标志来验证分配的代理配置文件。无效的目标或能力分配会在适配器执行前诚实地失败。成功的运行会在 `TaskRun.metricsJson` 中记录 `agentSelection` 元数据。

平台维护仍然需要通过现有调度器和护栏路径的审批；P14-4 仅使配置文件支持足够明确，以便选择策略使用。

### 验证

| 命令 | 结果 |
|---|---|
| 定向代理选择策略测试 | 通过：4 个测试。 |
| 平台维护 TaskRun 回归测试 | 通过：1 个测试。 |

---

## P14-3 能力与模式模式

**日期：** 2026-05-28

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/api/app/agent_capabilities.py` | 添加了受控的支持模式和能力标签，并附带验证辅助函数。 |
| `apps/api/app/agent_profiles.py` | 将内置的 AgentProfile 能力标签和支持模式与受控模式对齐。 |
| `apps/api/app/provider_configs.py` | 根据受控模式验证了提供者配置的支持模式。 |
| `apps/api/tests/test_agent_capabilities.py` | 为不支持的 modes/capability 标签添加了模式及拒绝覆盖。 |
| `apps/api/tests/test_planning.py` | 将 AgentProfile 和联系断言更新为受控的 capability/mode 值。 |
| `apps/web/src/lib/api.test.ts` | 更新了 API 测试夹具以使用受控的 capability/mode 值。 |
| `docs/project-state.md` | 记录了 P14-3 的行为和限制。 |
| `docs/change-log.md` | 记录了本次实现。 |
| `openspec/changes/agenthub-p14-custom-agent-provider-foundation/tasks.md` | 验证后将 P14-3 标记为完成。 |

### 变更内容

AgentHub 现在定义了受控的执行模式：

- `frontend`；
- `backend`；
- `qa`；
- `review`；
- `platform_maintenance`；
- `read_only`；
- `debug`。

AgentHub 还定义了受控的能力标签：

- `code_write`；
- `code_review`；
- `test_run`；
- `diff_analysis`；
- `preview`；
- `deploy_staging`；
- `platform_change`。

内置的 AgentProfile 和 ProviderConfig 元数据现在使用这些受控值。不支持的值将导致验证失败，而不会成为自由形式的权限。

### 验证

| 命令 | 结果 |
|---|---|
| 定向 capability/profile/provider 测试 | 通过：5 个测试。 |
| 定向 Web API 测试 | 通过：40 个测试。 |

---

## P14-2 提供者配置注册表

**日期：** 2026-05-28

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/api/app/provider_configs.py` | 为 Claude Code CLI、Codex CLI 和 Scripted Mock 添加了非机密提供者配置元数据。 |
| `apps/api/app/schemas.py` | 添加了 ProviderConfig API 响应模式。 |
| `apps/api/app/main.py` | 添加了只读的 `/provider-configs` 端点。 |
| `apps/api/tests/test_provider_configs.py` | 添加了提供者配置 API 覆盖和机密字段防护。 |
| `apps/web/src/lib/api.ts` | 添加了 ProviderConfig 客户端类型和 `listProviderConfigs`。 |
| `apps/web/src/lib/api.test.ts` | 为提供者配置元数据添加了 Web API 覆盖。 |
| `docs/project-state.md` | 记录了 P14-2 的行为和限制。 |
| `docs/change-log.md` | 记录了本次实现。 |
| `openspec/changes/agenthub-p14-custom-agent-provider-foundation/tasks.md` | 验证后将 P14-2 标记为完成。 |

### 变更内容

AgentHub 现在为当前本地提供者公开了一个只读的提供者配置注册表：

- Claude Code CLI；
- Codex CLI；
- Scripted Mock。

提供者配置元数据包括提供者 ID、显示名称、适配器类型、认证状态、可用性、默认角色和支持的模式。该注册表不存储或暴露机密、令牌、API 密钥或原始凭据。

P14-2 不实现云令牌管理、提供者市场行为、提供者安装或适配器调度变更。

### 验证

| 命令 | 结果 |
|---|---|
| 定向提供者配置 API 测试 | 通过：1 个测试。 |
| 针对性 Web API 测试 | 通过：40 项测试。 |

---

## P14-1 代理配置文件注册表

**日期：** 2026-05-28

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/api/app/agent_profiles.py` | 将 AgentProfile 升级为注册表风格的服务，新增状态字段，并添加了虚拟的 review/fallback 配置文件。 |
| `apps/api/app/schemas.py` | 在 API 响应中新增了 AgentProfile `status`。 |
| `status` | 从工作区配置文件 API 返回注册表配置文件，包括内置的审查和兜底配置文件。 |
| `apps/api/app/main.py` | 更新了配置文件 API 对注册表字段、状态、审查配置文件和兜底配置文件的覆盖范围。 |
| `apps/api/tests/test_planning.py` | 在 AgentProfile 客户端类型中新增了 `apps/web/src/lib/api.ts`。 |
| `apps/web/src/lib/api.ts` | 更新了客户端 API 夹具对 AgentProfile 状态的覆盖范围。 |
| `status` | 记录了 P14-1 的行为和限制。 |
| `apps/web/src/lib/api.test.ts` | 记录了本次实现。 |
| `docs/project-state.md` | 验证完成后将 P14-1 标记为完成。 |

### 变更内容

AgentHub 现在为内置配置文件提供了一个稳定的代理配置文件注册表契约。工作区配置文件 API 包含基于数据库的活动代理以及虚拟的审查和兜底配置文件。配置文件现在包含 `openspec/changes/agenthub-p14-custom-agent-provider-foundation/tasks.md`，因此可以表示可用、计划中、已禁用或未来草稿状态，而无需暗示写入执行。

P14-1 不包含提供者配置、能力强制、自定义草稿创建、市场行为或适配器调度变更。

### 验证

| 命令 | 结果 |
|---|---|
| 针对性配置文件 API 测试 | 通过：2 项测试。 |
| 针对性 Web API 测试 | 通过：39 项测试。 |

---

## P13-8 混合提供者预演与冻结审查

**日期：** 2026-05-27

### 修改的文件

| 文件 | 变更 |
|---|---|
| `status` | 通过 review/fallback 阶段部署证据，为后端=Codex 和前端=Claude Code 的提供者分配添加了确定性的 P13 冻结预演。 |
| `apps/api/tests/test_cross_provider_rehearsal.py` | 记录了 P13 冻结决策、预演路径、证据和注意事项。 |
| `docs/p13-freeze-review.md` | 记录了 P13-8 冻结结果和限制。 |
| `docs/project-state.md` | 记录了本次实现。 |
| `docs/change-log.md` | 验证完成后将 P13-8 和明确的非目标标记为完成。 |

### 变更内容

P13 现在拥有一个确定性的冻结预演，该预演模拟了一个有界的混合提供者工作流，但不声称具有实时的 diff/review/preview/local 执行能力。该预演创建一个共享的迷你 CRM 契约，将后端工作分配给 Codex，前端工作分配给 Claude Code，验证提供者感知的交接元数据，捕获差异和审查证据，启动一个健康的预览，记录本地阶段部署，并检查任务轨迹中提供者的可见性。

### 验证

| 命令 | 结果 |
|---|---|
| P13 混合提供者预演测试 | 通过：1 项测试。 |

---

## P13-7 混合提供者调度器集成

**日期：** 2026-05-27

### 修改的文件

| 文件 | 变更 |
|---|---|
| `openspec/changes/agenthub-p13-cross-provider-agent-coordination/tasks.md` | 在终端调度器元数据中保留了提供者 ID、提供者分配、重试 ID 和兜底 ID。 |
| `apps/api/app/scheduler.py` | 为混合提供者调度器增加了对依赖项、目标锁、不同目标并发和失败元数据的覆盖。 |
| `apps/api/tests/test_scheduler.py` | 记录了 P13-7 的行为和限制。 |
| `docs/project-state.md` | 记录了本次实现。 |
| `docs/change-log.md` | 验证完成后将 P13-7 标记为完成。 |

### 变更内容

调度器终端元数据现在在现有适配器类型之外，还保留了提供者分配详情。当存在重试和兜底引用时，它们也会被保留，因此恢复状态在混合提供者工作流中保持可审计。

回归覆盖验证了：

- 前端 Claude Code 任务等待后端 Codex 依赖项；
- 相同目标写锁与提供者无关；
- 不同的 Claude/Codex 目标可以与不同的提供者排队；
- 失败的混合提供者运行在调度器状态中保留提供者分配。

### 验证

| 命令 | 结果 |
|---|---|
| 针对性混合提供者调度器测试 | 通过：4 项测试。 |
| 完整调度器测试 | 通过：23 项测试。 |

---

## P13-6 跨提供者证据标准化

**日期：** 2026-05-27

### 修改的文件

| 文件 | 变更 |
|---|---|
| `openspec/changes/agenthub-p13-cross-provider-agent-coordination/tasks.md` | 为基于 TaskRun 的制品添加了一个共享的提供者证据标准化器。 |
| `apps/api/app/provider_evidence.py` | 在差异制品元数据和差异就绪事件中增加了提供者证据。 |
| `apps/api/app/diffs.py` | 在审查 frontend/backend 中增加了脚本化审查提供者证据和来源提供者证据。 |
| `apps/api/app/reviews.py` | 在预览制品元数据和预览就绪事件中增加了提供者证据。 |
| `apps/api/app/previews.py` | 在部署制品元数据和部署事件中增加了提供者证据。 |
| `apps/api/app/deployments.py` | 增加了对差异和审查证据元数据的覆盖。 |
| `apps/api/tests/test_previews.py` | 新增对预览证据元数据的覆盖。 |
| `apps/api/tests/test_deployments.py` | 新增对部署证据元数据的覆盖。 |
| `docs/project-state.md` | 记录了 P13-6 的行为和限制。 |
| `docs/change-log.md` | 记录了本次实现。 |
| `openspec/changes/agenthub-p13-cross-provider-agent-coordination/tasks.md` | 验证后标记 P13-6 为完成。 |

### 变更内容

Diff、脚本审查、预览和部署制品现在包含从 TaskRun 元数据派生的标准化提供者证据。该证据记录了任务运行 ID、运行状态、适配器类型、提供者 ID、提供者分配元数据、变更文件、相关日志、制品引用以及存在的 retry/fallback 引用。

脚本审查制品还记录了 `originProviderEvidence`，保留了产生被审查 diff 的提供者支持编码运行的身份，而不是将其隐藏在确定性审查适配器之后。

### 验证

| 命令 | 结果 |
|---|---|
| 定向 diff/review/preview/deploy 证据测试 | 通过：4 个测试。 |

---

## P13-5 提供者特定指令映射

**日期：** 2026-05-27

### 修改文件

| 文件 | 变更 |
|---|---|
| `apps/api/app/instruction_adapters/codex.py` | 在保留共享核心指令的同时，添加了 Codex 特定的指令包装器。 |
| `apps/api/app/instruction_adapters/claude_code.py` | 在保留共享核心指令的同时，添加了 Claude Code 特定的指令包装器。 |
| `apps/api/tests/test_task_runs.py` | 新增回归覆盖，验证 Codex 和 Claude Code 指令保留相同的规范契约、目标、交接、验证和护栏事实。 |
| `docs/project-state.md` | 记录了 P13-5 的行为和限制。 |
| `docs/change-log.md` | 记录了本次实现。 |
| `openspec/changes/agenthub-p13-cross-provider-agent-coordination/tasks.md` | 验证后标记 P13-5 为完成。 |

### 变更内容

Codex 和 Claude Code 指令适配器现在应用提供者特定的包装文本，同时保持共享角色指令和规范共享上下文不变。这使得提供者提示格式可以不同，而不会丢失共享的任务事实。

回归覆盖验证了两个提供者保留相同的契约 ID、frontend/backend 目标 ID、上游交接引用、已实现路由详情、验证期望和护栏。

### 验证

| 命令 | 结果 |
|---|---|
| 定向提供者指令映射测试 | 通过：2 个测试。 |
| 完整 TaskRun 测试 | 通过：52 个测试。 |

---

## P13-4 交接协议 v1

**日期：** 2026-05-27

### 修改文件

| 文件 | 变更 |
|---|---|
| `apps/api/app/handoffs.py` | 新增了感知提供者的交接元数据、基于 diff 的变更文件、已实现的 route/component 提示、审查警告和建议的后续范围。 |
| `apps/api/tests/test_task_runs.py` | 新增了前端到审查和审查到修复转换的交接协议覆盖、下游规范上下文和任务追踪可见性。 |
| `docs/project-state.md` | 记录了 P13-4 的行为和限制。 |
| `docs/change-log.md` | 记录了本次实现。 |
| `openspec/changes/agenthub-p13-cross-provider-agent-coordination/tasks.md` | 验证后标记 P13-4 为完成。 |

### 变更内容

交接制品现在携带感知提供者的元数据，用于跨提供者转换：

- `fromProviderId` / `fromAdapterType`；
- `toProviderId` / `toAdapterType`；
- 来自最新 diff 制品（如果可用）的变更文件；
- 已实现的路由和组件提示；
- 制品引用；
- 审查警告和建议的后续范围；
- 验证状态和风险说明。

下游会话上下文和规范共享上下文包含丰富的交接元数据，任务追踪通过现有制品导航公开相同的制品元数据。

### 验证

| 命令 | 结果 |
|---|---|
| 定向交接协议测试 | 通过：2 个测试。 |
| 完整 TaskRun 测试 | 通过：51 个测试。 |

---

## P13-3 规范上下文使用强制

**日期：** 2026-05-27

### 修改文件

| 文件 | 变更 |
|---|---|
| `apps/api/app/instruction_adapters/shared_sections.py` | 从过滤后的规范共享上下文（而非旧版会话上下文负载）渲染提供者可见的指令上下文。 |
| `apps/api/app/instruction_builder.py` | 在列出首选前端文件时使用规范安全路径，以便受保护的计划路径不会被复制到提供者指令中。 |
| `apps/api/tests/test_task_runs.py` | 新增了对规范共享上下文渲染、旧版上下文排除、受保护路径过滤和快照持久化的覆盖。 |
| `docs/project-state.md` | 记录了 P13-3 的行为和限制。 |
| `docs/change-log.md` | 记录了本次实现。 |
| `openspec/changes/agenthub-p13-cross-provider-agent-coordination/tasks.md` | 验证后标记 P13-3 为完成。 |

### 变更内容

CodexAdapter 和 ClaudeCodeAdapter 的 TaskRun 指令现在包含一个源自过滤后的 `Canonical Shared Context` JSON 部分。
`canonical_shared_context_v1` 合约。旧的 `legacyContext` 载荷不再渲染到提供者指令中。

前端角色指令现在从规范安全路径而非原始计划文件中推导首选文件列表，从而防止受保护的值（如依赖目录路径、主机绝对路径或包含机密的元数据）通过人类可读的指令体泄露。

TaskRun 元数据继续持久化 `canonicalContextSnapshot`，保留一份可供审计的记录，说明为提供者执行准备了哪些上下文。

### 验证

| 命令 | 结果 |
|---|---|
| 针对性的规范上下文指令测试 | 通过：3 个测试。 |
| 完整的 TaskRun 测试 | 通过：50 个测试。 |

---

## P13-2 感知提供者的代理配置文件

**日期：** 2026-05-26

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/api/app/agent_profiles.py` | 添加了支持的角色元数据，并使 AgentProfile adapter/provider 字段与 P13 提供者分配策略对齐。 |
| `apps/api/app/provider_assignments.py` | 添加了只读配置文件提供者分配解析，使用已配置的角色分配或内置提供者默认值。 |
| `apps/api/app/schemas.py` | 在 AgentProfile API 响应中添加了 `supportedRoles`。 |
| `apps/api/app/main.py` | 在工作区代理配置文件响应中返回了支持的角色。 |
| `apps/api/tests/test_planning.py` | 为感知提供者的配置文件和分配匹配的配置文件元数据添加了 API 覆盖。 |
| `apps/web/src/lib/api.ts` | 在 AgentProfile 客户端类型中添加了 `supportedRoles`。 |
| `apps/web/src/lib/api.test.ts` | 更新了配置文件 API 夹具覆盖范围，以包含感知提供者的元数据。 |
| `docs/project-state.md` | 记录了 P13-2 的行为和限制。 |
| `docs/change-log.md` | 记录了此实现。 |
| `openspec/changes/agenthub-p13-cross-provider-agent-coordination/tasks.md` | 验证后将 P13-2 标记为完成。 |

### 变更内容

AgentProfile 响应现在除了提供者 ID、适配器类型、支持的目标、支持的模式和安全标志之外，还公开了 `supportedRoles`。内置配置文件将当前角色代理映射到感知提供者的默认值，例如 `frontend -> local-codex-cli`、`backend -> local-codex-cli` 和 `qa/review -> local-scripted-review`。

当 `AGENTHUB_PROVIDER_ASSIGNMENT_MATRIX.roles` 配置了一个内置角色时，相应的 AgentProfile 会反映该已配置的 adapter/provider 选择。这使配置文件元数据与 P13-1 提供者分配矩阵保持兼容，而无需添加用户创建的自定义代理或更改执行调度行为。

### 验证

| 命令 | 结果 |
|---|---|
| 针对性的代理配置文件 API 测试 | 通过：2 个测试。 |
| 针对性的 Web API 测试 | 通过：39 个测试。 |

---

## P13-1 提供者分配矩阵

**日期：** 2026-05-26

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/api/app/provider_assignments.py` | 为角色默认值、目标覆盖、显式适配器选择以及旧版默认兜底元数据添加了提供者分配矩阵解析。 |
| `apps/api/app/task_runs.py` | 将 TaskRun 适配器选择路由到提供者分配解析，并在运行和状态事件上记录分配元数据。 |
| `apps/api/app/mission_trace.py` | 在任务追踪 TaskRun 条目中公开了提供者分配元数据。 |
| `apps/api/tests/test_task_runs.py` | 为前端、后端、审查、目标覆盖、旧版兜底、无效分配拒绝以及任务追踪可见性添加了提供者分配矩阵测试。 |
| `docs/project-state.md` | 记录了 P13-1 的行为和限制。 |
| `docs/change-log.md` | 记录了此实现。 |
| `openspec/changes/agenthub-p13-cross-provider-agent-coordination/tasks.md` | 在针对性验证后将 P13-1 标记为完成。 |

### 变更内容

P13-1 添加了一个显式且可审计的提供者分配基础。运行时配置可以通过 `AGENTHUB_PROVIDER_ASSIGNMENT_MATRIX.roles` 按角色分配提供者，并可以通过 `AGENTHUB_PROVIDER_ASSIGNMENT_MATRIX.targets` 按目标覆盖。特定于目标的分配优先于角色默认值。

TaskRun 现在在 `metricsJson` 中记录一个 `providerAssignment` 载荷，包含角色、适配器类型、提供者 ID、来源、目标 ID、支持的模式和兜底策略。任务追踪 TaskRun 条目公开相同的分配元数据。

现有的适配器选择保持兼容：当没有配置 P13 矩阵分配时，AgentHub 保留旧版 Agent 元数据和 `AGENTHUB_DEFAULT_CODE_ADAPTER` 行为。

### 验证

| 命令 | 结果 |
|---|---|
| 针对性的提供者分配测试 | 通过：5 个测试。 |
| 针对性的任务运行 / 调度器 / 规划测试 | 通过：92 个测试。 |

---

## P12-10 端到端演练与冻结审查

**日期：** 2026-05-26

### 修改的文件

| 文件 | 变更 |
|---|---|
| `docs/p12-freeze-review.md` | 添加了 P12 冻结证据、注意事项、验证说明和推荐标签。 |
| `docs/project-state.md` | 记录了 P12 冻结状态和证据 ID。 |
| `docs/change-log.md` | 记录了此冻结审查。 |
| `openspec/changes/agenthub-p12-platform-core-consolidation/tasks.md` | 验证后将 P12-10、非目标和验证标记为完成。 |
### 审查结果

P12 已准备好冻结，作为平台核心整合。

冻结预演验证了从新会话开始的整合本地演示路径，涵盖编排器规划、ScriptedMock 前端执行、差异对比、审查、交接、预览、本地暂存部署、后续修改、制品版本 v2、更新后的预览以及更新后的本地暂存部署。

### 验证

| 命令 | 结果 |
|---|---|
| P12 冻结预演 | 通过 |
| `pnpm check` | 通过 |
| `pnpm test` | 通过 |
| `pnpm demo:api:test` | 通过 |
| `git diff --check` | 通过 |
| `openspec validate agenthub-p12-platform-core-consolidation --strict` | 通过 |

推荐的冻结标签：
`p12-platform-core-consolidation-freeze`。

---

## 仓库卫生

**日期：** 2026-05-25

### 修改的文件

| 文件 | 变更 |
|---|---|
| `.gitignore` | 添加了公共文档允许列表规则，并忽略了内部规划、OpenSpec、研究、PDF、Office 和演示证据文档。 |
| `docs/change-log.md` | 记录了仓库卫生清理。 |

### 变更内容

仓库现在默认保留常见的公共项目文档可见，同时忽略内部规划和研究文档。这使未来的 GitHub 推送专注于源代码、配置、测试和公共项目入口点。

---

## P11-6 端到端预演与冻结审查

**日期：** 2026-05-25

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/api/app/deployments.py` | 修复了本地静态服务，使其使用 `sys.executable` 而不是假设主机上存在 `python`。 |
| `apps/api/tests/test_deployments.py` | 为静态服务器解释器命令添加了回归测试覆盖。 |
| `docs/p11-freeze-review.md` | 添加了 P11 冻结证据、注意事项、验证说明和推荐标签。 |
| `docs/project-state.md` | 记录了 P11-6 冻结结果和证据 ID。 |
| `docs/change-log.md` | 记录了本次冻结审查。 |
| `openspec/changes/agenthub-p11-real-staging-deploy-provider/tasks.md` | 验证后将 P11-6、非目标和验证标记为完成。 |

### 审查结果

P11 已准备好冻结，作为真实暂存部署提供者。

冻结预演对内置的 `demo-frontend` 目标使用了真实的本地暂存部署。它运行了 `pnpm build`，在本地 URL 上提供构建后的 `dist` 目录，验证了该 URL 返回了 HTML，并记录了部署日志、状态历史、目标元数据和源制品引用。

### 验证

| 命令 | 结果 |
|---|---|
| 真实本地暂存预演 | 通过 |
| 目标部署回归测试 | 通过 |
| `pnpm check` | 通过 |
| `pnpm test` | 通过 |
| `git diff --check` | 通过 |
| `openspec validate agenthub-p11-real-staging-deploy-provider --strict` | 通过 |

推荐的冻结标签：
`p11-real-staging-deploy-provider-freeze`。

---

## P11-5 部署门控

**日期：** 2026-05-25

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/api/app/deployments.py` | 为生产请求、预览健康检查、审查失败和目标策略违规添加了暂存部署门控。 |
| `apps/api/app/schemas.py` | 添加了部署环境请求字段。 |
| `apps/api/app/main.py` | 将请求的部署环境传递给 `DeployService`。 |
| `apps/api/tests/test_deployments.py` | 为审查失败、预览不健康、目标策略违规、生产拒绝和成功暂存路径添加了部署门控测试。 |
| `docs/project-state.md` | 记录了 P11-5 的行为和限制。 |
| `docs/change-log.md` | 记录了本次实现。 |
| `openspec/changes/agenthub-p11-real-staging-deploy-provider/tasks.md` | 在目标验证后将 P11-5 标记为完成。 |

### 变更内容

P11-5 在本地暂存提供者运行之前添加了保守的暂存部署门控。暂存部署现在拒绝 production/prod 环境请求、失败或不健康的预览先决条件、失败的最新审查制品，以及目标注册表路径策略之外的已更改文件。

模拟部署仍可用于现有的演示和兜底路径。

### 验证

| 命令 | 结果 |
|---|---|
| 目标部署测试 | 通过：17 个测试。 |

---

## P11-4 部署日志与状态制品

**日期：** 2026-05-25

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/api/app/deployments.py` | 添加了部署源元数据、日志、状态历史、失败部署制品持久化以及扩展的部署响应映射。 |
| `apps/api/app/main.py` | 在部署响应中返回了部署提供者类型、target/source 引用、日志和状态历史。 |
| `apps/api/app/schemas.py` | 为部署证据和状态历史添加了部署响应字段。 |
| `apps/api/tests/test_deployments.py` | 添加了部署证据、失败制品和 API 响应覆盖。 |
| `apps/web/src/lib/api.ts` | 为前端 API 类型添加了部署证据字段。 |
| `apps/web/src/lib/api.test.ts` | 更新了部署夹具负载覆盖。 |
| `apps/web/src/components/deploy-card.tsx` | 在部署卡片中渲染了 target/source 引用、状态历史和日志。 |
| `apps/web/src/components/deploy-card.test.tsx` | 添加了部署卡片证据断言。 |
| `apps/web/src/components/__fixtures__/sample-deployment.ts` | 添加了示例部署证据元数据。 |
| `docs/project-state.md` | 记录了 P11-4 的行为和限制。 |
| `docs/change-log.md` | 记录了本次实现。 |
| `openspec/changes/agenthub-p11-real-staging-deploy-provider/tasks.md` | 在定向验证后标记 P11-4 完成。 |

### 变更内容

P11-4 使部署证据可见且持久。部署制品和 API 响应现在包含目标 ID、提供者类型、源 preview/diff/review 引用、日志和状态历史。部署卡片内联渲染这些细节，因此暂存部署可以像其他 AgentHub 制品一样被审查。

本地暂存提供者失败时，现在会持久化带有诊断日志的失败部署制品，而不是在异常后消失。未知提供者仍会在制品创建前失败。

### 验证

| 命令 | 结果 |
|---|---|
| 定向部署测试 | 通过：13 个测试。 |
| 定向部署 card/frontend 测试 | 通过：37 个测试。 |

---

## P11-3 本地暂存部署提供者

**日期：** 2026-05-25

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/api/app/deployments.py` | 添加了 `local_staging` 提供者、构建运行器、静态目录服务器运行器、target/worktree 解析、健康检查以及提供者选择的部署创建。 |
| `apps/api/app/main.py` | 允许 `POST /previews/{previewId}/deploy` 接受 `providerId`，同时保留 mock 作为默认值。 |
| `apps/api/app/schemas.py` | 添加了部署创建请求模式。 |
| `apps/api/app/target_registry.py` | 使演示前端构建命令与目标根目录执行对齐。 |
| `apps/api/tests/test_deployments.py` | 添加了本地暂存成功、构建失败、缺少输出和 API 提供者选择测试。 |
| `apps/api/tests/test_target_registry.py` | 更新了部署配置断言，以支持目标根目录构建执行。 |
| `docs/project-state.md` | 记录了 P11-3 的行为和限制。 |
| `docs/change-log.md` | 记录了本次实现。 |
| `openspec/changes/agenthub-p11-real-staging-deploy-provider/tasks.md` | 在定向验证后标记 P11-3 完成。 |

### 变更内容

P11-3 添加了一个真实的本地暂存提供者路径。它从目标注册表读取部署配置，运行目标构建命令，检查配置的输出目录，启动本地静态服务器，执行 URL 健康检查，并在 URL 就绪时记录暂存部署。

API 仍与现有 mock 部署调用者兼容，现在接受 `providerId: local_staging` 用于暂存部署请求。确定性 TestClient 冒烟覆盖验证了本地提供者选择，无需启动长期运行的外部服务。

### 验证

| 命令 | 结果 |
|---|---|
| 定向部署 / 目标注册表测试 | 通过：24 个测试。 |

---

## P11-2 目标感知的部署配置

**日期：** 2026-05-25

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/api/app/target_registry.py` | 为目标项目添加了部署元数据，并为可部署的前端目标添加了 `resolve_deploy_config()`。 |
| `apps/api/app/models.py` | 为外部目标添加了部署元数据字段，用于暂存输出、暂存服务命令和部署提供者 ID。 |
| `apps/api/app/external_workspaces.py` | 接受并持久化了外部目标部署提供者元数据。 |
| `apps/api/app/schemas.py` | 在外部目标和目标项目 request/response 模式中暴露了部署元数据。 |
| `apps/api/app/main.py` | 通过目标注册表和外部目标 API 返回部署元数据。 |
| `apps/api/tests/test_target_registry.py` | 添加了部署配置解析和不可部署目标测试。 |
| `apps/api/tests/test_external_workspaces.py` | 添加了外部目标部署元数据 API 覆盖。 |
| `docs/project-state.md` | 记录了 P11-2 的行为和限制。 |
| `docs/change-log.md` | 记录了本次实现。 |
| `openspec/changes/agenthub-p11-real-staging-deploy-provider/tasks.md` | 在定向验证后标记 P11-2 完成。 |

### 变更内容

P11-2 使目标注册表成为部署配置的单一事实来源。可部署的前端目标现在可以暴露构建命令、暂存输出目录、暂存服务命令和允许的部署提供者 ID。内置演示前端宣传 mock 和本地暂存提供者的可用性，而 backend/platform 目标通过 `resolve_deploy_config()` 诚实地失败。

外部前端目标可以通过注册和工作区目标 API 携带部署元数据。P11-2 尚未执行部署命令。

### 验证

| 命令 | 结果 |
|---|---|
| 定向目标注册表 / 外部工作区测试 | 通过：16 个测试。 |

---

## P11-1 部署提供者抽象

**日期：** 2026-05-25

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/api/app/deployments.py` | 添加了部署提供者结果契约、提供者选择、mock 提供者兼容路径和 failed/unknown 提供者处理。 |
| `apps/api/tests/test_deployments.py` | 添加了部署提供者抽象测试，涵盖元数据、提供者选择、未知提供者拒绝、失败提供者结果和 mock 兼容性。 |
| `docs/project-state.md` | 记录了 P11-1 的行为与限制。 |
| `docs/change-log.md` | 记录了本次实现。 |
| `openspec/changes/agenthub-p11-real-staging-deploy-provider/tasks.md` | 在定向验证后将 P11-1 标记为完成。 |

### 变更内容

P11-1 引入了首个部署提供者抽象，但未改变当前运行时部署语义。现有的模拟部署行为仍可通过 `create_mock_deployment()` 使用，而较新的 `create_deployment()` 路径则通过 ID 选择提供者，并在部署制品中记录标准化的提供者元数据。

未知的提供者会在制品创建前被拒绝。失败的提供者结果会被如实报告，且不会创建就绪的部署制品。

### 验证

| 命令 | 结果 |
|---|---|
| 定向部署测试 | 通过：9 个测试。 |

---

## P10-8 健壮性预演与冻结审查

**日期：** 2026-05-24

### 修改的文件

| 文件 | 变更 |
|---|---|
| `docs/p10-freeze-review.md` | 添加了 P10 冻结证据、验证说明、注意事项及推荐标签。 |
| `docs/project-state.md` | 记录了 P10-8 冻结结果及推荐标签。 |
| `docs/change-log.md` | 记录了本次冻结审查。 |
| `openspec/changes/agenthub-p10-scheduler-robustness-conflict-recovery/tasks.md` | 在验证后将 P10-8 标记为完成。 |

### 审查结果

P10 已准备好冻结为“调度器健壮性与冲突恢复”。

本次冻结审查使用了确定性本地测试及现有的 P6/P7/P8/P9 基线覆盖率。未运行全新的真实 Claude/Codex 变异测试。

### 验证

| 命令 | 结果 |
|---|---|
| 定向 P10 预演测试 | 通过 |
| `pnpm check` | 通过 |
| `pnpm test` | 通过 |
| `git diff --check` | 通过 |
| `openspec validate agenthub-p10-scheduler-robustness-conflict-recovery --strict` | 通过 |

推荐冻结标签：
`p10-scheduler-robustness-conflict-recovery-freeze`。

---

## P10-7 恢复操作

**日期：** 2026-05-24

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/api/app/recovery.py` | 为过期任务失败、过期锁释放、重试及下游 stop/resume. 添加了可审计的恢复操作。 |
| `apps/api/app/task_runs.py` | 允许恢复操作请求检查点重试模式，同时保留重试安全检查。 |
| `apps/api/tests/test_recovery.py` | 添加了恢复操作审计及行为测试。 |
| `docs/project-state.md` | 记录了 P10-7 的行为与限制。 |
| `docs/change-log.md` | 记录了本次实现。 |
| `openspec/changes/agenthub-p10-scheduler-robustness-conflict-recovery/tasks.md` | 在验证后将 P10-7 标记为完成。 |

### 变更内容

P10-7 添加了显式的服务级恢复操作。过期任务失败、过期锁释放、从当前状态重试、从检查点重试、下游停止及下游恢复现在都会产生 `recovery.action` 审计事件。恢复操作复用了 P10 的心跳、过期锁、检查点、重试及调度器就绪状态保护机制，而非添加自动的 merge/reset 行为。

### 验证

| 命令 | 结果 |
|---|---|
| 定向恢复操作测试 | 通过：4 个测试。 |
| 定向 recovery/scheduler/task-run 回归测试 | 通过：61 个测试。 |
| `pnpm check` | 通过 |
| `pnpm test` | 通过 |
| `git diff --check` | 通过 |
| `openspec validate agenthub-p10-scheduler-robustness-conflict-recovery --strict` | 通过 |

---

## P10-6 冲突检测

**日期：** 2026-05-24

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/api/app/scheduler.py` | 在调度器层面添加了文件重叠、脏工作区及合约漂移冲突检测。 |
| `apps/api/app/task_runs.py` | 在创建 TaskRun 前使用完整的调度器就绪状态检查，使冲突能够阻止执行。 |
| `apps/api/tests/test_scheduler.py` | 添加了文件重叠、脏工作区及合约漂移冲突测试。 |
| `apps/api/tests/test_task_runs.py` | 调整了检查点测试夹具，以避免因冲突测试覆盖而故意污染被拒绝的文件。 |
| `docs/project-state.md` | 记录了 P10-6 的行为与限制。 |
| `docs/change-log.md` | 记录了本次实现。 |
| `openspec/changes/agenthub-p10-scheduler-robustness-conflict-recovery/tasks.md` | 在验证后将 P10-6 标记为完成。 |

### 变更内容

调度器就绪状态现在会在写入执行前阻止常见冲突：未排序的重叠计划文件、计划安全文件之外的脏工作区文件，以及 stale/mismatched 合约上下文。冲突会记录在任务调度器元数据中，且不会自动合并。

### 验证

| 命令 | 结果 |
|---|---|
| 定向冲突检测测试 | 通过：3 个测试。 |
| 定向 scheduler/task-run 回归测试 | 通过：57 个测试。 |
| `pnpm check` | 通过 |
| `pnpm test` | 通过 |
| `git diff --check` | 通过 |
| `openspec validate agenthub-p10-scheduler-robustness-conflict-recovery --strict` | 通过 |

---

## P10-5 故障传播加固

**日期：** 2026-05-24

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/api/app/previews.py` | 将预览创建的条件限定为 TaskRun 已完成且依赖项也已完成。 |
| `apps/api/app/deployments.py` | 在预览功能后，对已完成的 TaskRun 及其已完成的依赖项进行门控模拟部署。 |
| `apps/api/tests/test_previews.py` | 添加了失败的 TaskRun 和失败的依赖项预览拒绝测试。 |
| `apps/api/tests/test_deployments.py` | 添加了失败的 TaskRun 和失败的依赖项模拟部署拒绝测试。 |
| `docs/project-state.md` | 记录了 P10-5 的行为和限制。 |
| `docs/change-log.md` | 记录了本次实现。 |
| `openspec/changes/agenthub-p10-scheduler-robustness-conflict-recovery/tasks.md` | 验证后将 P10-5 标记为完成。 |

### 变更内容

预览和模拟部署不再在前置条件失败或不完整时继续执行。手动预览现在要求 TaskRun 及其依赖项均已完成。模拟部署保留了其健康预览的要求，并且还要求其支撑的 TaskRun 和依赖项均已完成。

### 验证

| 命令 | 结果 |
|---|---|
| 针对性的 preview/deploy 前置条件拒绝测试 | 通过：4 个测试。 |
| 针对性的 scheduler/preview/deploy/fallback 恢复测试 | 通过：29 个测试。 |
| `pnpm check` | 通过 |
| `pnpm test` | 通过 |
| `git diff --check` | 通过 |
| `openspec validate agenthub-p10-scheduler-robustness-conflict-recovery --strict` | 通过 |

---

## P10-4 重试幂等性

**日期：** 2026-05-24

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/api/app/task_runs.py` | 添加了重试元数据、脏工作区重试安全检查以及不安全重试的阻止。 |
| `apps/api/tests/test_task_runs.py` | 添加了重试幂等性元数据以及不安全的脏工作区外部重试测试。 |
| `docs/project-state.md` | 记录了 P10-4 的行为和限制。 |
| `docs/change-log.md` | 记录了本次实现。 |
| `openspec/changes/agenthub-p10-scheduler-robustness-conflict-recovery/tasks.md` | 验证后将 P10-4 标记为完成。 |

### 变更内容

重试现在会记录 `previousRunId`、失败摘要、重试模式、检查点引用以及脏工作区决策。当当前脏文件超出先前检查点或计划的安全路径范围时，自动重试将被阻止，从而防止盲目重试进入外部项目的本地编辑。

### 验证

| 命令 | 结果 |
|---|---|
| 针对性的重试幂等性测试 | 通过：2 个测试。 |
| 针对性的任务运行 retry/checkpoint/liveness 测试 | 通过：10 个测试。 |
| `pnpm check` | 通过 |
| `pnpm test` | 通过 |
| `git diff --check` | 通过 |
| `openspec validate agenthub-p10-scheduler-robustness-conflict-recovery --strict` | 通过 |

---

## P10-3 运行前快照 / 检查点

**日期：** 2026-05-24

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/api/app/task_runs.py` | 为写入型 TaskRun 添加了运行前检查点创建和检查点审计事件。 |
| `apps/api/tests/test_task_runs.py` | 添加了演示和外部目标的检查点覆盖。 |
| `docs/project-state.md` | 记录了 P10-3 的行为和限制。 |
| `docs/change-log.md` | 记录了本次实现。 |
| `openspec/changes/agenthub-p10-scheduler-robustness-conflict-recovery/tasks.md` | 验证后将 P10-3 标记为完成。 |

### 变更内容

写入型 TaskRun 现在在执行前存储 `metrics_json.preRunCheckpoint` 并发出 `task.checkpoint.created`。检查点包括目标元数据、目标注册表路径策略、可用的基础提交、限定的脏文件、计划文件、合约 ID/hash 以及创建时间。外部目标使用其注册的根目录和路径策略。

### 验证

| 命令 | 结果 |
|---|---|
| 针对性的检查点测试 | 通过：2 个测试。 |
| 针对性的 task-run/scheduler 存活性和锁测试 | 通过：16 个测试。 |
| `pnpm check` | 通过 |
| `pnpm test` | 通过 |
| `git diff --check` | 通过 |
| `openspec validate agenthub-p10-scheduler-robustness-conflict-recovery --strict` | 通过 |

---

## P10-2 过期目标锁清理

**日期：** 2026-05-24

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/api/app/scheduler.py` | 为过期的写锁持有者 TaskRun 添加了过期目标锁清理，包含审计事件和调度器刷新。 |
| `apps/api/tests/test_scheduler.py` | 添加了覆盖测试，确保活跃持有者不会被释放，而过期持有者会释放派生目标锁。 |
| `docs/project-state.md` | 记录了 P10-2 的行为和限制。 |
| `docs/change-log.md` | 记录了本次实现。 |
| `openspec/changes/agenthub-p10-scheduler-robustness-conflict-recovery/tasks.md` | 验证后将 P10-2 标记为完成。 |

### 变更内容

P10-2 保留了现有的 P8 派生目标锁模型，但增加了一个显式的清理路径：

- 具有有效租约的活跃 TaskRun 仍然是锁持有者；
- 过期的写锁持有者 TaskRun 可以被标记为过期并失败；
- 清理操作会写入 `target_lock.released` 事件，包含目标、持有者、锁模式、租约、释放时间戳和原因；
- 在清理过期持有者后，等待中的任务会被重新评估。

### 验证

| 命令 | 结果 |
|---|---|
| 针对性的过期锁清理测试 | 通过：2 个测试。 |
| 针对性的 scheduler/task-run 锁和存活测试 | 通过：14 个测试。 |
| `pnpm check` | 通过 |
| `pnpm test` | 通过 |
| `git diff --check` | 通过 |
| `openspec validate agenthub-p10-scheduler-robustness-conflict-recovery --strict` | 通过 |

---
## P10-1 TaskRun 心跳与租约

**日期:** 2026-05-24

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/api/app/models.py` | 新增 TaskRun 存活字段，用于运行器标识、心跳、租约过期和过期元数据。 |
| `apps/api/app/db.py` | 新增 TaskRun heartbeat/lease/stale 列的 SQLite 回填。 |
| `apps/api/app/task_runs.py` | 新增运行器租约初始化、心跳刷新、过期运行检测和诚实的过期失败标记。 |
| `apps/api/app/schemas.py` | 在 API 响应模式中暴露 TaskRun 存活元数据。 |
| `apps/api/app/main.py` | 在 TaskRun API 响应中包含存活元数据。 |
| `apps/api/tests/test_task_runs.py` | 新增心跳、租约和过期检测测试。 |
| `apps/api/tests/test_models.py` | 更新模型边界和响应别名测试以支持存活字段。 |
| `docs/project-state.md` | 记录 P10-1 行为和限制。 |
| `docs/change-log.md` | 记录本次实现。 |
| `openspec/changes/agenthub-p10-scheduler-robustness-conflict-recovery/tasks.md` | 验证后标记 P10-1 完成。 |

### 变更内容

TaskRun 现在拥有本地运行器存活元数据：

- 新运行获得 `runner_id`、`last_heartbeat_at` 和 `lease_expires_at`；
- 活跃运行可以刷新心跳和租约元数据；
- 过期的活跃租约可以用 `TASK_RUN_STALE` 标记为失败；
- 过期状态转换会写入审计事件，且不声明适配器成功。

### 验证

| 命令 | 结果 |
|---|---|
| 定向 heartbeat/stale 测试 | 通过：4 个测试。 |
| 定向 model/task-run 测试 | 通过：6 个测试。 |
| `pnpm check` | 通过 |
| `pnpm test` | 通过 |
| `git diff --check` | 通过 |
| `openspec validate agenthub-p10-scheduler-robustness-conflict-recovery --strict` | 通过 |

---

## P9-8 外部项目端到端预演与冻结审查

**日期:** 2026-05-24

### 修改的文件

| 文件 | 变更 |
|---|---|
| `docs/p9-freeze-review.md` | 新增 P9 冻结证据、预演 ID、验证说明、注意事项和推荐标签。 |
| `docs/project-state.md` | 记录 P9-8 冻结结果和推荐标签。 |
| `docs/change-log.md` | 记录本次冻结审查。 |
| `openspec/changes/agenthub-p9-external-project-workspace-mode/tasks.md` | 验证后标记 P9-8 完成。 |

### 审查结果

P9 已准备好作为外部项目工作区模式冻结。

P9 未运行全新的真实 Claude/Codex 变更。它使用了一个临时的本地
Vite 风格外部项目，并通过受控服务调用来验证分析、
注册、目标选择、外部 task/run 路由、差异、命令
证据和审查策略。

### P9 预演证据

| 字段 | 值 |
|---|---|
| 示例根目录 | `/tmp/agenthub-p9-external-sample` |
| 会话 ID | `09977dc0-1eac-49f6-ae78-cb7ae7aa9ccc` |
| 目标 ID | `external-p9-sample` |
| 分析状态 / 类型 | `ready`, `vite-react` |
| 任务 / 运行 | `ce8fe3de-6969-4273-84e9-274ab440f39b`, `1d6d2916-b179-4bb7-ad7a-642733dfd175` |
| 适配器类型 | `scripted_mock` 受控预演 |
| 变更的文件 | `src/App.tsx` |
| 差异制品 | `7bf6efa3-289b-4cb8-9644-6ca6e283b230` |
| 命令证据 | `c6d581bf-e80a-4fb9-bb21-f0db1cb9ff4d`, `b01ccc78-b3d4-44fc-b758-4c9558d2f594`, `9a256f14-fe1f-4e4b-9dc7-78c4402edd01` |
| 审查制品 / 状态 | `383e7822-0145-4950-9bd1-b3dffb170b36`, `passed` |

### 验证

| 命令 | 结果 |
|---|---|
| P9 临时外部预演 | 通过 |
| `pnpm check` | 通过 |
| `pnpm test` | 通过 |
| `pnpm demo:api:test` | 通过 |
| `git diff --check` | 通过 |
| `openspec validate agenthub-p9-external-project-workspace-mode --strict` | 通过 |

推荐冻结标签：
`p9-external-project-workspace-mode-freeze`。

---

## P9-7 外部项目审查

**日期:** 2026-05-24

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/api/app/reviews.py` | 新增外部目标 allowed/denied 路径审查和命令证据发现。 |
| `apps/api/tests/test_external_reviews.py` | 新增拒绝路径、超出允许路径、证据失败、证据缺失和完全通过的审查测试。 |
| `docs/project-state.md` | 记录 P9-7 行为和限制。 |
| `docs/change-log.md` | 记录本次实现。 |
| `openspec/changes/agenthub-p9-external-project-workspace-mode/tasks.md` | 验证后标记 P9-7 完成。 |

### 变更内容

P9-7 使外部审查具备策略感知能力：

- 拒绝路径的编辑会明确失败或发出警告；
- 超出允许路径的编辑会产生发现；
- 缺失或失败的已配置 check/test/build 证据会被诚实报告；
- 通过证据的干净外部目标差异可以通过审查。

### 验证

| 命令 | 结果 |
|---|---|
| 定向外部 review/evidence/diff 测试 | 通过：13 个测试。 |
| `pnpm check` | 通过 |
| `pnpm test` | 通过 |
| `git diff --check` | 通过 |
| `openspec validate agenthub-p9-external-project-workspace-mode --strict` | 通过 |

---

## P9-6 外部证据管道

**日期:** 2026-05-24

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/api/app/diffs.py` | 将外部差异收集范围限定为目标允许路径，同时排除 denied/dependency 路径。 |
| `apps/api/app/external_evidence.py` | 为 check/test/build 输出添加了命令证据制品记录。 |
| `apps/api/app/schemas.py` | 添加了命令证据 request/response 模式。 |
| `apps/api/app/main.py` | 为命令证据制品添加了 create/list API 端点。 |
| `apps/api/app/context_pack.py` | 将会话上下文包中添加了最新命令证据元数据。 |
| `apps/api/tests/test_diffs.py` | 添加了外部差异路径策略覆盖。 |
| `apps/api/tests/test_external_evidence.py` | 为通过和失败的输出添加了命令证据 service/API 测试。 |
| `docs/project-state.md` | 记录了 P9-6 的行为和限制。 |
| `docs/change-log.md` | 记录了本次实现。 |
| `openspec/changes/agenthub-p9-external-project-workspace-mode/tasks.md` | 验证后将 P9-6 标记为完成。 |

### 变更内容

P9-6 增加了基于能力的外部证据：

- 外部差异遵循目标路径策略；
- check/test/build 命令输出可作为 `command_evidence` 制品存储；
- 失败的命令退出仍保留为失败证据；
- 外部目标的预览保持可选。

### 验证

| 命令 | 结果 |
|---|---|
| 定向外部 evidence/diff 测试 | 通过：41 个测试。 |
| `pnpm check` | 通过 |
| `pnpm test` | 通过 |
| `git diff --check` | 通过 |
| `openspec validate agenthub-p9-external-project-workspace-mode --strict` | 通过 |

---

## P9-5 外部项目任务执行

**日期：** 2026-05-24

### 修改文件

| 文件 | 变更 |
|---|---|
| `apps/api/app/models.py` | 添加了会话活跃 frontend/backend 目标 ID。 |
| `apps/api/app/db.py` | 为现有本地会话表添加了 SQLite 列回填。 |
| `apps/api/app/schemas.py` | 添加了活跃目标字段和会话目标选择请求模式。 |
| `apps/api/app/main.py` | 添加了会话目标选择 API 和外部前端自动启动安全检查。 |
| `apps/api/app/planning.py` | 将直接提及和受限的 Orchestrator 前端请求路由到选定的外部目标。 |
| `apps/api/app/task_runs.py` | 对外部目标任务使用外部目标根目录作为 TaskRun 工作树路径。 |
| `apps/api/tests/test_external_workspaces.py` | 添加了会话目标选择测试。 |
| `apps/api/tests/test_planning.py` | 添加了外部直接前端和 Orchestrator 自动启动路由测试。 |
| `apps/api/tests/test_task_runs.py` | 添加了外部 TaskRun 工作树路径断言。 |
| `apps/api/tests/test_models.py` | 更新了活跃目标字段的模型边界预期。 |
| `docs/project-state.md` | 记录了 P9-5 的行为和限制。 |
| `docs/change-log.md` | 记录了本次实现。 |
| `openspec/changes/agenthub-p9-external-project-workspace-mode/tasks.md` | 验证后将 P9-5 标记为完成。 |

### 变更内容

P9-5 为已注册的外部目标提供了可执行的任务路径：

- 会话可以选择活跃的外部 frontend/backend 目标；
- 选定后，直接分配任务将目标指向活跃的外部项目；
- 受限的无提及 UI 请求可由 Orchestrator 路由到活跃的外部前端目标，并通过 TaskRun 自动启动；
- TaskRun 执行请求使用外部目标根目录作为工作树路径；
- 不支持的广泛请求将被拒绝，而非静默执行。

### 验证

| 命令 | 结果 |
|---|---|
| 定向外部 execution/routing 测试 | 通过：64 个测试。 |
| `pnpm check` | 通过 |
| `pnpm test` | 通过 |
| `git diff --check` | 通过 |
| `openspec validate agenthub-p9-external-project-workspace-mode --strict` | 通过 |

---

## P9-4 外部目标指令构建器

**日期：** 2026-05-24

### 修改文件

| 文件 | 变更 |
|---|---|
| `apps/api/app/instruction_builder.py` | 使用已注册的目标元数据和配置的命令证据，添加了外部 frontend/backend/review 指令主体。 |
| `apps/api/tests/test_task_runs.py` | 添加了外部前端、后端和审查指令覆盖。 |
| `docs/project-state.md` | 记录了 P9-4 的行为和限制。 |
| `docs/change-log.md` | 记录了本次实现。 |
| `openspec/changes/agenthub-p9-external-project-workspace-mode/tasks.md` | 验证后将 P9-4 标记为完成。 |

### 变更内容

P9-4 使角色指令对已注册的外部项目具有目标感知能力：

- frontend/backend 指令不再将外部目标简化为演示应用路径；
- 包含目标根目录、允许路径、拒绝路径、项目类型、包管理器、检测到的框架以及配置的验证命令；
- 审查指令保持面向阅读，并强调命令证据的真实性；
- 内置演示指令得以保留。

### 验证

| 命令 | 结果 |
|---|---|
| 定向 task-run/instruction 测试 | 通过：44 个测试。 |
| `pnpm check` | 通过 |
| `pnpm test` | 通过 |
| `git diff --check` | 通过 |
| `openspec validate agenthub-p9-external-project-workspace-mode --strict` | 通过 |

---

## P9-3 外部目标注册表集成

**日期：** 2026-05-24

### 修改文件

| 文件 | 变更 |
|---|---|
| `apps/api/app/target_registry.py` | 添加了工作区感知的合并注册表读取，以及外部目标到 `TargetProject` 的映射。 |
| `apps/api/app/main.py` | 新增合并工作区目标列表 API。 |
| `apps/api/app/schemas.py` | 新增目标项目响应模式。 |
| `apps/api/app/context_pack.py` | 将外部 `targetId` 元数据解析为会话上下文包。 |
| `targetId` | 允许指令生成使用上下文包中的目标元数据。 |
| `apps/api/app/instruction_builder.py` | 使目标写锁能够验证已注册的外部目标。 |
| `apps/api/app/scheduler.py` | 新增合并注册表与外部 backend/frontend 映射测试。 |
| `apps/api/tests/test_target_registry.py` | 新增合并目标 API 覆盖测试。 |
| `apps/api/tests/test_external_workspaces.py` | 新增外部目标写锁覆盖测试。 |
| `apps/api/tests/test_scheduler.py` | 新增上下文包到指令的外部目标覆盖测试。 |
| `apps/api/tests/test_task_runs.py` | 记录 P9-3 行为与限制。 |
| `docs/project-state.md` | 记录本次实现。 |
| `docs/change-log.md` | 验证完成后将 P9-3 标记为完成。 |

### 变更内容

P9-3 将已注册的外部目标集成到 AgentHub 现有的目标元数据路径中：

- 合并注册表读取包含内置目标和外部目标；
- 外部目标以与内置目标相同的结构携带路径策略和命令元数据；
- 上下文包和角色指令可引用外部目标元数据；
- 调度器目标锁适用于已注册的外部目标 ID。

### 验证

| 命令 | 结果 |
|---|---|
| 定向 registry/scheduler/task-run 测试 | 通过：56 个测试。 |
| `pnpm check` | 通过 |
| `pnpm test` | 通过 |
| `git diff --check` | 通过 |
| `openspec validate agenthub-p9-external-project-workspace-mode --strict` | 通过 |

---

## P9-2 项目分析器

**日期：** 2026-05-24

### 修改文件

| 文件 | 变更 |
|---|---|
| `apps/api/app/project_analyzer.py` | 新增只读分析器，用于处理常见 JS/Python 项目结构、安全路径推断、命令推断、拒绝路径默认值及不确定性状态。 |
| `apps/api/app/schemas.py` | 新增外部项目分析 request/response 模式。 |
| `apps/api/app/main.py` | 新增工作区作用域的外部目标分析 API。 |
| `apps/api/tests/test_project_analyzer.py` | 新增 Vite React、Next.js、FastAPI、Node API、Python 包、未知项目及 API 响应测试。 |
| `docs/project-state.md` | 记录 P9-2 行为与限制。 |
| `docs/change-log.md` | 记录本次实现。 |
| `openspec/changes/agenthub-p9-external-project-workspace-mode/tasks.md` | 验证完成后将 P9-2 标记为完成。 |

### 变更内容

P9-2 在不授予执行权限的情况下添加项目分析功能：

- 分析 `package.json`、锁文件、Vite/Next 配置、Python 项目文件、FastAPI 入口点及 source/test 目录；
- 推断项目类型、包管理器、检测到的框架、允许路径、拒绝路径及命令候选；
- 对未知或不完整的项目返回带有警告的 `needs_confirmation`；
- 从不安装依赖项或运行任意命令。

### 验证

| 命令 | 结果 |
|---|---|
| 定向分析器测试 | 通过：11 个测试。 |
| `pnpm check` | 通过 |
| `pnpm test` | 通过 |
| `git diff --check` | 通过 |
| `openspec validate agenthub-p9-external-project-workspace-mode --strict` | 通过 |

---

## P9-1 外部工作区注册

**日期：** 2026-05-24

### 修改文件

| 文件 | 变更 |
|---|---|
| `apps/api/app/models.py` | 新增持久化 `ExternalProjectTarget` 模型，用于外部工作区目标注册。 |
| `apps/api/app/external_workspaces.py` | 新增注册服务、root/path 验证、拒绝路径默认值及 list/read 辅助函数。 |
| `apps/api/app/schemas.py` | 新增外部目标创建与响应模式。 |
| `apps/api/app/main.py` | 新增工作区作用域的 create/list/read API，用于外部目标。 |
| `apps/api/tests/test_external_workspaces.py` | 新增注册、不安全根目录、有界路径及内置注册表回归测试。 |
| `apps/api/tests/test_models.py` | 更新模型边界预期，以适配新的外部目标表。 |
| `docs/project-state.md` | 记录 P9-1 行为与限制。 |
| `docs/change-log.md` | 记录本次实现。 |
| `openspec/changes/agenthub-p9-external-project-workspace-mode/tasks.md` | 验证完成后将 P9-1 标记为完成。 |

### 变更内容

P9-1 在不改变执行语义的情况下添加外部工作区注册层：

- 本地外部项目根目录可注册为工作区作用域的外部目标；
- 注册存储目标元数据、命令、包管理器、检测到的框架、允许路径及拒绝路径；
- 不安全的宽泛根目录和无界允许路径将被拒绝；
- 内置 P7/P8 目标注册表条目保持不变。

### 验证

| 命令 | 结果 |
|---|---|
| 定向外部工作区测试 | 通过：18 个测试。 |
| `pnpm check` | 通过 |
| `pnpm test` | 通过 |
| `git diff --check` | 通过 |
| `openspec validate agenthub-p9-external-project-workspace-mode --strict` | 通过 |

---

## P8-6 P8 端到端演练与冻结审查

**日期：** 2026-05-24
### 修改的文件

| 文件 | 变更 |
|---|---|
| `docs/p8-freeze-review.md` | 添加了 P8 冻结证据、调度器排练 ID、验证说明、注意事项和推荐标签。 |
| `docs/project-state.md` | 记录了 P8-6 冻结结果和推荐标签。 |
| `docs/change-log.md` | 记录了本次冻结审查。 |
| `openspec/changes/agenthub-p8-dependency-scheduler-target-locks/tasks.md` | 验证后将 P8-6 标记为完成。 |

### 审查结果

P8 已准备好作为依赖感知调度器和目标锁进行冻结。

P8 未运行全新的真实 Claude/Codex 变异。它使用临时 git 工作区和受控的本地伪造适配器来验证调度器顺序、目标锁、失败依赖阻塞、审查制品创建、健康预览管道和模拟部署管道。P6 仍然是最新的真实 `ClaudeCodeAdapter` 迷你 CRM 执行证据。

### P8 排练证据

| 字段 | 值 |
|---|---|
| 会话 ID | `3fad4108-f0ea-4134-8b31-fb2ab911fadd` |
| 合约 ID | `contract-mini_crm_contacts` |
| 后端任务/运行 | `e7f85f87-fa8a-4203-a33f-682e568a6d50`, `72cf0f92-1c65-460e-b697-4e37cbcefed0` |
| 前端任务/运行 | `e37a46b0-834b-4396-b703-8ecdfd1bf27b`, `bb28106d-d1f8-4431-8245-d40db304edfa` |
| 审查任务 | `336a0c82-6caf-4d84-b421-4ccfcdd17ad7` |
| 差异制品 | `104f1a7b-fa6f-4842-9152-a8e2acc0bbce`, `e92f2e27-c463-4a41-8dad-c7fce2eb87ce` |
| 预览/健康检查 | `56d01fc3-affb-4f6a-bf46-973469a81e1d`, `healthy` |
| 模拟部署/提供者 | `d94dade3-8b3e-4ea0-a0a9-61b2b085ce9e`, `mock` |
| 目标锁证据 | 等待任务 `7e507b15-3cd6-4be3-89d1-893e3777045a`, 持有者运行 `3c241653-2a4e-4782-b58c-729cdc98d1bf` |
| 失败依赖证据 | 失败任务 `39d5151f-888a-4790-bd66-9044f6328053`, 阻塞任务 `84e11005-0148-4926-993c-6c002555507b` |
| 平台保护 | 任务 `4ed028eb-998c-4ca4-8aa0-e0c2dd9dd2f8`, 运行 `ca3f70d9-d4aa-49ed-9e47-c757c432bde5`, 状态 `waiting_approval` |

### 验证

| 命令 | 结果 |
|---|---|
| P8 临时 API 排练 | 通过 |
| `pnpm check` | 通过 |
| `pnpm test` | 通过：37 个 Web 测试，155 个 API 测试，5 个 demo-api 测试。 |
| `pnpm demo:api:test` | 通过：5 个测试。 |
| `git diff --check` | 通过 |
| `openspec validate agenthub-p8-dependency-scheduler-target-locks --strict` | 通过 |

推荐冻结标签：
`p8-dependency-scheduler-target-locks-freeze`。

---

## P8-5 调度器 UI 追踪

**日期：** 2026-05-24

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/web/src/components/task-card-list.tsx` | 为 waits/blocks. 添加了调度器状态标签、任务卡片调度器摘要和执行追踪标志 |
| `apps/web/src/components/task-card-list.test.tsx` | 添加了对调度器目标锁、重试和兜底元数据渲染的覆盖。 |
| `docs/project-state.md` | 记录了 P8-5 UI 追踪行为和限制。 |
| `docs/change-log.md` | 记录了本次实现。 |
| `openspec/changes/agenthub-p8-dependency-scheduler-target-locks/tasks.md` | 验证后将 P8-5 标记为完成。 |

### 变更内容

P8-5 使调度器决策在现有 UI 中可见：

- 任务卡片显示调度器状态、原因、目标 ID、阻塞依赖、目标锁持有者运行 ID、写锁状态、可重试状态和兜底可用性；
- 执行追踪标记依赖等待、目标锁等待和阻塞状态；
- 现有的制品和运行控件保持不变。

### 验证

| 命令 | 结果 |
|---|---|
| 定向任务卡片列表测试 | 通过：37 个 Web 测试。 |
| `pnpm check` | 通过 |
| `pnpm test` | 通过：37 个 Web 测试，155 个 API 测试，5 个 demo-api 测试。 |
| `git diff --check` | 通过 |
| `openspec validate agenthub-p8-dependency-scheduler-target-locks --strict` | 通过 |

---

## P8-4 故障恢复与阻塞状态

**日期：** 2026-05-24

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/api/app/scheduler.py` | 为已完成、可重试和兜底可用状态添加了终端 TaskRun 调度器元数据。 |
| `apps/api/app/task_runs.py` | 在刷新下游依赖和锁状态之前记录终端调度器状态。 |
| `apps/api/tests/test_scheduler.py` | 添加了对兜底可用性、可重试状态以及兜底完成解除下游任务阻塞的覆盖。 |
| `docs/project-state.md` | 记录了 P8-4 故障恢复行为和限制。 |
| `docs/change-log.md` | 记录了本次实现。 |
| `openspec/changes/agenthub-p8-dependency-scheduler-target-locks/tasks.md` | 验证后将 P8-4 标记为完成。 |

### 变更内容

P8-4 使调度器故障恢复状态显式化：

- 已完成的 TaskRun 写入 `planJson.scheduler.state: completed`；
- failed/interrupted Codex 编码运行暴露 `fallback_available`；
- failed/interrupted 非 Codex 运行暴露 `retryable`；
- 上游故障后下游任务保持阻塞；
- 已完成的 retry/fallback 运行会重新评估下游任务，并在满足依赖和目标锁规则时解除其阻塞。

### 验证

| 命令 | 结果 |
|---|---|
| 定向调度器故障测试 | 通过：13 个测试。 |
| `pnpm check` | 通过 |
| `pnpm test` | 通过：36 个 Web 测试，155 个 API 测试，5 个 demo-api 测试。 |
| `git diff --check` | 通过 |
| `openspec validate agenthub-p8-dependency-scheduler-target-locks --strict` | 通过 |

---

## P8-3 自动运行流水线

**日期:** 2026-05-24

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/api/app/planning.py` | 将契约优先的 backend/frontend 任务标记为可自动启动。 |
| `apps/api/app/main.py` | 将安全自动启动扩展到演示后端任务，并在编码 TaskRun 完成后添加契约优先的流水线推进。 |
| `apps/api/tests/test_planning.py` | 更新了迷你 CRM 规划预期，以涵盖通过 TaskRun 实现的后端自动启动。 |
| `docs/project-state.md` | 记录了 P8-3 流水线的行为和限制。 |
| `docs/change-log.md` | 记录了本次实现。 |
| `openspec/changes/agenthub-p8-dependency-scheduler-target-locks/tasks.md` | 验证后将 P8-3 标记为完成。 |

### 变更内容

P8-3 将受约束的契约优先流水线接入现有的执行路径：

- 当依赖和锁允许时，后端和前端契约优先任务可以自动启动；
- 后端完成可以触发前端编码任务；
- 编码完成仍使用现有的差异收集、脚本化审查和账本刷新；
- 就绪的契约审查/QA 任务通过生成的审查制品完成，而不是运行一个可变的 QA 适配器；
- 前端完成会尝试现有的 Vite 预览，并且仅从健康的预览创建模拟部署。

### 验证

| 命令 | 结果 |
|---|---|
| 定向迷你 CRM 规划/调度器测试 | 通过：11 个测试。 |
| `pnpm check` | 通过 |
| `pnpm test` | 通过：36 个 Web 测试，152 个 API 测试，5 个演示 API 测试。 |
| `git diff --check` | 通过 |
| `openspec validate agenthub-p8-dependency-scheduler-target-locks --strict` | 通过 |

---

## P8-2 目标写入锁

**日期:** 2026-05-24

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/api/app/scheduler.py` | 添加了目标 ID 解析、写入锁检测、锁持有者元数据、平台目标阻塞以及组合调度器就绪状态。 |
| `apps/api/app/main.py` | 在安全任务自动启动前使用组合调度器就绪状态。 |
| `apps/api/app/task_runs.py` | 在手动创建 TaskRun 前强制目标写入锁，并在终端运行后刷新会话调度器状态。 |
| `apps/api/tests/test_scheduler.py` | 添加了 frontend/backend 锁、锁释放、只读审查和平台锁保护测试。 |
| `docs/project-state.md` | 记录了 P8-2 目标锁的行为和限制。 |
| `docs/change-log.md` | 记录了本次实现。 |
| `openspec/changes/agenthub-p8-dependency-scheduler-target-locks/tasks.md` | 验证后将 P8-2 标记为完成。 |

### 变更内容

P8-2 在 P8-1 依赖调度器之上添加了目标写入锁：

- 活跃的同一会话写入 TaskRun 会为其解析的 `targetId` 持有目标锁；
- 针对同一目标的另一个可运行写入任务会变为 `waiting_target_lock` 状态，而不是启动；
- 等待锁的元数据标识了目标和活跃持有者的 TaskRun ID；
- 终端 TaskRun 通过重新评估会话调度器状态来释放锁；
- 只读的审查/QA 任务默认不获取目标写入锁；
- 普通的应用后端任务在没有显式平台模式和批准的情况下，无法获取 `agenthub-platform` 写入锁。

### 验证

| 命令 | 结果 |
|---|---|
| 定向调度器锁测试 | 通过：10 个测试。 |
| `pnpm check` | 通过 |
| `pnpm test` | 通过：36 个 Web 测试，152 个 API 测试，5 个演示 API 测试。 |
| `git diff --check` | 通过 |
| `openspec validate agenthub-p8-dependency-scheduler-target-locks --strict` | 通过 |

---

## P8-1 依赖感知的任务调度器

**日期:** 2026-05-24

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/api/app/scheduler.py` | 添加了依赖就绪决策、调度器元数据持久化、会话刷新以及下游刷新辅助函数。 |
| `apps/api/app/main.py` | 在规划后和安全任务自动启动前评估调度器依赖就绪状态。 |
| `apps/api/app/task_runs.py` | 当上游 TaskRun 达到终端状态时，刷新下游调度器状态。 |
| `apps/api/tests/test_scheduler.py` | 添加了依赖就绪、自动启动阻塞、就绪自动启动和下游阻塞覆盖。 |
| `apps/api/tests/test_planning.py` | 更新了规划 API 预期，以暴露 `waiting_dependency` 状态和依赖任务的调度器元数据。 |
| `docs/project-state.md` | 记录了 P8-1 基线行为和限制。 |
| `docs/change-log.md` | 记录了本次实现。 |
| `openspec/changes/agenthub-p8-dependency-scheduler-target-locks/tasks.md` | 验证后将 P8-1 标记为完成。 |

### 变更内容

P8-1 使声明的任务依赖在调度器路径中生效：

- 未完成的依赖会阻止自动创建 TaskRun；
- 已完成的依赖允许符合自动启动条件的任务入队；
- 合成管理器规划任务在任务图创建时被标记为 `completed`，保留了现有的无提及前端自动运行路径；
- 失败、中断或阻塞的依赖会将下游任务标记为 `blocked`；
- 依赖状态可通过 `planJson.scheduler` 查看；
- 在计划自动启动之外，手动创建 TaskRun 保持不变。

### 验证

| 命令 | 结果 |
|---|---|
| 定向的 scheduler/planning 测试 | 通过：7 个测试。 |
| `pnpm check` | 通过 |
| `pnpm test` | 通过：36 个 Web 测试，147 个 API 测试，5 个 demo-api 测试。 |
| `git diff --check` | 通过 |
| `openspec validate agenthub-p8-dependency-scheduler-target-locks --strict` | 通过 |

---

## P7-6 E2E 预演与冻结评审

**日期：** 2026-05-24

### 修改的文件

| 文件 | 变更 |
|---|---|
| `docs/p7-freeze-review.md` | 添加了 P7 冻结证据，复用了 P6 真实执行证据、API 预演 ID、验证说明和注意事项。 |
| `docs/project-state.md` | 记录了 P7-6 冻结结果和推荐标签。 |
| `docs/change-log.md` | 记录了本次冻结评审。 |
| `openspec/changes/agenthub-p7-target-registry-permissioned-execution/tasks.md` | 验证后将 P7-6 标记为完成。 |

### 评审结果

P7 已准备好作为目标项目注册表 + 权限化执行进行冻结。

P7 未运行全新的真实 Claude/Codex 变更。它复用了 P6 最终的
`ClaudeCodeAdapter` mini CRM 证据用于差异、评审、预览和模拟
部署，然后通过 API 预演和回归验证验证了 P7 特定的行为。

### P7 API 预演证据

| 字段 | 值 |
|---|---|
| Mini CRM 会话 ID | `d0500f2c-a480-4903-aea5-5d2d72b2bf31` |
| 合约 ID | `contract-mini_crm_contacts` |
| 前端 / 后端目标 ID | `demo-frontend`, `demo-backend` |
| Demo API 基础 URL | `http://127.0.0.1:5174` |
| Mini CRM 任务 ID | `952bcfd1-12b9-41ca-b81d-694a66b4dcea`, `d382a368-0cd2-4d46-86c6-790b691d4b58`, `5966d060-0df4-463d-94e1-d7bebdddf729`, `634bb541-3b0e-47ad-a408-13392b6dea11` |
| 平台会话 ID | `57d92dde-710f-484e-b86a-f7c0e06e22e6` |
| 平台任务 / 运行 | `fc86452a-a92b-4894-844d-372b5df799e1`, `7ef6efcb-979c-4984-a1a2-2f29f893bc79` |
| 平台目标 / 状态 | `agenthub-platform`, `waiting_approval` |
| 平台审批 | `security_approval`, `high` |

### 验证

| 命令 | 结果 |
|---|---|
| P7 API 预演脚本 | 通过 |
| `pnpm check` | 通过 |
| `pnpm test` | 通过：36 个 Web 测试，142 个 API 测试，5 个 demo-api 测试。 |
| `pnpm demo:api:test` | 通过：5 个测试。 |
| `git diff --check` | 通过 |
| `openspec validate agenthub-p7-target-registry-permissioned-execution --strict` | 通过 |

推荐的冻结标签：
`p7-target-registry-permissioned-execution-freeze`。

---

## P7-5 平台维护模式

**日期：** 2026-05-24

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/api/app/planning.py` | 添加了显式的平台维护路由，同时保留普通的 `@backend` 路由到 `demo-backend`。 |
| `apps/api/app/task_runs.py` | 为 `agenthub-platform` 任务添加了需要审批的 TaskRun 创建。 |
| `apps/api/tests/test_planning.py` | 增加了对普通后端路由和显式平台模式任务创建的覆盖。 |
| `apps/api/tests/test_task_runs.py` | 增加了对平台维护 TaskRun 审批请求的覆盖。 |
| `docs/project-state.md` | 记录了 P7-5 平台模式行为。 |
| `docs/change-log.md` | 记录了本次实现。 |
| `openspec/changes/agenthub-p7-target-registry-permissioned-execution/tasks.md` | 验证后将 P7-5 标记为完成。 |

### 变更内容

P7-5 引入了显式的 AgentHub 平台维护模式：

- 普通的 `@backend` 请求目标为 `demo-backend` / `apps/demo-api`；
- 显式的 `platform mode` 或平台维护措辞会创建
  `agenthub-platform` 任务；
- 平台任务需要 `platformMode: true` 和 `requiresApproval: true`；
- 平台 TaskRun 以 `waiting_approval` 状态启动，并发出
  `security_approval` 请求，而不是立即排队执行。

### 验证

| 命令 | 结果 |
|---|---|
| 定向的 routing/approval 测试 | 通过：3 个测试。 |
| `pnpm check` | 通过 |
| `pnpm test` | 通过：36 个 Web 测试，142 个 API 测试，5 个 demo-api 测试。 |
| `git diff --check` | 通过 |
| `openspec validate agenthub-p7-target-registry-permissioned-execution --strict` | 通过 |

---

## P7-4 目标感知的评审 / QA

**日期：** 2026-05-24

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/api/app/reviews.py` | 为目标注册表评审检查添加了允许路径、拒绝路径、API 基础一致性以及 contract/task 目标一致性。 |
| `apps/api/tests/test_task_runs.py` | 增加了对平台代码变更失败和任务目标不匹配失败的评审覆盖。 |
| `docs/project-state.md` | 记录了 P7-4 评审行为。 |
| `docs/change-log.md` | 记录了本次实现。 |
| `openspec/changes/agenthub-p7-target-registry-permissioned-execution/tasks.md` | 验证后将 P7-4 标记为完成。 |

### 变更内容

P7-4 使确定性评审制品具有目标感知能力：

- 保持在 `demo-frontend` 和 `demo-backend` 允许路径内的全栈差异通过；
- 前端本地 API 基础 URL 必须与注册表解析的
  `demo-backend` 基础 URL 匹配；
- 修改 `apps/api` 的普通应用差异评审失败，风险较高；
- 任务目标 ID 会与合约目标 ID 进行核对。

在此阶段，评审对于 preview/mock 部署仍然是建议性的且非阻塞的。

### 验证

| 命令 | 结果 |
|---|---|
| 定向的 scheduler/planning 测试 | 通过：7 个测试。 |
| `pnpm check` | 通过 |
| `pnpm test` | 通过：36 个 Web 测试，147 个 API 测试，5 个 demo-api 测试。 |
| `git diff --check` | 通过 |
| `openspec validate agenthub-p8-dependency-scheduler-target-locks --strict` | 通过 |
|---|---|
| `tests/test_task_runs.py` 中的定向审查测试 | 通过：4 项测试。 |
| `bash scripts/check-api.sh` | 通过 |
| `pnpm check` | 通过 |
| `pnpm test` | 通过：36 项 Web 测试、141 项 API 测试、5 项 demo-api 测试。 |
| `git diff --check` | 通过 |
| `openspec validate agenthub-p7-target-registry-permissioned-execution --strict` | 通过 |

---

## P7-3 目标感知契约规划器

**日期：** 2026-05-24

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/api/app/planning.py` | 更新了契约优先规划，以从注册表中推导出 frontend/backend 目标 ID、安全路径、原始目标兼容性字段以及演示后端基础 URL。 |
| `apps/api/tests/test_planning.py` | 在生成的任务图中增加了对目标 ID、注册表派生的契约元数据以及目标 ID 的覆盖。 |
| `docs/project-state.md` | 记录了 P7-3 规划器的行为。 |
| `docs/change-log.md` | 记录了本次实现。 |
| `openspec/changes/agenthub-p7-target-registry-permissioned-execution/tasks.md` | 验证后标记 P7-3 完成。 |

### 变更内容

P7-3 在保持现有 P6 迷你 CRM 路径兼容的同时，使契约优先计划具备目标感知能力：

- 应用契约现在包含 `frontendTargetId: demo-frontend` 和 `backendTargetId: demo-backend`；
- `backendTarget`、`frontendTarget`、`backendAllowedPaths`、`frontendAllowedPaths`、`backendBaseUrl` 和 `demoApiBaseUrl` 从注册表元数据中派生；
- 后端、前端和审查任务计划包含目标 ID；
- 任务图元数据包含目标绑定执行步骤的目标 ID。

### 验证

| 命令 | 结果 |
|---|---|
| `pytest tests/test_planning.py -q` | 通过：18 项测试。 |
| `bash scripts/check-api.sh` | 通过 |
| `pnpm check` | 通过 |
| `pnpm test` | 通过：36 项 Web 测试、139 项 API 测试、5 项 demo-api 测试。 |
| `git diff --check` | 通过 |
| `openspec validate agenthub-p7-target-registry-permissioned-execution --strict` | 通过 |

---

## P7-2 目标感知指令构建器

**日期：** 2026-05-24

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/api/app/instruction_builder.py` | 通过目标注册表元数据解析角色指令，包括目标 ID、允许的路径、命令、相关后端基础 URL 以及平台模式要求。 |
| `apps/api/app/context_pack.py` | 当存在目标 ID 时，将已解析的目标元数据和相关目标元数据添加到会话上下文包中。 |
| `apps/api/app/main.py` | 移除了未使用的旧版 `instruction_for_task` 辅助函数，使指令生成只有一个后端边界。 |
| `instruction_for_task` | 增加了对目标感知后端、前端、契约、上下文包和平台维护行为的 instruction/request 覆盖。 |
| `apps/api/tests/test_task_runs.py` | 记录了 P7-2 的行为和剩余的迁移注意事项。 |
| `docs/project-state.md` | 记录了本次实现。 |
| `docs/change-log.md` | 验证后标记 P7-2 完成。 |

### 变更内容

P7-2 在保持 P6 指令行为兼容的同时，允许 P7 目标感知计划驱动指令构建：

- 前端指令引用 `demo-frontend`、`apps/demo/src` 以及注册表解析的 `demo-backend` 基础 URL；
- 后端指令引用 `demo-backend`、`apps/demo-api` 和 `pnpm demo:api:test`；
- 显式的 `agenthub-platform` 任务生成需要平台模式和审批的平台维护指令；
- 上下文包暴露 `targetProject` 和 `relatedTargetProjects` 元数据，用于适配器请求构建。

P7-3 仍需更新规划器输出，以便默认发出目标 ID。

### 验证

| 命令 | 结果 |
|---|---|
| `pytest tests/test_task_runs.py -q` | 通过：26 项测试。 |
| `bash scripts/check-api.sh` | 通过 |
| `pnpm check` | 通过 |
| `pnpm test` | 通过：36 项 Web 测试、139 项 API 测试、5 项 demo-api 测试。 |
| `git diff --check` | 通过 |
| `openspec validate agenthub-p7-target-registry-permissioned-execution --strict` | 通过 |

---

## P7-1 目标项目注册表

**日期：** 2026-05-24

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/api/app/target_registry.py` | 添加了一个静态目标项目注册表，包含演示前端、演示后端和 AgentHub 平台目标记录。 |
| `apps/api/tests/test_target_registry.py` | 增加了对目标元数据、相关后端查找、拒绝路径和平台审批要求的注册表覆盖。 |
| `docs/project-state.md` | 记录了 P7-1 目标注册表基线和剩余的迁移注意事项。 |
| `docs/change-log.md` | 记录了本次实现。 |
| `openspec/changes/agenthub-p7-target-registry-permissioned-execution/tasks.md` | 在完成聚焦的注册表验证后标记 P7-1 完成。 |

### 变更内容

P7-1 为目标元数据创建了一个单一的后端注册表边界：

- `demo-frontend` 映射到 `apps/demo`，允许在 `apps/demo/src` 下进行前端应用工作，并与 `demo-backend` 关联；
- `demo-backend` 映射到 `apps/demo-api`，将 `http://127.0.0.1:5174` 暴露为演示后端基础 URL，并拒绝 `apps/api`；
- `agenthub-platform` 代表 AgentHub 平台维护，需要显式的平台模式加审批。
默认拒绝路径包括 `.env*`、`node_modules`、`.git` 和 `secrets`。
P7-1 尚未将规划器、指令构建器或审查逻辑迁移至消费注册表；该工作从 P7-2 和 P7-3/P7-4. 开始。

### 验证

| 命令 | 结果 |
|---|---|
| `pytest tests/test_target_registry.py -q` | 通过：7 项测试。 |
| `bash scripts/check-api.sh` | 通过 |
| `pnpm check` | 通过 |
| `pnpm test` | 通过：36 项 Web 测试、138 项 API 测试、5 项 demo-api 测试。 |
| `git diff --check` | 通过 |
| `openspec validate agenthub-p7-target-registry-permissioned-execution --strict` | 通过 |

---

## P6-7 最终全栈演练与冻结审查

**日期：** 2026-05-23

### 修改文件

| 文件 | 变更 |
|---|---|
| `apps/demo-api/app/main.py` | 新增本地预览 CORS 支持，使 Vite 预览能够调用安全的演示后端。 |
| `apps/demo-api/tests/test_contacts.py` | 为本地预览来源新增 CORS 预检覆盖。 |
| `docs/project-state.md` | 记录最终 P6-7 冻结证据及剩余注意事项。 |
| `docs/change-log.md` | 记录本次最终演练。 |
| `openspec/changes/agenthub-p6-agent-execution-upgrade/tasks.md` | 在最终演练通过后标记 P6-7 完成。 |

### 审查结果

P6 已准备好作为本地单用户 Agent 编码工作区的实用 Agent 执行能力升级进行冻结。

全新无提及请求：
```text
帮我做一个 mini CRM，包含联系人和备注
```
最终彩排对后端 Agent 和前端 Agent 的运行均使用了真实的 `ClaudeCodeAdapter` 执行。生成的前端使用了合约演示 API 基础 URL `http://127.0.0.1:5174`，最终差异中不包含 `http://localhost:8000` 或 `http://127.0.0.1:8000`。

对预览的浏览器检查显示联系人列表包含 `Ada Lovelace` 和 `Grace Hopper`，验证了迷你 CRM 从演示 API 加载了数据。

### 证据

| 字段 | 值 |
|---|---|
| 会话 ID | `d39ed32a-8426-4c75-86a1-9fd10a57f44c` |
| 合约 ID | `contract-mini_crm_contacts` |
| 演示 API 基础 URL | `http://127.0.0.1:5174` |
| 后端任务 / 运行 | `efe6482b-b2e3-43a7-bae9-2aa0b44dde41`, `908a5708-3334-474c-8af6-b18e6ceaa319` |
| 前端任务 / 运行 | `f1d141d1-7fcb-4629-9ed1-20fd957d6ef4`, `7a01e9ea-8d5d-4690-ae4c-35fbca0b6309` |
| 适配器类型 | 两次编码运行均为 `claude_code` |
| 最终差异制品 | `a89dba5d-cc92-490c-aca1-6c00cd20cc5c` |
| 最终审查制品 | `076f01c5-1949-4fa6-9715-623e41642edb` |
| 最终审查状态 / 风险 | `passed`, `low` |
| 预览 | `d515ffaf-bf9d-481d-9b51-77aa57eb2cef`, `http://127.0.0.1:62947`, 健康 |
| 模拟部署 | `ff54062e-35ca-462d-a5f7-e9a4786517ec`, `mock`, `ready` |

### 剩余注意事项

- 计划的 QA/Review 任务仍待处理；自动差异后审查提供合约一致性证据。
- 审查仍然是确定性的 `scripted_mock`，而非真实的 Claude 审查。
- 部署仍标记为模拟，并非生产部署。
- P6 仍局限于支持的迷你应用系列，而非任意 SaaS 生成。

### 验证

| 命令 | 结果 |
|---|---|
| `pnpm check` | 通过 |
| `pnpm test` | 通过：36 个 Web 测试，131 个 API 测试，5 个演示 API 测试。 |
| `pnpm demo:api:test` | 通过：5 个测试。 |
| `git diff --check` | 通过 |
| `openspec validate agenthub-p6-agent-execution-upgrade --strict` | 通过 |

推荐冻结标签：`p6-agent-execution-upgrade-freeze`。

---

## P6-7a 演示 API 基础对齐修复

**日期：** 2026-05-23

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/api/app/planning.py` | 在合约优先应用合约和验证期望中添加了 `demoApiBaseUrl`。 |
| `apps/api/app/instruction_builder.py` | 更新了合约感知的前端 Agent 指令，要求使用演示后端基础 URL，并禁止为生成的应用数据使用 AgentHub 平台 API 基础 URL。 |
| `apps/api/app/reviews.py` | 为引用 AgentHub 平台 API 而非演示 API 基础的前端差异添加了脚本化审查检测。 |
| `apps/api/tests/test_planning.py` | 为 `demoApiBaseUrl` 和验证期望添加了合约覆盖。 |
| `apps/api/tests/test_task_runs.py` | 为演示 API 基础对齐添加了指令和审查覆盖。 |
| `apps/demo-api/app/main.py` | 添加了本地预览 CORS 支持，以便 Vite 预览可以调用安全的演示后端。 |
| `apps/demo-api/tests/test_contacts.py` | 为本地预览来源添加了 CORS 预检覆盖。 |
| `docs/project-state.md` | 记录了 P6-7a 行为和剩余冻结注意事项。 |
| `docs/change-log.md` | 记录了此实现。 |

### 变更内容

P6-7a 在规划、指令和审查层面修复了 P6-7 冻结阻塞器：

- 迷你应用 `appContract` 负载现在包含 `demoApiBaseUrl: "http://127.0.0.1:5174"`；
- 合约感知的全栈任务的前端 Agent 指令现在要求使用该演示后端基础 URL 进行应用数据调用；
- 前端 Agent 指令明确禁止为生成的应用数据调用 `http://localhost:8000` 或 `http://127.0.0.1:8000`；
- 当合约感知的前端差异引用 AgentHub 平台 API 基础而非演示 API 基础时，脚本化审查现在会发出警告。
- 演示 API 现在通过 CORS 允许本地预览来源。

P6-7a 最初并未运行新的真实 Claude/Codex 变更。后续的最终 P6-7 彩排验证了生成的前端代码使用了演示 API 基础，并且浏览器可见的迷你 CRM 数据从 `apps/demo-api` 加载。

### 验证

| 命令 | 结果 |
|---|---|
| `pytest tests/test_planning.py tests/test_task_runs.py -q` | 通过：43 个测试。 |
| `pnpm check` | 通过 |
| `pnpm test` | 通过：36 个 Web 测试，131 个 API 测试，4 个演示 API 测试。 |
| `pnpm demo:api:test` | 通过：4 个测试。 |
| `git diff --check` | 通过 |
| `openspec validate agenthub-p6-agent-execution-upgrade --strict` | 通过 |

---

## P6-7 全栈垂直切片彩排及冻结审查

**日期：** 2026-05-23

### 修改的文件

| 文件 | 变更 |
|---|---|
| `docs/project-state.md` | 记录了 P6-7 冻结审查结果、持久预览证据和集成阻塞器。 |
| `docs/change-log.md` | 记录了此冻结审查。 |

### 审查结果

P6 尚未准备好冻结。

P6-7 复用了 P6-6 的真实执行证据，而不是运行另一个 Claude/Codex 变更。现有的 P6-6 后端和前端编码 TaskRun 均使用了 `ClaudeCodeAdapter` 并成功完成。最终差异和审查制品仍然显示共享的 `contract-mini_crm_contacts` 合约以及在 `apps/demo-api` 和 `apps/demo/src` 下的目标感知变更。

### 持久预览证据
旧的 `127.0.0.1:8000` 进程接受了 TCP 连接，但未响应
`/health`，因此演练在
`127.0.0.1:8010` 上使用 `pnpm dev:api` 启动了一个新的持久化 AgentHub API。

预览是通过持久化 API 为前端任务运行
`ade5c49c-097d-448e-831c-d10c6bdc3a71` 启动的。

| 字段 | 值 |
|---|---|
| 预览 ID | `3e500940-4d46-423b-af66-b36f1e6ba604` |
| 预览 URL | `http://127.0.0.1:65046` |
| 预览健康状态 | `healthy` |
| 即时 `curl -I` | `200 OK` |
| 延迟 20 秒后的 `curl -I` | `200 OK` |
| 模拟部署 ID | `6b14e81b-c1d6-40ed-b6c4-88a3f846db60` |
| 模拟部署 provider/status | `mock`, `ready` |

临时预览进程和临时的 `8010` / `5174` 开发服务
在验证后已停止。

### 冻结阻塞项

生成的前端预览可访问，但应用默认情况下未与
安全演示后端完全集成：

- `apps/demo-api` 在 `http://127.0.0.1:5174` 上正确提供服务；
- `GET /health` 和 `GET /contacts` 针对 `5174` 工作正常；
- 生成的 P6-6 前端代码硬编码了
  `const API_BASE = "http://localhost:8000"`；
- 浏览器检查显示预览卡在 `Loading contacts...`；
- `curl http://127.0.0.1:8000/contacts` 针对过时的 AgentHub API
  进程超时。

OpenSpec P6-7 复选框仍处于未选中状态。建议的下一个任务是
进行针对性修复，将演示 API 基础 URL 传递给契约感知的前端
指令，并为 frontend/backend API 基础
一致性添加 review/test 覆盖。

### 验证

| 命令 | 结果 |
|---|---|
| `pnpm check` | 通过 |
| `pnpm test` | 通过：36 个 Web 测试，130 个 API 测试，4 个演示 API 测试。 |
| `pnpm demo:api:test` | 通过：4 个测试。 |
| `git diff --check` | 通过 |
| `openspec validate agenthub-p6-agent-execution-upgrade --strict` | 通过 |

---

## P6-6 迷你 CRM 全栈垂直切片

**日期：** 2026-05-22

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/api/app/reviews.py` | 添加了契约感知的脚本化审查检查，以便审查制品可以验证最终的全栈差异是否包含后端和前端契约目标。 |
| `apps/api/tests/test_task_runs.py` | 添加了对后端和前端变更文件的契约感知审查验证覆盖。 |
| `docs/p6-mini-crm-vertical-slice.md` | 记录了 P6-6 冒烟证据、ID、变更文件、验证说明和注意事项。 |
| `docs/project-state.md` | 记录了 P6-6 垂直切片结果和剩余注意事项。 |
| `docs/change-log.md` | 记录了本次实现和演练。 |
| `openspec/changes/agenthub-p6-agent-execution-upgrade/tasks.md` | 验证后将 P6-6 标记为完成。 |

### 变更内容

P6-6 通过以下请求验证了一个有界的迷你 CRM 全栈垂直切片：
```text
帮我做一个 mini CRM，包含联系人和备注
```
编排器生成了共享的 `contract-mini_crm_contacts` 应用合约。
后端 Agent 任务的目标是 `apps/demo-api`，前端 Agent 任务的目标是 `apps/demo/src`，两个编码 TaskRun 均使用了 `ClaudeCodeAdapter`。

最终累积的差异覆盖了：

- `apps/demo-api/app/main.py`；
- `apps/demo-api/tests/test_contacts.py`；
- `apps/demo/src/App.tsx`；
- `apps/demo/src/styles.css`。

最终自动审查制品以低风险通过，并验证了 `contract-mini_crm_contacts` 的合约一致性。预览制品在创建时状态健康，部署制品仍保持模拟标记。

### 证据

| 字段 | 值 |
|---|---|
| 会话 ID | `ad122cf7-afe7-4921-bbd9-b7e815539427` |
| 合约 ID | `contract-mini_crm_contacts` |
| 后端任务/运行 | `590cb06b-4a47-422e-b68f-79a873d4c84a`, `d6779d0f-afa3-4124-9117-c40b651dd79a` |
| 前端任务/运行 | `12ffc19d-f483-4f8d-a541-4c5b935a49b4`, `ade5c49c-097d-448e-831c-d10c6bdc3a71` |
| 适配器类型 | 两个编码运行均为 `claude_code` |
| 最终差异制品 | `db403329-7f0c-4b2c-9134-d2d7ee652564` |
| 最终审查制品 | `1782b85d-c7f9-4d93-b699-27bd27a05ef7` |
| 预览 | `79bfff4f-4991-470b-8862-eb43e7dac852`, `http://127.0.0.1:55592`，创建时健康 |
| 模拟部署 | `e7b676d6-1505-43f8-be78-7120bfaef831`, `mock`, `ready` |

### 验证

| 命令 | 结果 |
|---|---|
| `pytest tests/test_task_runs.py -q` | 通过：24 项测试。 |
| smoke worktree `apps/demo-api` 测试 | 通过：6 项测试。 |
| `pnpm check` | 通过 |
| `pnpm test` | 通过：36 项 Web 测试，130 项 API 测试，4 项 demo-api 测试。 |
| `pnpm demo:api:test` | 通过：4 项测试。 |
| `git diff --check` | 通过 |
| `openspec validate agenthub-p6-agent-execution-upgrade --strict` | 通过 |

### 注意事项

- 这是 API 驱动的演练，而非浏览器点击演练。
- 审查路径使用了确定性的 `ScriptedMockAdapter` 审查行为。
- 计划中的 QA/Review 任务保持待处理状态，因为自动差异后审查制品提供了合约一致性证据。
- 在一次性 TestClient 进程退出后，后续对记录预览 URL 的 `curl` 无法连接，因此应在 P6-7 期间在持久化 `pnpm dev:api` 下检查长期预览可用性。
- 模拟部署保持模拟标记，未执行生产部署。

---

## P6-5 目标感知的合约优先编排器

**日期：** 2026-05-22

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/api/app/planning.py` | 为待办事项、笔记和迷你 CRM 联系人应用添加了有界应用意图检测和合约优先任务图生成。 |
| `apps/api/app/context_pack.py` | 在会话上下文包中添加了显式的 `appContract` 上下文。 |
| `apps/api/app/instruction_builder.py` | 为 Manager、Backend、Frontend 和 QA/Review 指令添加了合约感知的角色指导。 |
| `apps/api/tests/test_planning.py` | 添加了对有界应用解析、无提及迷你 CRM 合约规划、目标映射和不受支持的 SaaS 边界的覆盖。 |
| `apps/api/tests/test_task_runs.py` | 添加了对后端、前端和审查指令引用同一共享合约的覆盖。 |
| `docs/project-state.md` | 记录了 P6-5 的行为、目标和限制。 |
| `docs/change-log.md` | 记录了本次实现。 |
| `openspec/changes/agenthub-p6-agent-execution-upgrade/tasks.md` | 验证后将 P6-5 标记为完成。 |

### 变更内容

编排器现在能够识别针对待办事项、笔记和迷你 CRM 联系人的有界全栈迷你应用请求。对于这些请求，它会生成一个共享的 `appContract` 计划负载，并创建一个串行任务图：
```text
Manager / Contract task -> Backend Agent task -> Frontend Agent task -> QA / Review task
```
该合约包含应用 name/type、用户目标、实体、字段、API 路由、
前端页面、`backendTarget: apps/demo-api`、`frontendTarget: apps/demo`、
验证预期以及任务图。后端、前端和审查
任务都引用相同的 `contractId` 和 `appContract`。

P6-5 默认将生成的任务保持为待处理状态。它不实现实际的
全栈应用生成、合约制品持久化、生产部署、
认证、支付、多租户、Docker、提供商市场、PR 创建或
允许应用后端任务编辑 `apps/api`。

现有的登录页面、有边界的前端、未提及的仪表盘自动运行、直接的
`@frontend` 和直接的 `@backend` 路径保持不变。

### 验证

| 命令 | 结果 |
|---|---|
| `pytest tests/test_planning.py tests/test_task_runs.py -q` | 通过：41 个测试。 |
| `pnpm check` | 通过 |
| `pnpm test` | 通过 |
| `git diff --check` | 通过 |
| `openspec validate agenthub-p6-agent-execution-upgrade --strict` | 通过 |

手动真实的 Claude/Codex 执行未针对 P6-5 运行。该任务的范围限定为
合约优先的规划和合约感知的指令生成。

---

## P6-4 安全演示后端目标脚手架

**日期：** 2026-05-22

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/demo-api/app/main.py` | 添加了独立的 FastAPI 演示后端，包含健康检查和联系人端点。 |
| `apps/demo-api/tests/test_contacts.py` | 添加了演示后端端点测试。 |
| `apps/demo-api/README.md` | 记录了演示后端的用途、端点和命令。 |
| `scripts/check-demo-api.sh` | 为演示后端添加了编译检查包装器。 |
| `scripts/test-demo-api.sh` | 为演示后端添加了 pytest 包装器。 |
| `scripts/dev-demo-api.sh` | 为演示后端添加了本地 uvicorn 开发包装器。 |
| `package.json` | 添加了 `check:demo-api`、`demo:api:test` 和 `demo:api:dev`；在根验证中包含了 demo-api checks/tests。 |
| `apps/api/app/planning.py` | 更新了直接的 `@backend` 分配，以便在脚手架存在时创建一个安全的 `apps/demo-api` 任务。 |
| `apps/api/app/instruction_builder.py` | 更新了后端代理指令，以目标 `apps/demo-api` 并保持 `apps/api` 受保护。 |
| `apps/api/tests/test_planning.py` | 更新了直接的后端提及覆盖率，以创建安全的演示后端任务。 |
| `apps/api/tests/test_task_runs.py` | 更新了后端指令覆盖率，以覆盖可用的演示后端目标。 |
| `AGENTS.md` | 将 demo-api 命令和脚手架描述添加到项目护栏中。 |
| `docs/project-state.md` | 记录了 P6-4 的行为和限制。 |
| `docs/change-log.md` | 记录了此实现。 |
| `openspec/changes/agenthub-p6-agent-execution-upgrade/tasks.md` | 在验证后将 P6-4 标记为完成。 |

### 变更内容

添加了 `apps/demo-api` 作为后端代理工作的安全应用后端目标。
该脚手架故意很小：一个使用内存数据和 `GET /health`、`GET /contacts` 以及 `POST /contacts` 的 FastAPI 联系人 API。

当 `apps/demo-api` 存在时，直接的 `@backend` 请求现在会创建一个分配给后端代理的待处理 `backend_change` 任务。该任务的范围限定为
`apps/demo-api` 文件，并且在 P6-4 中不会自动启动。AgentHub 平台
位于 `apps/api` 下的后端文件通过指令和规划元数据保持受保护。

P6-4 不实现合约优先编排、全栈生成、
生产部署、Docker、云数据库、认证、支付、多租户或
与演示 API 的自动前端集成。

### 验证

| 命令 | 结果 |
|---|---|
| `pnpm check:demo-api` | 通过 |
| `pnpm demo:api:test` | 通过：4 个测试。 |
| `pytest tests/test_planning.py tests/test_task_runs.py -q` | 通过：37 个测试。 |
| `pnpm check` | 通过 |
| `pnpm test` | 通过 |
| `git diff --check` | 通过 |
| `openspec validate agenthub-p6-agent-execution-upgrade --strict` | 通过 |

---

## P6-2 / P6-3 会话上下文包和基于角色的指令

**日期：** 2026-05-22

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/api/app/context_pack.py` | 为适配器执行添加了可重用的会话上下文包构建器。 |
| `apps/api/app/instruction_builder.py` | 为经理、前端、后端和 QA/review 任务添加了特定角色的指令生成。 |
| `apps/api/app/main.py` | 更新了 TaskRun 请求构建，以附加 `sessionContext` 并使用基于角色的指令。 |
| `sessionContext` | 添加了对上下文包内容、制品元数据、选定制品验证、前端请求保留、后端缺失目标诚实性以及审查差异上下文的覆盖率。 |
| `apps/api/tests/test_task_runs.py` | 记录了 P6-2/P6-3 的行为和限制。 |
| `docs/project-state.md` | 记录了此实现。 |
| `docs/change-log.md` | 在验证后将 P6-2 和 P6-3 标记为完成。 |

### 变更内容

实现了 P6 会话上下文和指令质量层。适配器
请求现在在 `planContext` 中包含一个 `sessionContext` 对象，并且生成的
指令将相同的上下文作为 JSON 嵌入到 Claude Code / Codex 中。

上下文包包括原始用户请求、当前任务元数据、
最近同会话消息、账本摘要、最新变更文件、最新差异元数据、最新审查摘要、最新 preview/deploy 状态、选定制品（若提供）、安全目标路径及验证预期。

按角色划分的指令行为：

- **管理者/编排器**：规划、路由、澄清或诚实拒绝不支持的请求。
- **前端**：保留原始请求，包含会话上下文，保持旧版 login-page/button/title 路径不变，并允许在 `apps/demo/src` 内进行有意义的有限变更。
- **后端**：为 `apps/demo-api` 做准备，同时明确说明目标不可用，且 `apps/api` 不得修改。
- **QA/审查**：保持只读导向，聚焦于差异、变更文件、账本、preview/deploy 状态及建议性发现。

P6-2/P6-3 不得添加演示后端脚手架、全栈生成、Manager/Worker 调度、生产部署、新适配器或更广泛的护栏权限。

### 验证

| 命令 | 结果 |
|---|---|
| `pytest tests/test_planning.py tests/test_task_runs.py -q` | 通过：37 项测试。 |
| `pnpm check` | 通过 |
| `pnpm test` | 通过 |
| `git diff --check` | 通过 |
| `openspec validate agenthub-p6-agent-execution-upgrade --strict` | 通过 |

手动跟进冒烟测试未执行新的真实 Claude/Codex 变更。跟进上下文支持已通过后端测试验证，该测试检查生成的 `sessionContext` 及角色指令。

---

## P6-1b 编排器自主性真实冒烟测试

**日期：** 2026-05-22

### 修改的文件

| 文件 | 变更 |
|---|---|
| `docs/p6-orchestrator-autonomy-smoke.md` | 为无提及的编排器自动运行添加了详细真实冒烟证据。 |
| `docs/project-state.md` | 记录了 P6-1b 冒烟结果、证据 ID 及注意事项。 |
| `docs/change-log.md` | 记录了本次 P6-1b 冒烟文档更新。 |

### 已验证内容

使用 `AGENTHUB_DEFAULT_CODE_ADAPTER=claude_code` 及以下请求运行了一次 API 驱动的真实执行冒烟测试：
```text
帮我把当前 demo app 改成一个 dashboard，有三张统计卡片和一个最近活动列表
```
未提及角色的普通消息被路由到编排器/管理器，创建了一个安全的演示前端任务，自动启动了一个 TaskRun，调用了 `ClaudeCodeAdapter`，生成了真实的差异，创建了脚本化的审查制品，在冒烟测试期间启动了健康的预览，并创建了模拟部署卡片。

证据：

- 会话 ID：`cca9af54-1338-4cdd-b239-7f8b6e1dcc76`；
- 消息 ID：`48bad4c0-8ddf-4514-bf35-d2561082c22e`；
- 任务 ID：`63a8aded-b311-40f3-a54c-a40d232102c5`；
- 任务运行 ID：`210f3f89-df0f-4e72-8c20-d505faed5ea2`；
- 适配器类型：`claude_code`；
- 最终状态：`completed`；
- 变更文件：`apps/demo/src/App.tsx`，
  `apps/demo/src/styles.css`；
- 差异制品 ID：`7114d52a-925a-4c4d-a00b-4d6c8775a20c`；
- 审查制品 ID：`ce989818-5d85-4f88-9f70-8b9b5e69d606`；
- 预览 ID / 冒烟期间健康状态：
  `841f7fd6-bb75-4e80-b19c-9b228f5040fb`，`healthy`；
- 模拟部署 ID / 状态：
  `7c9fab78-2b5f-44b3-a9fc-2af0d912a757`，`ready`。

### 注意事项

本次冒烟测试使用了 FastAPI `TestClient`，而非浏览器点击自动化。预览在冒烟测试期间是健康的，但在一次性 TestClient 进程退出后的后续 `curl` 无法访问预览 URL。请在后续浏览器排练期间，在 `pnpm dev:api` 下再次验证长期预览的可用性。

审查制品使用了确定性的 `scripted_mock` 审查行为。由于真实的 Claude Code 已成功完成，因此未触发 ScriptedMock 兜底执行。

---

## P6-1 编排器自主性冲刺

**日期：** 2026-05-22

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/api/app/planning.py` | 添加了默认编排器路由、显式直接分配路由、安全演示前端任务创建、后端缺失目标响应，以及通过 QA 支持的审查任务进行 `@review` 路由。 |
| `apps/api/app/main.py` | 在消息规划后添加了安全演示任务自动启动，以及保留原始用户请求的通用演示前端指令。 |
| `apps/api/tests/test_planning.py` | 增加了对未提及角色的编排器路由、自动启动的演示前端任务、直接 `@frontend`、`@backend` 和 `@review` 行为的测试覆盖。 |
| `apps/api/tests/test_task_runs.py` | 增加了对通用演示前端指令和计划上下文保留的测试覆盖。 |
| `apps/api/tests/test_chat_events.py` | 更新了编排器边界响应的消息范围预期。 |
| `docs/project-state.md` | 记录了 P6-1 的行为、验证和限制。 |
| `docs/change-log.md` | 记录了本次 P6-1 的实现。 |
| `openspec/changes/agenthub-p6-agent-execution-upgrade/proposal.md` | 更新了 P6-1 中关于编排器自动运行的措辞。 |
| `openspec/changes/agenthub-p6-agent-execution-upgrade/design.md` | 记录了狭窄的自动运行冲刺决策及其边界。 |
| `openspec/changes/agenthub-p6-agent-execution-upgrade/specs/agent-execution/spec.md` | 为编排器创建的安全演示编码任务添加了自动运行需求场景。 |
| `openspec/changes/agenthub-p6-agent-execution-upgrade/tasks.md` | 验证后将 P6-1 标记为完成。 |

### 变更内容

将 P6-1 实现为一个狭窄的编排器自主性冲刺。没有显式角色提及的普通用户消息现在默认路由到编排器/管理器。当编排器能够将请求映射到安全演示前端目标时，它会创建一个前端任务，并通过现有执行路径自动启动一个 TaskRun。

显式提及现在充当分配快捷方式：

- `@frontend` 为受限的演示 UI 请求创建一个待处理的前端任务；
- `@backend` 报告在后台执行可以运行之前需要一个安全演示后端目标；
- `@qa` 创建一个 QA 审查类型的任务；
- `@review` 创建一个由 QA 代理路径支持的只读审查任务。

通用演示前端指令现在保留原始用户请求，并允许在 `apps/demo/src` 内进行更广泛的编辑，同时仍然阻止 `.env`、密钥、`node_modules`、生产部署、依赖安装、任意主机命令和 AgentHub 平台后端编辑。

P6-1 未添加完整的 approval/risk 引擎、Manager/Worker 调度器、全栈应用生成、生产部署、多用户 IM、提供商市场、Docker 沙箱或 PR 创建。

### 验证

| 命令 | 结果 |
|---|---|
| `pnpm check` | 通过 |
| `pnpm test` | 通过：36 个 Web 测试和 121 个 API 测试。 |
| `git diff --check` | 通过 |
| `openspec validate agenthub-p6-agent-execution-upgrade --strict` | 通过 |

P6-1 未运行手动浏览器冒烟测试。此任务中未声称任何真实的 Claude/Codex 成功。

---

## P5-7 端到端排练与冻结审查

**日期：** 2026-05-22

### 修改的文件

| 文件 | 变更 |
|---|---|
| `AGENTS.md` | 使基线护栏与已完成的 P5 ledger/review/artifact UI 状态保持一致。 |
| `docs/project-state.md` | 记录了 P5 冻结准备情况、证据、注意事项、验证和推荐的标签名称。 |
| `docs/change-log.md` | 记录了本次 P5-7 冻结审查。 |
| `openspec/changes/agenthub-p5-platform-evolution/tasks.md` | 验证后将 P5-7 标记为完成。 |

### 变更内容

完成了针对 `agenthub-p5-platform-evolution` 的 P5 冻结审查。审查确认 AgentHub 现在呈现为
一个本地单用户 IM 风格的多智能体编码工作区 v1，同时保留 P4 最终演示循环：
```text
requirement -> plan -> agent execution -> diff -> preview -> mock deploy
```
本次审查使用了 P4 浏览器证据，针对真实的 Claude Code 和兜底执行路径，以及 P5 backend/frontend 针对新工作区形状的测试覆盖率和代码审查：

- 智能体联系人列表和本地 Direct Chat / Group 工作流可视化模式；
- 会话执行账本和工作区上下文卡片；
- 有界动态管理器规划器 v1；
- 非阻塞审查智能体制品；
- 多智能体执行追踪；
- Diff、Review、Preview 和 Mock Deploy 制品消息卡片。

P5-7 期间未运行新的 Claude/Codex 变异测试。P5 仍明确限定在本地单用户工作区范围内，不添加多用户 IM、外部 IM 集成、生产部署、提供商市场、Docker 沙箱、PR 创建或不受限制的任意编辑。

### 验证

| 命令 | 结果 |
|---|---|
| `openspec validate agenthub-p5-platform-evolution --strict` | 通过 |
| `pnpm check` | 通过 |
| `pnpm test` | 通过：36 个 Web 测试和 116 个 API 测试。 |
| `git diff --check` | 通过 |

提交后建议的冻结标签：
```text
agenthub-p5-platform-evolution-freeze
```
---

## P5-6 制品消息卡片 v2

**日期:** 2026-05-21

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/web/src/components/task-card-list.tsx` | 为 Diff、Review、Preview 和 Mock Deploy 制品添加了内联消息样式卡片，并带有 panel/context/action 操作提示。 |
| `apps/web/src/components/task-card-list.test.tsx` | 为制品卡片、上下文选择、审查操作、预览打开和模拟部署操作行为添加了前端覆盖。 |
| `apps/web/src/components/workspace-shell.tsx` | 添加了本地会话范围的后续制品上下文芯片，并将 review/deploy/preview 卡片操作连接到现有 API。 |
| `apps/web/src/components/workspace-shell.test.tsx` | 更新了 Review 操作的 API 模拟。 |
| `docs/project-state.md` | 记录了 P5-6 的行为、限制和验证。 |
| `docs/change-log.md` | 记录了本次 P5-6 的实现。 |
| `openspec/changes/agenthub-p5-platform-evolution/tasks.md` | 验证后将 P5-6 标记为完成。 |

### 变更内容

为 P5 IM 风格工作区实现了前端优先的制品消息卡片。Diff、Review、Preview 和 Mock Deploy 制品现在在任务时间线内以内联卡片形式呈现，包含源 task/run 元数据、状态、关键制品详情和操作按钮。

卡片操作仅映射到现有行为：

- 在右侧制品面板中检查制品；
- 使用 Diff 或 Review 作为本地后续上下文；
- 当未加载审查时，触发现有 Review API 以处理 Diff；
- 打开现有的 Preview；
- 从健康的 Preview 创建现有的模拟部署卡片。

编辑器现在为所选制品显示一个会话范围的本地后续上下文芯片。P5-6 不会在后端消息记录中持久化制品引用，也不会更改规划器或适配器语义。

Mock Deploy 仍被明确标记为模拟证据，而非生产部署。

### 验证

| 命令 | 结果 |
|---|---|
| `pnpm check` | 通过 |
| `pnpm test` | 通过：36 个 Web 测试和 116 个 API 测试。 |
| `git diff --check` | 通过 |
| `openspec validate agenthub-p5-platform-evolution --strict` | 通过 |

---

## P5-5 动态管理器规划器 v1

**日期:** 2026-05-21

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/api/app/planning.py` | 添加了有界规则驱动的 Manager 规划器 v1、结构化任务图元数据、图验证和动态前端意图分类。 |
| `apps/api/app/main.py` | 为新的前端变更目标添加了有界适配器指令。 |
| `apps/api/tests/test_planning.py` | 添加了对动态意图、图元数据、后续审查任务和不支持的回退行为的覆盖。 |
| `docs/project-state.md` | 记录了 P5-5 的行为、限制和验证。 |
| `docs/change-log.md` | 记录了本次 P5-5 的实现。 |
| `openspec/changes/agenthub-p5-platform-evolution/tasks.md` | 验证后将 P5-5 标记为完成。 |

### 变更内容

为有界前端变更意图实现了一个确定性的本地 Manager 规划器 v1。该规划器现在对以下支持的请求进行分类：

- 标题或标题文本更改；
- 主要按钮文本更改；
- theme/accent 颜色更改；
- 简单输入字段添加；
- 简单 status/help 文本添加；
- 小型布局副本调整。

由编排器支持的请求会产生一个结构化任务图，包含目标、规划器版本、意图、任务节点、分配的代理角色、优先级、依赖关系和预期的制品类型。该图创建 Manager、Frontend Coding 和 Review 任务。同会话的后续请求会创建一个串行的 Frontend Coding 任务，后跟一个 Review 任务。

原始登录页面路径保持确定性，并标记为 `deterministic_login_v1`。不支持的广泛请求会回退到现有的确定性行为，不会创建任务或声称支持。

P5-5 不会调用 LLM 规划器、实现无限制的任意编辑、更改适配器调度、添加 Manager/Worker 调度、添加生产部署或添加真正的多用户 IM。

### 验证

| 命令 | 结果 |
|---|---|
| `pnpm check` | 通过 |
| `pnpm test` | 通过：34 个 Web 测试和 116 个 API 测试。 |
| `git diff --check` | 通过 |
| `openspec validate agenthub-p5-platform-evolution --strict` | 通过 |

---

## P5-4 多代理执行跟踪 UI

**日期:** 2026-05-21

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/web/src/components/task-card-list.tsx` | 为 Manager、Coding Agent、Diff、Review、Preview 和 Mock Deploy 阶段添加了派生的多代理执行跟踪。 |
| `apps/web/src/components/task-card-list.test.tsx` | 添加了对跟踪渲染、回退高亮、审查警告高亮和制品链接的覆盖。 |
| `docs/project-state.md` | 记录了 P5-4 的行为、限制和验证。 |
| `docs/change-log.md` | 记录了本次 P5-4 的实现。 |
| `openspec/changes/agenthub-p5-platform-evolution/tasks.md` | 验证后将 P5-4 标记为完成。 |

### 变更内容

在任务时间线中实现了一个前端优先的多代理执行跟踪。该跟踪从现有任务、任务运行、制品、审查、预览和部署中派生其状态。它显示：

- Manager 已规划；
- Coding Agent 已运行；
- Diff 已生成；
- Review Agent 已审核；
- 预览状态健康；
- Mock 部署就绪。

每个阶段显示代理或服务标识、adapter/service 类型、状态以及可用的制品链接。Diff、Review、Preview 和 Mock Deploy 节点复用现有的制品选择行为，因此右侧的制品面板仍作为详细检查器。

兜底恢复和审核警告状态会被高亮显示。系统生成的步骤被标记为服务而非自主代理。

P5-4 不会改变适配器调度、任务执行、差异收集、预览、Mock 部署、Review Agent 语义或后端运行时行为。它不会新增 Manager/Worker 调度、动态规划、真实多用户 IM、生产部署或真实的 Claude/Codex 审核执行。

### 验证

| 命令 | 结果 |
|---|---|
| `pnpm check` | 通过 |
| `pnpm test` | 通过：34 个 Web 测试和 113 个 API 测试。 |
| `git diff --check` | 通过 |
| `openspec validate agenthub-p5-platform-evolution --strict` | 通过 |

---

## P5-3 Review Agent 工作流

**日期：** 2026-05-21

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/api/app/models.py` | 新增持久化的 `Review` 记录，链接到审核制品和已审核的差异制品。 |
| `apps/api/app/reviews.py` | 新增确定性的脚本化审核创建、列表、幂等性和事件发射。 |
| `apps/api/app/ledger.py` | 在会话账本摘要中包含最新的审核摘要。 |
| `apps/api/app/schemas.py` | 新增 Review 制品响应模式。 |
| `apps/api/app/main.py` | 新增审核端点，以及在差异生成后自动进行非阻塞的脚本化审核创建。 |
| `apps/api/tests/test_models.py` | 更新了 Review 的模型边界覆盖。 |
| `apps/api/tests/test_diffs.py` | 覆盖了自动审核创建、manual/idempotent 审核创建和账本摘要更新。 |
| `apps/web/src/lib/api.ts` | 新增 Review 制品类型和审核 API 辅助函数。 |
| `apps/web/src/lib/api.test.ts` | 新增审核 create/list 端点的客户端 API 覆盖。 |
| `apps/web/src/components/__fixtures__/sample-review.ts` | 新增一个可复用的审核制品夹具。 |
| `apps/web/src/components/task-card-list.tsx` | 加载 Review 制品并渲染审核时间线芯片。 |
| `apps/web/src/components/task-card-list.test.tsx` | 覆盖了审核时间线芯片和制品面板交接行为。 |
| `apps/web/src/components/preview-card.tsx` | 将 Review 制品添加到右侧制品面板。 |
| `apps/web/src/components/preview-card.test.tsx` | 覆盖了 Review 制品渲染。 |
| `docs/project-state.md` | 记录了 P5-3 的行为、限制和风险。 |
| `docs/change-log.md` | 记录了本次 P5-3 实现。 |
| `openspec/changes/agenthub-p5-platform-evolution/tasks.md` | 验证后将 P5-3 标记为完成。 |

### 变更内容

在差异生成后实现了一个非阻塞的 Review Agent 工作流。当 TaskRun 产生差异时，AgentHub 现在会使用确定性的 `scripted_mock` 审核路径创建一个持久化的 Review 制品。该审核包含状态、风险等级、摘要、已审核文件、发现、建议的更改、已审核差异制品 ID 和适配器类型。

审核路径仅为建议性质。它不会阻止预览创建或 Mock 部署，也不会改变现有的编码适配器行为。此任务中未运行或声称执行了真实的 Claude 或 Codex 审核。

右侧制品面板现在支持 Review 制品，与 Diff、Preview 和 Mock Deploy 并列。任务时间线会加载审核制品，并在可用时显示审核芯片。会话账本摘要会在刷新后包含最新的审核摘要。

### 验证

| 命令 | 结果 |
|---|---|
| `pnpm check` | 通过 |
| `pnpm test` | 通过：33 个 Web 测试和 113 个 API 测试。 |
| `git diff --check` | 通过 |
| `openspec validate agenthub-p5-platform-evolution --strict` | 通过 |

---

## P5-2 共享上下文和执行账本

**日期：** 2026-05-21

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/api/app/models.py` | 新增持久化的 `SessionExecutionLedger`，用于会话范围的上下文快照。 |
| `apps/api/app/ledger.py` | 新增确定性的账本 refresh/read 辅助函数，从消息、任务、运行和制品中派生。 |
| `apps/api/app/schemas.py` | 新增执行账本响应模式。 |
| `apps/api/app/main.py` | 新增 `GET /sessions/{session_id}/ledger`，并在 message/planning、差异、预览和 Mock 部署事件后刷新账本。 |
| `apps/api/tests/test_models.py` | 更新了新账本表的模型边界覆盖。 |
| `apps/api/tests/test_planning.py` | 覆盖了需求规划后的账本创建。 |
| `apps/api/tests/test_diffs.py` | 覆盖了差异收集后的账本更新。 |
| `apps/api/tests/test_previews.py` | 覆盖了健康预览创建后的账本更新。 |
| `apps/api/tests/test_deployments.py` | 覆盖了 Mock 部署创建后的账本更新。 |
| `apps/web/src/lib/api.ts` | 新增了 `SessionExecutionLedger` 和 `getSessionLedger`。 |
| `apps/web/src/lib/api.test.ts` | 新增了会话账本读取的客户端 API 覆盖。 |
| `apps/web/src/components/workspace-shell.tsx` | 新增了所选会话 `Workspace Context` 卡片。 |
| `apps/web/src/components/workspace-shell.test.tsx` | 为工作区上下文账本卡片添加了 UI 覆盖。 |
| `docs/project-state.md` | 记录了 P5-2 状态、刷新点、限制和验证。 |
| `docs/change-log.md` | 记录了本次 P5-2 实现。 |
| `openspec/changes/agenthub-p5-platform-evolution/tasks.md` | 验证后将 P5-2 标记为完成。 |

### 变更内容

为每个会话实现了一个轻量级持久化执行账本。该账本存储当前目标、活跃代理、最新 task/run/diff/preview/mock 部署引用、变更文件、上次成功适配器、摘要 Markdown 以及更新时间戳。

在用户 message/planning、差异收集、健康预览创建或刷新以及模拟部署创建后，账本会从现有数据库记录中刷新。读取端点也会从持久化数据中刷新，以便无需跨会话记忆即可重建旧会话。

前端现在在工作区外壳中为所选会话渲染一个紧凑的 `Workspace Context` 卡片。它显示当前目标、活跃代理、最新证据、适配器和变更文件，同时保持现有任务时间线和制品面板不变。

P5-2 未添加向量数据库、嵌入、跨会话长期记忆、审查代理执行、Manager/Worker 调度或适配器执行变更。

### 验证

| 命令 | 结果 |
|---|---|
| `pnpm check` | 通过 |
| `pnpm test` | 通过：30 个 Web 测试和 113 个 API 测试。 |
| `git diff --check` | 通过 |
| `openspec validate agenthub-p5-platform-evolution --strict` | 通过 |

---

## P5-1 代理注册表与即时通讯联系人 UI

**日期：** 2026-05-21

### 修改文件

| 文件 | 变更 |
|---|---|
| `apps/api/app/schemas.py` | 为即时通讯风格注册表元数据添加了代理联系人响应模式。 |
| `apps/api/app/repositories.py` | 对已启用代理查找进行排序，以实现确定性注册表输出。 |
| `apps/api/app/main.py` | 添加了工作区范围的代理联系人注册表端点及显示元数据映射。 |
| `apps/api/tests/test_planning.py` | 为内置联系人、审查占位符和 ScriptedMock 兜底服务添加了后端覆盖。 |
| `apps/web/src/lib/api.ts` | 添加了 `AgentContact` 和 `listWorkspaceAgents`。 |
| `apps/web/src/lib/api.test.ts` | 为工作区代理联系人添加了客户端 API 覆盖。 |
| `apps/web/src/app/page.tsx` | 为工作区外壳加载了代理联系人。 |
| `apps/web/src/app/page.test.tsx` | 覆盖了将获取的联系人传入外壳的功能。 |
| `apps/web/src/components/workspace-shell.tsx` | 添加了代理联系人 UI 以及直接聊天/群组工作流视觉模式。 |
| `apps/web/src/components/workspace-shell.test.tsx` | 为联系人和视觉模式添加了 UI 覆盖。 |
| `docs/project-state.md` | 记录了 P5-1 状态、限制和验证。 |
| `docs/change-log.md` | 记录了本次 P5-1 实现。 |
| `openspec/changes/agenthub-p5-platform-evolution/tasks.md` | 验证后将 P5-1 标记为完成。 |

### 变更内容

实现了 P5-1，未更改运行时执行语义。AgentHub 现在拥有一个后端支持的注册表结构，用于已启用的内置代理，并在工作区侧边栏中将其渲染为头等即时通讯风格联系人。

注册表公开显示名称、头像首字母、角色、适配器类型、能力标签、状态、联系人类型和 write/review 安全标志。它保持现有的 `CodexAdapter`、`ClaudeCodeAdapter` 和 `ScriptedMockAdapter` 模型不变，为未来的 P5 审查工作流工作添加了审查代理占位符，并保持 ScriptedMock 作为兜底服务可见。

UI 仅添加了直接聊天和群组工作流作为本地视觉模式。P5-1 未添加多用户账户、外部即时通讯集成、Manager/Worker 调度、动态规划、审查代理执行、提供商市场或生产部署。

### 验证

| 命令 | 结果 |
|---|---|
| `pnpm check` | 通过 |
| `pnpm test` | 通过：28 个 Web 测试和 114 个 API 测试。 |
| `git diff --check` | 通过 |
| `openspec validate agenthub-p5-platform-evolution --strict` | 通过 |

---

## P4-6 最终冻结审查

**日期：** 2026-05-20

### 修改文件

| 文件 | 变更 |
|---|---|
| `docs/project-state.md` | 记录了最终冻结就绪状态、注意事项、验证结果及推荐标签名称。 |
| `docs/change-log.md` | 记录了本次最终冻结审查。 |
| `openspec/changes/agenthub-final-demo-hardening/tasks.md` | 验证后将 P4-6 标记为完成。 |

### 变更内容

完成了 `agenthub-final-demo-hardening` 的最终冻结审查。

审查验证了基线文档一致地将 AgentHub 描述为本地单用户代理编码工作区/强演示 MVP，且未声称是完整的即时通讯多用户平台、生产部署、提供商市场、Docker 沙箱、PR 创建或广泛的任意自然语言编辑。

剩余注意事项已记录：

- 部署基于模拟，非生产部署；
- 浏览器点击自动化限制已记录；
- `pnpm demo:reset` 不会删除 `.worktrees`；
- `pnpm demo:reset` 不会停止过期的预览或开发服务器进程；
- mobile/responsive 的打磨完善仍为后续工作。

未更改任何应用代码、运行时行为、适配器行为、UI 重新设计或生产部署工作。

### 验证

| 命令 | 结果 |
|---|---|
| `openspec validate agenthub-im-coding-mvp --strict` | 通过 |
| `openspec validate agenthub-final-demo-hardening --strict` | 通过 |
| `pnpm check` | 通过 |
| `pnpm test` | 通过：26 个 Web 测试和 113 个 API 测试。 |
| `git diff --check` | 通过 |

提交此审查后推荐的最终标签：
```text
agenthub-final-demo-hardening-freeze
```
---

## P4-5 最终项目总结 / 面试说明

**日期:** 2026-05-20

### 修改的文件

| 文件 | 变更 |
|---|---|
| `docs/project-summary-for-interview.md` | 添加了一份用于演示、评审和面试的真实最终总结。 |
| `docs/project-state.md` | 记录了 P4-5 总结范围。 |
| `docs/change-log.md` | 记录了本次文档更新。 |
| `openspec/changes/agenthub-final-demo-hardening/tasks.md` | 在文档验证后标记 P4-5 完成。 |

### 变更内容

创建了一份最终项目总结，将 AgentHub 解释为一个本地单用户 Agent 编码工作区 / 强演示 MVP。该总结涵盖了问题、架构、会话工作树模型、适配器模型、制品流水线、故障恢复路径、后续文本变更流程、真实与模拟组件、明确的非目标、设计权衡以及面试讨论要点。

该总结引用了 `docs/e2e-capability-audit.md` 作为证据，而非发明新的 ID。

未更改任何应用代码或运行时行为。

### 验证

| 命令 | 结果 |
|---|---|
| `git diff --check` | 通过 |

---

## P4-4 最终演示检查清单

**日期:** 2026-05-20

### 修改的文件

| 文件 | 变更 |
|---|---|
| `docs/final-demo-checklist.md` | 添加了一份以证据为先的最终演示检查清单，涵盖重置、启动、真实代理路径、兜底路径、后续路径、证据 ID 和故障排除。 |
| `docs/demo-script.md` | 在设置说明中链接了最终演示检查清单。 |
| `docs/project-state.md` | 记录了 P4-4 检查清单范围。 |
| `docs/change-log.md` | 记录了本次文档更新。 |
| `openspec/changes/agenthub-final-demo-hardening/tasks.md` | 在文档验证后标记 P4-4 完成。 |

### 变更内容

创建了一份最终演示检查清单，可在排练、录制或评审前遵循。它涵盖：

- `pnpm demo:reset`；
- 后端和前端启动；
- 可选的 `AGENTHUB_DEFAULT_CODE_ADAPTER=claude_code`；
- 固定请求 `@orchestrator build a login page for the demo app`；
- 任务运行和适配器验证；
- diff 制品、预览 iframe 和模拟部署卡片检查；
- 通过 `ScriptedMockAdapter` 强制失败的兜底路径；
- 后续请求 `把按钮文案改成 Sign in`；
- 证据 ID 捕获；
- 针对端口、API 可用性、Claude/Codex 认证或配额、过期预览以及在 API 持有 SQLite 打开句柄时重置被拒绝等问题的故障排除。

未更改任何应用代码或运行时行为。

### 验证

| 命令 | 结果 |
|---|---|
| `git diff --check` | 通过 |

---

## P4-3 安全演示重置助手

**日期:** 2026-05-20

### 修改的文件

| 文件 | 变更 |
|---|---|
| `scripts/demo-reset.sh` | 添加了一个非破坏性的本地演示重置助手，在重建种子数据库前备份 SQLite 状态。 |
| `package.json` | 添加了 `pnpm demo:reset`。 |
| `AGENTS.md` | 将 `pnpm demo:reset` 添加到已记录的项目命令允许列表中。 |
| `README.md` | 记录了安全重置行为、备份位置和恢复方法。 |
| `docs/demo-script.md` | 添加了干净的排练设置指南。 |
| `docs/project-state.md` | 记录了 P4-3 重置助手行为。 |
| `docs/change-log.md` | 记录了此任务。 |
| `openspec/changes/agenthub-final-demo-hardening/tasks.md` | 在重置排练和验证后标记 P4-3 完成。 |

### 变更内容

为本地演示状态添加了一个可重复的重置工作流：
```bash
pnpm demo:reset
```
该辅助程序会备份 `apps/api/data/agenthub.sqlite3` 以及 `apps/api/data/backups/demo-reset-<timestamp>/` 下的所有 SQLite WAL/SHM 文件，备份后仅删除活跃的 SQLite 文件，然后通过现有的 SQLModel 初始化路径重新创建并填充数据库。

该辅助程序不会删除 `.worktrees`、源代码、依赖项或预览文件，也不会停止正在运行的预览或开发服务器进程。当 SQLite 数据库被 API 进程打开时，它会拒绝运行，并打印所创建备份的恢复说明。

### 验证

| 命令 | 结果 |
|---|---|
| `pnpm demo:reset` 当 API 持有 SQLite 打开状态时 | 通过：拒绝重置并打印了持有进程。 |
| `pnpm demo:reset` 停止 API 后 | 通过：备份了数据库并重新创建了已填充的 SQLite 状态。 |
| SQLite 种子数据检查 | 通过：1 个用户、1 个工作区、4 个代理、0 个会话、0 个任务运行、0 个预览。 |
| `.worktrees` 检查 | 通过：`.worktrees` 仍然存在且未被删除。 |
| `pnpm check` | 通过 |
| `pnpm test` | 通过：26 个 Web 测试和 113 个 API 测试。 |
| `git diff --check` | 通过 |

重置演练备份：
```text
apps/api/data/backups/demo-reset-20260520-124612/
```
---

## 长期平台路线图

**日期:** 2026-05-20

### 修改的文件

| 文件 | 变更 |
|---|---|
| `docs/platform-roadmap.md` | 新增了从当前本地演示基线到 IM 风格多智能体协作平台的长期 AgentHub 平台路线图。 |
| `docs/change-log.md` | 记录了本次路线图文档的更新。 |

### 变更内容

创建了一份战略路线图，将当前的最终演示加固范围与未来的平台工作分开。它涵盖了动态编排器规划、共享上下文与记忆、manager/worker 调度、Claude Code 安全审查智能体、多用户 IM 集成、plugin/skill 生态系统以及真实的部署提供商。

该路线图明确指出，这些阶段并非当前三周内的任务，在实施之前应成为聚焦的 OpenSpec 变更。

### 验证

| 命令 | 结果 |
|---|---|
| `git diff --check` | 通过 |

---

## P4-2 浏览器端到端点击演练

**日期:** 2026-05-20

### 修改的文件

| 文件 | 变更 |
|---|---|
| `docs/e2e-capability-audit.md` | 为真实的 Claude Code 和兜底路径新增了 P4-2 浏览器点击演练证据，以及重载和 UI 注意事项。 |
| `docs/project-state.md` | 在稳定的项目状态中记录了 P4-2 证据 ID 和重载注意事项。 |
| `docs/change-log.md` | 记录了本次文档更新。 |
| `openspec/changes/agenthub-final-demo-hardening/tasks.md` | 在浏览器演练和验证后，将 P4-2 标记为完成。 |

### 变更内容

记录了针对最终 AgentHub 演示加固变更的浏览器 UI 点击演练。该演练验证了：
```text
requirement -> plan -> UI Start run -> agent execution -> diff -> preview -> mock deploy
```
真实代理路径：

- 会话：`59ad209a-1f8d-4134-97c4-e4ad275b6f67`
- TaskRun：`f1e78e9e-2f6b-4b9c-b4a7-5879d513c555`
- 适配器：`claude_code`
- Diff 制品：`b4c0fae4-bfeb-4105-a506-64de639472c6`
- 预览：`4eb1622b-fb10-49e7-9b3d-5c256fad4b29`
- 预览 URL：`http://127.0.0.1:49373`
- 部署：`6c5a423c-ec7b-4070-9a05-87a8dddd91a1`
- Provider/status：`mock`，`ready`

兜底路径：

- 会话：`c148a1d6-8cd1-4efb-a797-7d10bbe475aa`
- 失败的 Codex TaskRun：`e7cead6e-93cd-4195-9a53-e258da253a81`
- 失败错误码：`CODEX_DEMO_FORCED_FAILURE`
- 兜底 TaskRun：`36d68849-f644-4242-a64b-27c05b8cf2d8`
- 适配器：`scripted_mock`
- Diff 制品：`fbe67726-20e3-4ad5-9b08-d4514aa97cbe`
- 预览：`6c7f6f46-e287-4698-b6be-c99058f69b11`
- 预览 URL：`http://127.0.0.1:49752`
- 部署：`a0b5d533-acee-4b2a-a384-103197d46481`
- Provider/status：`mock`，`ready`

### 注意事项

- 开始按钮的宽泛浏览器定位器最初匹配了所有三个任务卡片；演练通过针对前端任务的第二个 `开始运行` 按钮进行了恢复。
- 重新加载后，即使预览和部署制品已持久化，制品面板默认显示 Diff 标签页。点击 `预览1` 可恢复预览 URL 和 iframe 视图。
- 未添加任何应用代码、产品行为、UI 重新设计、提供商市场、生产部署、Docker 沙箱、WebSocket/multiplayer、PR 创建或宽泛编辑功能。

### 验证

| 命令 | 结果 |
|---|---|
| `pnpm check` | 通过 |
| `pnpm test` | 通过 |
| `git diff --check` | 通过 |

### 后续浏览器抽查

在 2026-05-20 上，持久化的 P4-2 真实 Claude Code 和兜底会话在 Codex 应用内浏览器中重新打开，未运行其他真实代理变更。

- 真实 Claude Code 会话
  `59ad209a-1f8d-4134-97c4-e4ad275b6f67` 仍显示已完成的
  `claude_code` 证据、`apps/demo/src/App.tsx` diff 标签、预览 iframe
  `http://127.0.0.1:49373` 和模拟部署
  `6c5a423c-ec7b-4070-9a05-87a8dddd91a1`。
- 兜底会话 `c148a1d6-8cd1-4efb-a797-7d10bbe475aa` 仍显示
  `CODEX_DEMO_FORCED_FAILURE`、`scripted_mock`、`兜底已恢复`、`Diff 就绪`、
  `预览健康` 和 `模拟部署就绪`。

---

## P4-1 基线治理清理

**日期：** 2026-05-20

### 修改的文件

| 文件 | 变更 |
|---|---|
| `AGENTS.md` | 将仓库护栏从仅 P0 的措辞更新为当前最终演示基线，包括 Codex、Claude Code 和脚本化模拟适配器。 |
| `README.md` | 将 AgentHub 重新定义为本地单用户代理编码工作区/强演示 MVP，并记录了当前适配器路径。 |
| `docs/project-state.md` | 添加了 P4-1 治理基线说明，保留了 P0/P1/P2/P3/P4 已验证的路径。 |
| `docs/change-log.md` | 记录了此次清理。 |
| `openspec/changes/agenthub-im-coding-mvp/specs/worktree-diff/spec.md` | 将可选的补丁验证要求更改为严格兼容的 MUST 措辞。 |
| `openspec/changes/agenthub-final-demo-hardening/proposal.md` | 为严格的 OpenSpec 验证添加了 documentation/verification 能力。 |
| `openspec/changes/agenthub-final-demo-hardening/specs/demo-baseline-hardening/spec.md` | 为最终演示加固添加了治理和证据纪律要求。 |
| `openspec/changes/agenthub-final-demo-hardening/tasks.md` | 验证后标记 P4-1 完成。 |

### 变更内容

围绕当前项目状态对齐基线治理：

- AgentHub 现在被一致描述为本地单用户代理编码工作区/强演示 MVP，而非完整的多用户 IM 协作平台。
- `CodexAdapter`、`ClaudeCodeAdapter` 和 `ScriptedMockAdapter` 均被视为
  当前适配器，不得移除或退化。
- 基于兜底的 P0 路径保持不变。
- 生产部署、提供商市场、Docker 沙箱、WebSocket/multiplayer、
  外部 IM 集成、PR 创建、宽泛的任意编辑和企业工作流仍不在范围内。
- `worktree-diff` 中之前的 OpenSpec 严格验证问题已修复。

### 验证

| 命令 | 结果 |
|---|---|
| `openspec validate agenthub-im-coding-mvp --strict` | 通过 |
| `openspec validate agenthub-final-demo-hardening --strict` | 通过 |
| `pnpm check` | 通过 |
| `pnpm test` | 通过（26 个 Web 测试，113 个 API 测试） |
| `git diff --check` | 通过 |

### 剩余治理注意事项

- P4-2 仍需要浏览器端到端点击演练；P4-0 验证了浏览器面向的 API 路径，但未完成自动化浏览器点击。
- 预先存在的脏文件，包括本地 app/test/doc 更改和未跟踪的截图，除非 P4-1 直接要求，否则保持不变。
- 此任务未更改任何应用运行时行为。

---

## P4-0 完整端到端代理执行能力审计

**日期：** 2026-05-19

### 修改的文件

| 文件 | 变更 |
|---|---|
| `docs/e2e-capability-audit.md` | 添加了 P4-0 执行能力审计、证据 ID、限制和结论。 |
| `docs/project-state.md` | 记录了 P4-0 已验证的真实代理、兜底和后续路径。 |
| `docs/change-log.md` | 记录了此次审计。 |

### 变更内容

记录了当前 AgentHub 执行的完整端到端能力审计
流水线。审计使用了 `AGENTHUB_DEFAULT_CODE_ADAPTER=claude_code` 并验证了：
```text
requirement -> orchestrator plan -> Direct Start -> ClaudeCodeAdapter -> file mutation -> diff -> healthy preview -> mock deploy
```
它还验证了强制性的 Codex 失败加上 ScriptedMockAdapter 兜底路径，
以及针对 `把按钮文案改成 Sign in` 的同一会话自然语言跟进路径。

### 审计结果

- 真实代理路径：通过浏览器面向 API 的端点。
- 兜底路径：通过。
- 跟进路径：通过。
- 浏览器点击自动化：未完全验证，因为未安装 Playwright，且 Chrome AppleScript 控制被 macOS Apple Events 权限提示阻止。

### 验证

| 命令 | 结果 |
|---|---|
| `pnpm check` | 通过 |
| `pnpm test` | 通过（139 个测试：26 个 Web + 113 个 API） |
| `git diff --check` | 通过 |

---

## 前端中文文案与排版优化

**日期：** 2026-05-19

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/web/src/app/globals.css` | 添加了中文优先的字体栈和全局 line-height/text 渲染调优。 |
| `apps/web/src/lib/date-format.ts` | 将紧凑时间戳改为中文 month/day 格式。 |
| `apps/web/src/lib/date-format.test.ts` | 更新了针对中文日期输出的时间戳预期。 |
| `apps/web/src/components/workspace-shell.tsx` | 本地化了命令中心 Shell 标签、错误文案、Composer 占位符、演示流水线、侧边栏、聊天和时间线标题。 |
| `apps/web/src/components/task-card-list.tsx` | 本地化了任务状态、运行历史、证据标签、审批文案和运行控件，同时保留现有回调。 |
| `apps/web/src/components/preview-card.tsx` | 本地化了 preview/artifact 面板标签、操作按钮、摘要元数据、空状态和 iframe 标题。 |
| `apps/web/src/components/diff-card.tsx` | 本地化了差异制品标签、变更文件元数据和 expand/collapse 控件。 |
| `apps/web/src/components/deploy-card.tsx` | 本地化了部署卡片标签和通用 status/title 显示。 |
| `apps/web/src/components/health-card.tsx` | 本地化了后端健康状态徽章显示。 |
| 前端组件测试 | 更新了针对本地化 UI 文案的断言。 |
| `docs/change-log.md` | 记录了本次本地化和排版优化。 |

### 变更内容

前端现在以中文呈现命令中心界面，同时保留后端数据、适配器名称、文件路径、URL 以及诸如 `Diff`、`Vite` 和 `API` 等技术产品术语，以支持编码代理演示。

间距和排版针对中文可读性进行了轻微调整：

- 中文优先的系统字体栈，包含 `PingFang SC`、`Microsoft YaHei` 和 Noto CJK 后备字体。
- 全局正文行高设置为 `1.5`。
- 时间线项目间距略微收紧，以适应更密集的中文标签。
- 面向用户的日期格式现在渲染为 `5月17日 02:06`。

### 验证

| 命令 | 结果 |
|---|---|
| `pnpm --filter @agenthub/web check` | 通过 |
| `pnpm --filter @agenthub/web test` | 通过（26 个 Web 测试） |
| `pnpm check` | 通过 |
| `pnpm test` | 通过（26 个 Web 测试，113 个 API 测试） |
| `git diff --check` | 通过 |
| 浏览器渲染检查 | 通过：已验证中文 Shell 文案、中文优先字体栈、视口高度文档、内部滚动区域和 Composer 可见性。截图于 `/tmp/agenthub-zh-ui-check.png` 捕获。 |

### 已知限制

- 任务标题、会话标题、适配器名称、制品标题、路径、URL 和原始后端状态字符串，当来自持久化后端数据或有意使用的技术标识符时，仍可能为英文。

---

## P3 UI 同步错误处理

**日期：** 2026-05-19

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/api/app/main.py` | 允许 `http://127.0.0.1:3000` 和 `http://localhost:3000` 作为本地前端 CORS 来源。 |
| `apps/api/tests/test_health.py` | 为回环和本地主机前端来源添加了 CORS 回归测试覆盖。 |
| `apps/web/src/components/workspace-shell.tsx` | 为消息、任务、SSE 任务刷新和 UI 操作添加了受保护的客户端会话同步错误处理。 |
| `apps/web/src/components/workspace-shell.test.tsx` | 添加了一个回归测试，模拟浏览器 fetch 失败并验证显示面向用户的后端同步警告。 |
| `docs/change-log.md` | 记录了修复。 |

### 变更内容

浏览器端会话刷新现在会捕获失败的 `fetch` 调用，而不是泄漏未处理的 Promise 拒绝。当 FastAPI 后端不可达或会话同步请求失败时，UI 会保持现有页面挂载，并显示一个紧凑的警告，提示用户检查后端 URL。

后端现在接受两种常见的本地浏览器来源，因此在端口 8000 上从 API 获取数据时，在 `localhost:3000` 或 `127.0.0.1:3000` 打开 Web UI 不会触发 CORS。预期的客户端同步失败不再调用 `console.error`，因此它们不会在开发终端中显示为 Next/browser 错误堆栈。

### 原因

当 `fetch` 在切换或加载会话时失败，浏览器报告了来自 `listSessionMessages` 和 `listSessionTasks` 的未处理拒绝。该失败应在 UI 中可见且可恢复，而不是作为运行时错误出现。在本地开发中，浏览器来源也可能在 `localhost` 和 `127.0.0.1` 之间不同；CORS 必须允许两种形式。

### 验证

| 命令 | 结果 |
|---|---|
| `pnpm check` | 通过 |
| `pnpm test` | 通过（139 项测试：26 项 Web + 113 项 API） |
| `git diff --check` | 通过 |

---

## TaskRun 测试环境隔离

**日期：** 2026-05-19

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/api/tests/test_task_runs.py` | 将 TaskRun API 测试与继承的 `AGENTHUB_DEFAULT_CODE_ADAPTER` shell 状态隔离，同时保留显式的 Claude 默认适配器覆盖。 |
| `docs/change-log.md` | 记录了测试隔离修复。 |

### 变更内容

TaskRun 测试现在会清除共享的 `client` 夹具中的 `AGENTHUB_DEFAULT_CODE_ADAPTER`，因此即使开发者从为 Claude Code 演示配置的 shell 启动测试，默认的 Codex 断言也能保持稳定。有意验证 `claude_code` 选择的测试仍会通过 `monkeypatch` 显式设置环境变量。

### 验证

| 命令 | 结果 |
|---|---|
| `AGENTHUB_DEFAULT_CODE_ADAPTER=claude_code pnpm test:api` | 通过（112 项 API 测试） |
| `pnpm check` | 通过 |
| `pnpm test` | 通过（25 项 Web 测试，112 项 API 测试） |
| `git diff --check` | 通过 |

### 已知限制

- 这不会改变运行时适配器选择行为；它仅稳定了测试环境。

---

## 命令中心布局滚动修复

**日期：** 2026-05-18

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/web/src/app/globals.css` | 将 `html` 和 `body` 锁定为视口高度，并禁用了文档级滚动。 |
| `apps/web/src/app/page.tsx` | 将页面根元素更改为视口高度、溢出隐藏的应用外壳。 |
| `apps/web/src/app/page.test.tsx` | 更新了视口高度布局的外壳所有权断言。 |
| `apps/web/src/components/workspace-shell.tsx` | 使命令中心外壳、侧边栏、中心时间线和编辑器使用有界的 flex/grid 尺寸，并包含内部滚动区域。 |
| `apps/web/src/components/preview-card.tsx` | 使制品详情面板成为有界的内部滚动区域。 |
| `docs/change-log.md` | 记录了此布局滚动修复。 |

### 变更内容

此阶段保持命令中心结构、状态所有权、API 和演示操作不变，同时修复了页面级滚动：

- 应用外壳现在使用视口高度并设置溢出隐藏。
- 左侧会话列表在侧边栏内滚动。
- 中心 chat/task 时间线在中心面板内滚动。
- 编辑器锚定在中心工作区的底部。
- 右侧制品详情面板在内部滚动，而不是拉伸文档。

### 验证

| 命令 | 结果 |
|---|---|
| `pnpm check` | 通过 |
| `pnpm test` | 通过（25 项 Web 测试，112 项 API 测试） |
| `git diff --check` | 通过 |
| 浏览器布局检查 | 通过：Chrome DevTools 测量显示 document/body 滚动高度等于视口高度，`html`/`body` 溢出隐藏，侧边栏和中心滚动区域在内部溢出，制品面板使用内部溢出，编辑器在底部可见，页眉可见。截图于 `/tmp/agenthub-scroll-check.png` 捕获。 |

### 已知限制

- 这仅是一次布局机制调整；它不会重新设计任务时间线或添加完整的制品面板标签页。

---

## P3 UI 最终视觉 QA 阶段

**日期：** 2026-05-18

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/web/src/components/task-card-list.tsx` | 通过更强的选中制品强调、更大的任务标题、更紧凑的依赖文本以及保留的垂直轨道层级，提高了任务时间线的可读性。 |
| `apps/web/src/components/preview-card.tsx` | 为制品详情添加了摘要元数据，包括源任务、任务运行、变更文件、差异统计、预览 health/status 和部署 status/provider.。 |
| `apps/web/src/components/workspace-shell.tsx` | 弱化了低价值的烟雾测试会话，减少了侧边栏元数据重复，并将顶部流水线标记为演示流程。 |
| `docs/change-log.md` | 记录了此最终视觉 QA 打磨阶段。 |

### 变更内容

此阶段保持命令中心结构和制品状态所有权不变，同时收紧视觉呈现：

- 中心任务卡片现在具有更强的标题权重和选中的制品焦点。
- 左侧会话列表在视觉上弱化了重复的烟雾测试会话，并且仅显示活动会话的任务焦点元数据。
- 右侧制品详情面板现在包含源任务摘要和制品特定统计信息：
  - 差异：文件数、变更文件、新增行数、删除行数。
  - 预览：健康状态、状态、端口、主机。
  - 部署：提供商、状态、环境、URL。
- 顶部流水线现在带有显式的 `Demo flow` 标签。

### 验证

| 命令 | 结果 |
|---|---|
| `pnpm check` | 通过 |
| `pnpm test` | 通过（25 项 Web 测试，112 项 API 测试） |
| `git diff --check` | 通过 |
| 浏览器渲染检查 | 通过：针对正在运行的本地 UI 捕获了 `/tmp/agenthub-final-visual-qa.png`。 |

### 已知限制

- 这不会添加新的制品面板工作流或生产级标签页。
- Mobile/responsive 行为仍是未来的阶段。
- 烟雾测试会话仍然可选；它们仅在视觉上被弱化。

---

## P3 UI 重新设计阶段 3：时间线和制品面板打磨

**日期：** 2026-05-18

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/web/src/components/task-card-list.tsx` | 优化了中心任务列表，使其成为更强的垂直执行轨道，改进了任务卡间距，并使兜底恢复流程更清晰地呈现为：Codex 失败 → 兜底恢复 → 制品就绪。 |
| `apps/web/src/components/task-card-list.test.tsx` | 更新了优化后任务标签的任务标记断言。 |
| `apps/web/src/components/preview-card.tsx` | 强化了制品面板的层级结构，包含更清晰的详情头部、分段式 Diff/Preview/Deploy 选择器、已选制品标签以及更强的活动标签状态。 |
| `apps/web/src/components/workspace-shell.tsx` | 减少了侧边栏会话列表的冗余信息，并提升了顶部流水线状态的可读性。 |
| `docs/change-log.md` | 记录了本次第三阶段视觉优化工作。 |

### 变更内容

第三阶段在保留第二阶段数据所有权和 API 行为不变的基础上，优化了视觉层级：

- 中心任务时间线现在采用垂直轨道，并带有编号的任务节点。
- 任务卡片更轻量、更易扫描，且不再那么方正。
- 运行历史按更清晰的运行次数和恢复状态进行分组。
- 兜底恢复现在呈现为：
  `Codex failed -> fallback recovered -> artifacts ready`。
- 侧边栏会话显示更少的重复元数据；仅选中的会话会显示任务焦点详情。
- 顶部流水线对已完成、已恢复、就绪、运行中和待处理状态使用了更清晰的状态标签。
- 制品面板现在呈现为一个详情面板，包含更清晰的头部、已选制品类型标签以及分段式的 Diff / Preview / Deploy 控件。

### 验证

| 命令 | 结果 |
|---|---|
| `pnpm check` | 通过 |
| `pnpm test` | 通过（25 个 Web 测试，112 个 API 测试） |
| `git diff --check` | 通过 |
| 浏览器渲染检查 | 通过：已捕获 `/tmp/agenthub-phase3-polish.png` 并对照现有本地 web/API 服务进行验证。 |

### 已知限制

- 这仍然不是一个完整的任务执行详情页面。
- 制品面板控件已优化，但仍是一个紧凑的选择器，而非完整的生产级标签页。
- 移动端布局将在后续阶段处理。

---

## P3 UI 重新设计第二阶段：制品面板所有权

**日期：** 2026-05-18

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/web/src/components/task-card-list.tsx` | 从中心时间线中移除了内联的详细 Diff、Preview 和 Deploy 卡片渲染；任务卡片现在仅显示制品摘要标签和更清晰的 recovery/run 摘要。 |
| `apps/web/src/components/preview-card.tsx` | 将右侧面板扩展为一个制品面板，能够渲染选中的 diff、preview 或 deployment 详情，并暴露现有的 preview/deploy 操作。 |
| `apps/web/src/components/workspace-shell.tsx` | 添加了纯前端的制品选择状态、默认选择最新制品的功能以及右侧面板回调，同时保留了现有的 API 调用和 SSE 刷新。 |
| `apps/web/src/components/task-card-list.test.tsx` | 更新了任务时间线测试，以断言摘要标签、制品选择和制品项交接，而非内联详情卡片。 |
| `apps/web/src/components/preview-card.test.tsx` | 更新了面板测试，以验证选中制品的渲染。 |
| `docs/change-log.md` | 记录了本次第二阶段前端重新设计工作。 |

### 变更内容

中心任务时间线现在专注于执行状态。它不再在每个任务后内联复制详细的 diff、preview 或 deployment 卡片。相反，每个任务卡片仅展示紧凑的制品证据：

- Diff 就绪
- 已更改文件
- Preview 健康状态
- Deploy mock 就绪
- 已恢复 / 兜底状态

`TaskCardList` 仍然使用现有的前端 API 客户端函数来获取 TaskRun 制品，但现在会将其转换为纯前端的 `ArtifactPanelItem` 对象，并传递给 `WorkspaceShell`。`WorkspaceShell` 会保留选中的制品 ID，并在没有有效选择时将面板默认显示为最新的可用制品。

右侧的制品面板现在负责制品详情的渲染：

- Diff 制品通过现有的 `DiffCard` 渲染。
- Preview 制品通过现有的 `PreviewCard` 加 iframe 渲染。
- Deployment 制品通过现有的 `DeployCard` 渲染。

现有行为保持不变：

- 开始、重试、使用 ScriptedMockAdapter 重试、强制 Codex 失败、中断、批准和拒绝操作仍保留在中心任务卡片中。
- Preview 刷新、打开、停止和 mock 部署操作仍通过右侧面板连接到现有的 API 回调。
- 未对后端 API 进行任何更改。

### 验证

| 命令 | 结果 |
|---|---|
| `pnpm check` | 通过 |
| `pnpm test` | 通过（25 个 Web 测试，112 个 API 测试） |
| `git diff --check` | 通过 |
| 浏览器渲染检查 | 通过：已捕获 `/tmp/agenthub-phase2-artifact-panel.png`；右侧面板默认显示最新的 diff 制品，而中心时间线不再渲染内联的制品详情卡片。 |

### 已知限制

- 这并未实现完整的制品面板标签页或任务详情页面。
- 面板仍使用紧凑的选择器轨道；更丰富的制品浏览功能将在后续的视觉优化阶段处理。
- 中心任务时间线在制品所有权稳定后，仍需另一次优化以实现更紧凑的垂直轨道样式。

---

## P3 UI 视觉质量优化第一轮
**日期：** 2026-05-18

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/web/src/app/page.tsx` | 移除了外层页面卡片包装器，使指挥中心呈现为完整工作区。 |
| `apps/web/src/app/page.test.tsx` | 更新了全屏页面结构的 shell 所有权断言。 |
| `apps/web/src/components/health-card.tsx` | 将后端健康状态压缩为单个头部徽章，并附带工具提示详情。 |
| `apps/web/src/components/preview-card.tsx` | 优化了右侧制品面板占位符，添加了标签式选项卡、Safari 风格预览外壳、虚线预览画布和可见的等待卡片。 |
| `apps/web/src/components/workspace-shell.tsx` | 调整了标题层级、流水线处理方式、侧边栏选中状态、中央空状态卡片、编辑器表面和编排器计划样式。 |
| `docs/change-log.md` | 记录了本次视觉 QA 优化过程。 |

### 视觉 QA 方法

使用三个根级参考 PNG（`1.png`、`2.png`、`3.png`）作为
可用的视觉参考，因为在此检出中缺少 `docs/ui-redesign/assets`。
主要工作区目标为 `3.png`。

通过本地 Google Chrome 无头模式捕获当前 UI：
```bash
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --headless=new \
  --disable-gpu \
  --hide-scrollbars \
  --window-size=1440,1000 \
  --virtual-time-budget=5000 \
  --screenshot=/tmp/agenthub-main-workspace-task-refined.png \
  "http://127.0.0.1:3000?session=cb653482-c31a-48da-a8ee-31ed8cd367e3"
```
### 发现的主要视觉不匹配问题

1.  命令中心仍显示为大型圆角页面卡片，而非全屏工作区。
2.  头部高度和后端健康状态权重使流水线显得次要。
3.  侧边栏的已选会话样式过于通用，与参考中更强的活动导轨不匹配。
4.  右侧制品面板占位符缺少参考中的预览画布质量。
5.  Orchestrator/empty-state 卡片需要更轻的层级和更柔和的边框。

### 验证

| 命令 | 结果 |
|---|---|
| `pnpm check` | 通过 |
| `pnpm test` | 通过（25 个 Web 测试，112 个 API 测试） |
| `git diff --check` | 通过 |

### 已知限制

-   此轮迭代有意不实现执行详情页面或完整的制品面板标签页。
-   侧边栏时间戳仍由现有日期格式化程序支持，以避免在此纯视觉切片中引入对水合敏感的相对时间渲染。

---

## P3 UI 重新设计切片 1：命令中心外壳

**日期：** 2026-05-18

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/web/src/app/globals.css` | 为表面、主靛蓝色、弱化文本、边框和代码颜色添加了命令中心设计令牌。 |
| `apps/web/src/app/page.tsx` | 将旧的页面包装器替换为命令中心容器，并将健康状态移入工作区外壳头部插槽。 |
| `apps/web/src/app/page.test.tsx` | 更新了主页测试，以断言外壳拥有命令中心页面结构。 |
| `apps/web/src/components/health-card.tsx` | 将后端健康状态从大型页面卡片精简为头部的紧凑状态表面。 |
| `apps/web/src/components/preview-card.tsx` | 将右侧预览区域重新设计为制品面板占位符，同时保留预览 refresh/close 和 iframe 行为。 |
| `apps/web/src/components/task-card-list.tsx` | 将任务重构为带有代理标签、运行历史、证据芯片的时间线，并保留 run/approval/preview/deploy 控件。 |
| `apps/web/src/components/task-card-list.test.tsx` | 更新了对新时间线标签和拆分运行历史标记的断言。 |
| `apps/web/src/components/ui/button.tsx` | 使按钮圆角和主色与命令中心令牌方向对齐。 |
| `apps/web/src/components/workspace-shell.tsx` | 将前端外壳重建为左侧边栏、中央 IM chat/task 时间线、顶部演示流水线和右侧制品面板布局，同时保留现有状态所有权和 API 回调。 |
| `docs/change-log.md` | 记录了此纯前端重新设计切片。 |

### 变更内容

实现了来自 `docs/ui-redesign-spec.md` 的第一个实际 UI 重新设计切片。
之前的页面级卡片布局被替换为 IM 风格的编码代理命令中心：

1.  一个固定的左侧 workspace/session 边栏，包含工作区标识、会话列表、当前会话状态元数据和全宽的新建会话操作。
2.  一个中央工作区，包含当前会话头部、聊天气泡、编排器计划标注、任务时间线容器和编辑器。
3.  一个右侧制品面板占位符，在视觉上保留最终的 diff/preview/deploy 工作区，而不添加不支持的标签页。
4.  一个顶部演示流水线，展示 P0 循环：需求 → 计划 → 运行 → 差异 → 预览 → 部署。

所有现有的前端 API 调用和回调（用于启动、重试、强制失败、兜底、预览、部署、批准、拒绝、中断、SSE 刷新和持久化 session/task/run/artifact 获取）仍通过现有客户端函数连接。

### 验证

| 命令 | 结果 |
|---|---|
| `pnpm check` | 通过 |
| `pnpm test` | 通过（25 个 Web 测试，112 个 API 测试） |
| `git diff --check` | 通过 |
| 手动本地渲染检查 | 通过：复用了现有的 `127.0.0.1:8000` 和 `127.0.0.1:3000` 服务；验证渲染的 HTML 包含命令中心标题、演示流水线阶段、后端状态、新建会话操作和制品面板占位符。 |

### 已知限制

-   此切片有意不实现完整的制品面板标签页。
-   流水线预览和部署阶段保持为视觉占位符，直到制品面板阶段连接更丰富的制品状态。
-   `docs/ui-redesign/assets` 在此检出中不存在；根级别的未跟踪参考 PNG 文件保持不变。
-   未生成屏幕截图，因为工作区中未安装 Playwright；手动检查使用了已在运行的本地 Next.js 服务器，并渲染了 HTML 验证。

---

## 前端设计交接简报

**日期：** 2026-05-17

### 修改的文件

| 文件 | 变更 |
|---|---|
| `docs/frontend-design-brief.md` | 添加了一份 Gemini 交接简报，记录了当前前端能力、UI 表面、流程、架构、API 约束、设计问题和实现约束。 |
| `docs/change-log.md` | 记录了此纯文档交接任务。 |

未更改任何应用代码、后端代码、前端代码、适配器代码、测试或依赖项。

### 变更内容

创建了一份纯文档的前端设计简报，以便 Gemini 可以在经过验证的 P1 能力和当前 API 约束范围内提出更好的 AgentHub UI。

该简报记录了：
- AgentHub 的 IM 风格编码代理产品定位。
- 已验证的 P1 直接 Codex 及兜底能力。
- 当前的会话、聊天、任务、运行、差异、预览、面板、部署和健康 UI 界面。
- 主要成功、兜底和 reload/recovery 流程。
- 当前的 Next.js 前端架构、API 客户端函数、数据类型、状态获取和 SSE 使用。
- Backend/API Gemini 不得超越的约束。
- 目标当前 UI 弱点及 Gemini 的设计要求。
- 未来 Codex 前端重构的实现约束。

### 验证

| 命令 | 结果 |
|---|---|
| `git diff --check` | 通过 |

### 已知限制

- 此任务未重新设计或实现 UI 更改。
- 审批卡片 UI 仍处于冻结的 P1 判断路径之外，并记录为当前前端中不存在。

---

## P1-1：直接 UI 启动 TaskRun 分发修复

**日期：** 2026-05-16

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/api/app/main.py` | +86/-3 行 |
| `apps/api/tests/test_task_runs.py` | +107 行（3 个新测试） |

### 修改的函数/区域

- `apps/api/app/main.py`
  - `create_task_run_for_task` — 从 `def` 更改为 `async def`，添加了 `BackgroundTasks` 参数，现在在创建 TaskRun 后分发 `_background_execute_task_run`。
  - `adapter_for_type`（新增）— 从适配器类型字符串解析 `AgentAdapter` 实例。
  - `execute_task_run`（新增）— 可重用辅助函数，构建 `AgentRunRequest`，通过 `run_adapter_event_stream` 分发适配器执行，并在完成时收集差异。
  - `_background_execute_task_run`（新增）— 异步后台任务，创建独立数据库会话，解析适配器，调用 `execute_task_run`，并将意外失败规范化为 `failed` 状态并附带 `ADAPTER_EXECUTION_ERROR`。

- `apps/api/tests/test_task_runs.py`
  - `test_direct_ui_start_dispatch_creates_queued_run_with_adapter_type`（新增）
  - `test_direct_ui_start_background_execution_persists_events`（新增）
  - `test_direct_ui_start_scripted_mock_background_execution_persists_events`（新增）

### 变更内容

`POST /tasks/{task_id}/runs` 之前仅创建了一个 `queued` TaskRun 数据库行并立即返回。未分发任何适配器执行。TaskRun 永远停留在 `queued` 状态。

此修复后，端点：
1. 在 `queued` 状态下创建 TaskRun（未更改）。
2. 通过 FastAPI `BackgroundTasks` 分发 `_background_execute_task_run`。
3. 立即返回 TaskRun 响应。
4. 后台任务创建独立数据库会话，解析适当的适配器（`CodexAdapter` 或 `ScriptedMockAdapter`），并调用现有的 `execute_task_run` 路径。
5. 持久化 TaskRunEvent，应用状态转换，并在完成时收集差异。
6. 将意外的适配器失败规范化为 `failed` 状态。

### 原因

直接 UI 启动是唯一未分发适配器执行的执行路径。工作路径（`force-codex-failure` 和 `retry-with-fallback`）在创建运行后已调用 `run_adapter_event_stream`。此修复将直接 UI 启动与现有分发模式统一，同时使用 `BackgroundTasks` 避免阻塞 HTTP 响应以等待长时间运行的适配器执行。

### 验证

| 命令 | 结果 |
|---|---|
| `pnpm check` | 通过 |
| `pnpm test` | 通过（77 个测试：21 个 Web + 56 个 API） |
| `git diff --check` | 通过 |

### 已知限制

- 未测试真实 Codex 成功，因为此机器未安装 Codex CLI。
- 此修复在分发级别验证直接 UI 启动（后台执行已调度，适配器调用已尝试，TaskRunEvent 已持久化，失败已规范化）。
- 完整的制品生成（差异、预览、部署）仍取决于针对真实会话工作树的成功适配器执行。
- 现有的基于兜底的 P0 演示路径（`Force Codex failure` → `Retry with ScriptedMockAdapter` → 差异 → 预览 → 部署）保持完整且未更改。

---

## P1-2：真实 Codex CLI 执行验证

**日期：** 2026-05-16

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/api/tests/test_codex_adapter.py` | +30 行（4 个新测试） |
| `apps/api/tests/test_task_runs.py` | +19/-2 行（加强断言） |

### 修改的函数/区域

- `apps/api/tests/test_codex_adapter.py`
  - `test_codex_adapter_default_binary_is_macos_codex_app_path`（新增）— 验证 `DEFAULT_CODEX_BINARY` 常量。
  - `test_codex_adapter_respects_codex_cli_path_env_var`（新增）— 验证 `CODEX_CLI_PATH` 环境变量覆盖。
  - `test_codex_adapter_falls_back_to_default_when_env_var_unset`（新增）— 验证环境变量缺失时兜底到默认值。
  - `test_codex_adapter_constructor_binary_override_takes_precedence`（新增）— 验证显式 `codex_binary` 参数具有最高优先级。

- `apps/api/tests/test_task_runs.py`
  - `test_direct_ui_start_background_execution_persists_events` — 加强断言：现在验证适配器生命周期事件存在于排队之后，并且失败的运行带有 `CODEX_*` 错误代码及非空错误消息。

### 变更内容
1. 为 `CodexAdapter` 二进制解析新增了 4 个单元测试（默认路径、环境变量覆盖、构造函数覆盖、兜底优先级）。
2. 强化了后台调度集成测试，以断言当执行失败时 CodexAdapter 能生成可识别的 `CODEX_*` 错误码。
3. 针对会话工作区执行了一次真实的 Codex CLI 冒烟测试，以验证当 Codex 可用时适配器路径能端到端工作。

### 真实 Codex CLI 冒烟测试结果

- **Codex CLI 可用：** `/Applications/Codex.app/Contents/Resources/codex` (v0.131.0-alpha.9) — **是。**
- **Codex CLI 已认证：** 使用 ChatGPT 登录 — **是。**
- **命令格式：** 与 `docs/adapter-notes.md` 完全匹配 (`--ask-for-approval never exec --json --cd <worktree> --sandbox workspace-write "<instruction>"`)。
- **生成的 JSONL 事件：** `thread.started`, `turn.started`, `item.started`, `item.completed` — **是。**
- **退出码：** `0` — **是。**
- **工作区中的文件变更：** 未测试（只读冒烟）。Codex 搜索并定位了跨多个会话工作区目录的 `apps/demo/src/App.tsx`。

### 原因

P1-1 修复了 Direct UI Start 调度，但未验证真实的 CodexAdapter CLI 路径是否实际工作。P1-2 弥补了这一验证缺口：确认 Codex CLI 存在且可执行，确认其命令格式与文档规范匹配，确认它在会话工作区内生成 JSONL 生命周期事件，并添加了不依赖真实 Codex 的 CI 安全测试。

### 验证

| 命令 | 结果 |
|---|---|
| `pnpm check` | 通过 |
| `pnpm test` | 通过（81 个测试：21 个 Web + 60 个 API） |
| `git diff --check` | 通过 |
| 真实 Codex 只读冒烟（手动） | 通过（JSONL 事件，工作区导航已确认） |
| 真实 Codex 写入与差异冒烟（手动） | 通过（见下文） |

### 真实 Codex 写入与差异冒烟测试 (2026-05-16)

**结果 A：通过 Direct UI Start 验证了真实的写入与差异（API 级别，非 UI 级别）。**

创建了一个新的会话工作区。将一个任务分配给前端代理（CodexAdapter）。使用指令调用 CodexAdapter：`"In apps/demo/src/App.tsx, find the element with data-agenthub-target='primary-action-button' and change only its text to 'Codex Verified'."`

结果：
- **持久化了 26 个 TaskRunEvent**，包括 `thread.started`, `turn.started`, `item.started`/`item.completed`（command_execution 和 file_change）, `turn.completed`。
- **Codex 修改了文件：** `apps/demo/src/App.tsx` — 将按钮文本从 `"Continue"` 替换为 `"Codex Verified"`。
- **TaskRun 状态：** `completed`。
- **收集了差异制品：** `artifact.diff.ready` 事件已持久化，包含 `artifactId` 和 `diffId`。Git 差异确认 1 个文件已更改，1 处插入，1 处删除。
- **瞬态 stderr 噪声：** Codex 在执行期间将 `"Reconnecting..."` 消息作为 `{"type":"error"}` JSONL 事件发出；这些被映射到 `CODEX_EXIT_ERROR` 错误事件，但当 `turn.completed` 紧随其后时不会阻止运行完成。这是已知的 Codex CLI 行为，而非适配器错误。

验证是通过直接 Python 调用 `CodexAdapter` + `run_adapter_event_stream` + `collect_task_run_diff` 执行的，而非通过 HTTP 端点，因为 CodexAdapter 中的 `BackgroundTasks` + 同步 `process.communicate()` 会阻塞 FastAPI 事件循环，在长时间 Codex 运行期间阻止并发请求处理。这种事件循环阻塞是一个预先存在的限制，同样影响 `force-codex-failure` 和 `retry-with-fallback` 端点。

### 已知限制

- 真实 Codex CLI **可用**（v0.131.0-alpha.9，通过 ChatGPT 登录）在当前验证环境中。这取决于环境。
- **真实的写入与差异已验证**（API 级别）：Codex 修改了 `apps/demo/src/App.tsx`，文件变更由 `git diff` 确认，差异制品由后端服务收集。
- Direct UI Start 端点在后台调度真实的 Codex 执行。`process.communicate()` 正在阻塞事件循环；此问题已在 P1-3 中解决。
- 来自缺失工作区与缺失 Codex 二进制的 `FileNotFoundError` 都映射到 `CODEX_NOT_FOUND`。这种预先存在的歧义未在 P1-2 中处理。
- 瞬态 Codex `"Reconnecting..."` JSONL 事件被映射到 `CODEX_EXIT_ERROR` 错误事件，但当 `turn.completed` 紧随其后时不会阻止成功完成。
- 现有的基于兜底的 P0 演示路径保持不变。

---

## P1-3：非阻塞子进程执行修复

**日期：** 2026-05-16

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/api/app/codex_adapter.py` | +2 行：添加了 `import asyncio`，将 `communicate()` 更改为 `await asyncio.to_thread(communicate)` |
| `apps/api/tests/test_codex_adapter.py` | +49 行：`DelayedFakeCodexProcess`，非阻塞测试，`_drain_events` 辅助函数 |
| `docs/change-log.md` | P1-3 条目 |

### 修改的函数 / 区域

- `apps/api/app/codex_adapter.py`
  - `streamEvents`（第 161 行）：将同步的 `state.process.communicate()` 替换为 `await asyncio.to_thread(state.process.communicate)`。
  - 添加了 `import asyncio`。

- `apps/api/tests/test_codex_adapter.py`
- `DelayedFakeCodexProcess`（新增）——一个伪进程，在 `communicate()` 中休眠，以模拟长时间运行的子进程。
- `test_codex_adapter_does_not_block_event_loop_during_communicate`（新增）——证明当适配器的 `communicate()` 在线程池中运行时，并发的 `asyncio.sleep` 能及时完成。
- `_drain_events`（新增）——辅助函数，用于从异步生成器中收集事件。

### 变更内容

`CodexAdapter.streamEvents()` 内部的阻塞式 `process.communicate()` 调用被包裹在 `asyncio.to_thread()` 中。这将阻塞式的子进程等待移至工作线程，从而保持 asyncio 事件循环空闲，以服务其他请求（健康检查、SSE、任务查询）。

### 原因

P1-2 确认，`BackgroundTasks` 加上同步的 `process.communicate()` 会在整个 Codex 执行期间（30-90秒）阻塞 FastAPI asyncio 事件循环。在此期间，无法服务任何其他 HTTP 请求——健康检查、SSE 事件推送和任务查询都会挂起。`asyncio.to_thread()` 将阻塞操作隔离在线程池中，使事件循环保持响应能力。

### HTTP 直接 UI 启动验证

ScriptedMockAdapter 通过完整的 HTTP 路径进行了测试：

| 步骤 | 结果 |
|---|---|
| `POST /tasks/{task_id}/runs` | 返回 201，包含已排队的 TaskRun |
| 执行期间的健康检查 | 全程约 5ms 内返回 `ok` |
| TaskRun 最终状态 | `completed` |
| Diff 制品 | 1 个文件变更（`apps/demo/src/App.tsx`），11 处新增，4 处删除 |

CodexAdapter 通过直接调用 `_background_execute_task_run` 运行：
- 持久化了 9 个 TaskRunEvent（已排队 → 流式事件 → 错误事件）
- TaskRun 最终状态为 `failed`，附带 `CODEX_USAGE_LIMIT`（账户达到使用限制）
- Codex 子进程执行期间事件循环保持空闲

### 验证

| 命令 | 结果 |
|---|---|
| `pnpm check` | 通过 |
| `pnpm test` | 通过（82 个测试：21 个 Web + 61 个 API） |
| `git diff --check` | 通过 |
| HTTP 直接 UI 启动 + ScriptedMockAdapter | 通过（已收集 diff） |
| 直接 `_background_execute_task_run` + CodexAdapter | 通过（事件已持久化，使用限制已标准化） |

### 已知限制

- 事件仍在 `communicate()` 返回后批量持久化，而非在 Codex 执行期间实时流式传输。实时的逐行事件流式传输需要将 `communicate()` 替换为异步 readline 循环——已推迟。
- 在 P1-3 验证期间，真实的 Codex 达到了使用限制，因此未验证真实 Codex 通过 HTTP 的成功路径。已验证标准化的失败路径（CODEX_USAGE_LIMIT）。
- `asyncio.to_thread` 需要 Python 3.9+；该项目要求 Python 3.9+。
- 现有的基于兜底的 P0 演示路径保持不变。

---

## P1-4：增量式 Codex JSONL 流式传输

**日期：** 2026-05-16

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/api/app/codex_adapter.py` | 将全过程的 stdout 收集替换为增量式 stdout JSONL 逐行流式传输和并发的 stderr 捕获。 |
| `apps/api/tests/test_codex_adapter.py` | 添加了流式进程的伪实现和测试，用于增量事件生成、完成前持久化和事件循环响应性。 |
| `docs/change-log.md` | 添加了此 P1-4 条目。 |

### 修改的函数/区域

- `apps/api/app/codex_adapter.py`
  - `CodexProcess`——现在暴露 `stdout_lines()`、`wait()` 和 `stderr_text()`，而非全过程的 `communicate()` 契约。
  - `SubprocessCodexProcess.stdout_lines`——使用 `asyncio.to_thread(stdout.readline)` 逐行读取 stdout。
  - `SubprocessCodexProcess.stderr_text`——在 stdout 流式传输的同时并发地排空 stderr。
  - `CodexAdapter.streamEvents`——一旦每条完整的 JSONL stdout 行可用，立即解析，立即生成映射后的 `AgentEvent`，然后在进程完成后处理 stderr 和退出状态。
  - `_finish_process`——等待进程完成并返回标准化的 stderr 摘录。

- `apps/api/tests/test_codex_adapter.py`
  - `StepwiseFakeCodexProcess`——伪进程，在第一条 JSONL 行后暂停，以便测试可以证明事件在进程完成前已生成。
  - `test_codex_adapter_streams_jsonl_before_process_completion`——验证第一个映射事件在伪进程 waited/exited. 之前已生成。
  - `test_codex_streamed_events_persist_before_process_completion`——验证 `run_adapter_event_stream` 在进程完成前持久化了第一个 TaskRunEvent。
  - `test_codex_adapter_does_not_block_event_loop_while_waiting_for_jsonl`——验证在等待 Codex stdout 时可以运行不相关的异步任务。

### 变更内容

在 P1-4 之前，`CodexAdapter.streamEvents()` 使用了：
```python
stdout, stderr = await asyncio.to_thread(state.process.communicate)
```
这保持了 FastAPI 事件循环的响应性，但它仍然在 Codex 退出后才收集所有 stdout。TaskRunEvent 在子进程运行结束时被批量解析和持久化。

在 P1-4 之后，适配器增量地流式传输 stdout：

1. 并发启动 stderr 捕获。
2. 等待每个可用的 JSONL stdout 行。
3. 立即解析该行。
4. 将其映射为 `AgentEvent`。
5. 立即将事件产出给 `run_adapter_event_stream`。
6. 让 `run_adapter_event_stream` 在 SSE 投递前持久化事件。
7. stdout 关闭后，等待进程完成并处理 stderr/exit 退出码。

### 原因

P1-3 解决了事件循环阻塞问题，但没有解决实时可见性问题。UI/SSE 路径可以保持响应性，但在进程完成之前无法观察 Codex 的进度。P1-4 使 Codex JSONL stdout 成为真正的流，这样在 Codex 仍在运行时，持久化的 TaskRunEvent 就可以出现。

### 验证

| 命令 | 结果 |
|---|---|
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_codex_adapter.py` | 通过（14 个测试） |
| `pnpm check` | 通过 |
| `pnpm test` | 通过（84 个测试：21 个 Web + 63 个 API） |
| `git diff --check` | 通过 |

### 手动验证结果

针对一个新的计划前端任务，尝试了使用真实 Codex 的 HTTP 直接启动：

- 会话：`62919139-e820-47d0-9557-ae7653740082`
- TaskRun：`360e7781-a3cf-4692-bf7f-67f5447c0f36`
- 初始状态：`queued`
- 执行期间观察到的状态：`streaming`
- 执行期间的健康检查：`ok`（1-9ms）
- 持久化事件回放行数：12
- 最终状态：`failed`
- 标准化错误码：`CODEX_EXIT_ERROR`
- 标准化错误消息：
  `Reconnecting... 2/5 (timeout waiting for child process to exit)`
- Diff 制品：未生成

这验证了 HTTP 直接启动不再卡在 `queued`，尝试了真实的 Codex 执行，events/state 在 Codex 运行时变得可见，并且 API 保持响应性。它**没有**验证 HTTP 直接启动 -> 真实 Codex 文件变更 -> diff 制品，因为真实的 Codex 进程在产生成功的文件变更之前就失败了。

### 已知限制

- 适配器现在增量地流式传输 Codex stdout，但真实的 HTTP 写入和 diff 验证仍然依赖于本地 Codex quota/auth/process 的稳定性。
- Stderr 被并发捕获并附加到最终的 fallback/error 处理中，但映射的中间事件可能不包含最终的 stderr，因为它们是在进程完成之前发出的。
- 通过真实 Codex 成功路径的 Preview/deploy 仍未得到验证，除非手动 HTTP 运行达到成功的文件变更和 diff 制品。
- 现有的基于兜底的 P0 演示路径保持不变，并且必须保持可用。

---

## P1-5：Codex 重连处理与 HTTP 直接启动诊断

**日期：** 2026-05-16

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/api/app/codex_adapter.py` | 将 Codex 重连 JSON 事件视为信息性进度，当后续通用 `turn.failed` 到达时保留特定的 Codex 错误码。 |
| `apps/api/app/main.py` | 为计划的前端登录页面任务生成有边界的演示文件指令，而不是将宽泛的任务标题发送给 Codex。 |
| `apps/api/tests/test_codex_adapter.py` | 添加了重连和特定错误保留的测试。 |
| `apps/api/tests/test_task_runs.py` | 添加了有边界的前端登录页面运行指令的测试。 |
| `docs/change-log.md` | 添加了此 P1-5 条目。 |

### 修改的函数/区域

- `apps/api/app/codex_adapter.py`
  - `_map_codex_json_event` — 将 `Reconnecting... N/5 (timeout waiting for child process to exit)` JSON 事件映射为 `message.delta` 进度事件，而不是终端错误。
  - `_is_reconnecting_error`（新增）— 从 Codex JSON stdout 检测重连进度消息。
  - `_is_generic_failure_event`（新增）— 检测通用 `CODEX_EXIT_ERROR` / `Codex run failed.` 事件。
  - `CodexAdapter.streamEvents` — 当更具体的 Codex 错误已经发出时，跳过后续的通用 `turn.failed` 错误，这样诸如 `CODEX_USAGE_LIMIT` 的可操作错误就不会被覆盖。

- `apps/api/app/main.py`
  - `instruction_for_task`（新增）— 将计划的前端登录页面任务转换为一个小的、明确的指令，针对 `apps/demo/src/App.tsx` 和 `data-agenthub-target="login-page-slot"`。
  - `agent_run_request_for` — 现在使用 `instruction_for_task(task)` 而不是宽泛的任务标题。

### 变更内容

P1-4 显示 HTTP 直接启动失败，错误信息为：
```text
CODEX_EXIT_ERROR: Reconnecting... 2/5 (timeout waiting for child process to exit)
```
P1-5 发现这是一个适配器映射错误。手动运行相同的 Codex CLI 命令表明，Codex 可以发出 `Reconnecting... 5/5`，然后记录 `falling back to HTTP`，继续发出正常的事件项，修改文件，并以 `turn.completed` 结束。因此，重新连接 JSON 事件不一定是终止性的。

适配器现在将重新连接 JSON 事件视为进度消息。真正的失败来自进程退出码、非重新连接的 Codex 错误，或特定的 Codex 故障（如使用限制或身份验证失败）。

P1-5 还缩小了 HTTP Direct Start 指令的范围。以前，后端只发送任务标题 `Build the Vite React login page`，因此 Codex 将请求视为一个宽泛的 OpenSpec 实现任务，并在接触演示应用之前读取大型 OpenSpec 文件。现在，后端为确定性的演示登录页面任务发送一个有限制的、针对文件的指令。

### 原因

直接的 Python 写入和差异冒烟测试成功，因为它使用了狭窄的文件编辑指令。HTTP Direct Start 使用了宽泛的任务标题，并且还将 Codex 重新连接进度视为终止性的。这些差异使得 HTTP 路径在 mutation/diff 之前失败，尽管 CLI 能够在同一会话工作区中进行真实的文件编辑。

### 验证

| 命令 | 结果 |
|---|---|
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_codex_adapter.py tests/test_task_runs.py` | 通过（29 个测试） |
| `pnpm check` | 通过 |
| `pnpm test` | 通过（89 个测试：21 个 Web + 68 个 API） |
| `git diff --check` | 通过 |

### 手动验证结果

在重新连接映射和有界指令修复之后，尝试了使用真实 Codex 的 HTTP Direct Start：

- 会话：`1eac3075-ac06-4504-94f9-76dd4b17ad9d`
- TaskRun：`dac99e3d-2bb5-4f93-a31d-da9480c04ae6`
- 初始状态：`queued`
- 执行期间观察到的状态：`streaming`
- 执行期间的健康检查：`ok` 在 1-5ms 内
- 持久化事件重放行数：27
- 最终状态：`failed`
- 最终标准化错误码：`CODEX_EXIT_ERROR`
- 最终标准化错误消息：`Codex run failed.`
- 差异制品：未生成

检查持久化事件后，在最终通用失败之前发现了有用的底层错误：
```text
CODEX_USAGE_LIMIT: You've hit your usage limit. To get more access now, send a request to your admin or try again at 10:02 PM.
```
在 P1-5 之后，测试确保这个特定的 `CODEX_USAGE_LIMIT` 错误被保留下来，
而不会被后续的通用 `turn.failed` 事件覆盖。

在 Codex 失败后，同一会话中也执行了兜底路径：

- 使用 ScriptedMockAdapter 重试：已完成
- Diff 制品：已生成
- 变更的文件：`apps/demo/src/App.tsx`
- Diff 统计：1 个文件变更，11 处新增，4 处删除
- 预览：在 `http://127.0.0.1:64508` 处健康
- 部署：mock 提供者，状态 `ready`

### 已知限制

- HTTP 使用真实 Codex 文件变更和 diff 收集的 Direct Start 未经验证，
  因为在 HTTP 运行期间，本地 Codex 账户达到了使用限制。
- 手动 CLI 验证确认了重连事件之后可以跟随兜底到 HTTP、文件变更、`git diff` 和 `turn.completed`；
  适配器现在能处理该事件形态。
- Preview/deploy 通过真实 Codex 成功路径仍未验证，直到 Codex 配额允许一次成功的 HTTP Direct Start 变更。
- 现有的基于兜底的 P0 演示路径保持完整且已验证。

---

## P1-6：HTTP Direct Start 真实 Codex 端到端预演

**日期：** 2026-05-16

### 修改的文件

| 文件 | 变更 |
|---|---|
| `docs/change-log.md` | 添加了此 P1-6 预演结果。 |

### 变更内容

P1-6 未更改任何产品代码。这是在 P1-5 reconnect/error-handling 修复之后以及 Codex 使用限制重置之后进行的一次针对性预演。

### 手动验证结果

HTTP 使用真实 Codex 的 Direct Start 通过 UI 使用的后端 API 路径进行了预演：

- 会话：`a0b51d27-0473-44f3-b079-bbb02fdf00bb`
- 用户请求：
  `@orchestrator build a login page for the demo app`
- Codex 支持的任务：`f9e982c3-df76-4740-b38c-e14e8cb3497c`
- TaskRun：`fa23fb4a-6506-4b0e-a608-3197356d0628`
- 初始状态：`queued`
- 执行期间观察到的状态：`streaming`
- 最终状态：`completed`
- 错误 code/message：无
- 持久化的事件重放行数：84
- 执行期间的健康检查：`ok`，耗时 1-5 毫秒
- 工作树：
  `.worktrees/98449267-914c-4f26-82b5-e1d176d64f91/a0b51d27-0473-44f3-b079-bbb02fdf00bb`

真实 Codex 变更了：
```text
apps/demo/src/App.tsx
```
收集到的差异制品已持久化：

- 制品 ID：`782e16f4-36b5-46f3-86cf-42c3fb6119e9`
- 差异 ID：`5df0273d-f9fc-46b3-bbfa-242d5d185667`
- 变更文件：`["apps/demo/src/App.tsx"]`
- 统计：1 个文件变更，20 处新增，4 处删除

文件差异将确定性的登录页面插槽副本替换为包含邮箱和密码字段的紧凑登录表单。这验证了：
```text
HTTP Direct Start -> real Codex file mutation -> diff artifact
```
### 兜底验证

P1-6 直接 Codex 运行已完成，因此本次演练中不需要兜底。P1-5 在此次运行之前立即验证了兜底路径：

- 使用 ScriptedMockAdapter 重试完成。
- 为 `apps/demo/src/App.tsx` 生成了差异制品。
- 预览变为健康状态。
- 创建了模拟部署卡片。

### 验证

| 命令 | 结果 |
|---|---|
| `pnpm check` | 通过 |
| `pnpm test` | 通过（89 个测试：21 个 Web + 68 个 API） |
| `git diff --check` | 通过 |

### 已知限制

- 本次演练中，预览和模拟部署未从真实的 Codex 成功运行触发。已验证的 P1-6 范围是真实的 Codex 变更加差异制品。
- Codex 运行耗时约 163 秒，并在完成前发出了重连进度，因此演示仍应保留 ScriptedMockAdapter 兜底可用。

---

## P1-7：真实 Codex 预览和模拟部署演练

**日期：** 2026-05-16

### 修改的文件

| 文件 | 变更 |
|---|---|
| `docs/change-log.md` | 添加了此 P1-7 演练结果。 |

### 修改的函数或区域

未修改任何产品代码。本次演练在 P1-6 成功的真实 Codex 直接启动运行后，使用了现有的预览和部署 API。

### 变更内容

后端、前端、适配器、预览或部署实现均未变更。唯一的变更是记录了从真实 Codex 差异制品到预览和模拟部署的聚焦验证结果。

### 原因

P1-6 已验证：
```text
HTTP Direct Start -> real Codex file mutation -> diff artifact
```
P1-7 验证现有制品路径能否从同一个真实的 Codex TaskRun 继续执行到：
```text
healthy Vite preview -> mock deploy card
```
### 手动验证结果

该演练复用了 P1-6 中成功的真实 Codex 直接启动运行：

- 会话：`a0b51d27-0473-44f3-b079-bbb02fdf00bb`
- Codex 支持的任务：`f9e982c3-df76-4740-b38c-e14e8cb3497c`
- TaskRun：`fa23fb4a-6506-4b0e-a608-3197356d0628`
- 来自真实 Codex 的变更文件：`apps/demo/src/App.tsx`
- Diff 制品 ID：`782e16f4-36b5-46f3-86cf-42c3fb6119e9`
- Diff ID：`5df0273d-f9fc-46b3-bbfa-242d5d185667`

针对该 TaskRun 调用了现有的预览 API：
```text
POST /task-runs/fa23fb4a-6506-4b0e-a608-3197356d0628/preview
```
预览结果：

- 预览 ID：`877daf34-cabe-4ddf-8726-94677ba18831`
- 预览制品 ID：`a14d9194-b198-4d17-a152-79e71cc0590a`
- URL：`http://127.0.0.1:53089`
- 端口：`53089`
- 命令：`pnpm dev --host 127.0.0.1 --port 53089`
- 进程 ID：`32754`
- 健康状态：`healthy`
- 制品状态：`ready`

预览 URL 成功提供了 Vite React HTML 外壳。

针对健康预览调用了现有的模拟部署 API：
```text
POST /previews/877daf34-cabe-4ddf-8726-94677ba18831/deploy
```
部署结果：

- 部署 ID：`9ba427d9-1ea8-454a-8890-e243075fcec7`
- 部署制品 ID：`a623f388-8891-4282-9f7d-6b0074a9152c`
- 提供商：`mock`
- 环境：`preview`
- 状态：`ready`
- 提交 SHA/worktree 引用：
  `9777b992c46ebb52150c19131410c3dfea54c268+worktree`
- URL：
  `https://mock.agenthub.local/deployments/9ba427d9-1ea8-454a-8890-e243075fcec7`
- 部署日志 URI：
  `mock://deployments/9ba427d9-1ea8-454a-8890-e243075fcec7/logs`

此验证：
```text
HTTP Direct Start -> real Codex file mutation -> diff artifact -> healthy Vite preview -> mock deploy
```
预览和部署记录由后端创建并持久化。前端已读取这些持久化的 preview/deployment API，但本次 P1-7 演练直接使用了后端 API 路径，而非通过浏览器 UI 点击操作。

### 兜底验证

本次演练无需使用兜底路径，因为 P1-6 中真实的 Codex 运行已完成并生成了差异。基于兜底的 P0 演示路径仍由现有测试和之前的 P1-5/P1-6 验证覆盖：
```text
forced Codex failure -> ScriptedMockAdapter fallback -> diff -> preview -> mock deploy
```
### 验证

| 命令 | 结果 |
|---|---|
| `pnpm check` | 通过 |
| `pnpm test` | 通过（89 项测试：21 项 Web + 68 项 API） |
| `git diff --check` | 通过 |

### 已知限制

- 此 P1-7 演练通过现有后端 API 触发了预览和部署，而非通过点击浏览器 UI。
- 真实的 Codex 执行仍然依赖于本地 Codex 配额和 CLI 稳定性；请保留 ScriptedMockAdapter 兜底用于演示。

---

## Codex 工作流文档

**日期：** 2026-05-17

### 修改的文件

| 文件 | 变更 |
|---|---|
| `AGENTS.md` | 添加了项目级强制 Codex 规则。 |
| `docs/codex-task-template.md` | 添加了可复用的短提示工作流模板。 |
| `docs/project-state.md` | 添加了稳定的 P0/P1 状态、P1-6/P1-7 证据以及 P1-8 UI 差距。 |
| `docs/change-log.md` | 记录了此纯文档工作流的变更。 |

### 变更内容

将重复的长提示上下文移入稳定的项目文档中：

- `AGENTS.md` 现在为未来的 Codex 工作命名了强制规则，包括最小任务范围、诚实验证声明、保留基于兜底的 P0 演示、避免使用禁止的 non-P0/P1 功能（除非明确要求）、在工程文件变更时更新变更日志，以及除非明确指示，否则不提交或推送。
- `docs/codex-task-template.md` 定义了标准的 read/check/diagnose/edit 工作流和最终响应检查清单。
- `docs/project-state.md` 记录了当前的 P0/P1 状态，包括 P1-6 真实 Codex 直接启动差异验证、P1-7 后端 API preview/deploy 验证以及具体的 P1-7 证据 ID。

### 原因

未来的 Codex 提示现在可以引用这些文档，而无需每次都重复相同的长上下文、约束和收尾要求。

### 范围

仅文档变更。未更改任何应用代码、后端代码、测试、依赖项或运行时行为。

### 验证

| 命令 | 结果 |
|---|---|
| `pnpm check` | 未运行；仅文档变更。 |
| `pnpm test` | 未运行；仅文档变更。 |
| `git diff --check` | 通过 |

### 已知限制

- 此变更未验证任何应用行为。

---

## P1-8：浏览器 UI 预览和模拟部署演练

**日期：** 2026-05-17

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/web/src/app/page.tsx` | 让 `WorkspaceShell` 使用全页宽度，使其自身的右侧预览面板不与健康卡片竞争空间。 |
| `apps/web/src/app/page.test.tsx` | 添加了聚焦的页面布局契约测试。 |
| `docs/project-state.md` | 将 P1-8 从已知差距更新为已验证的浏览器 UI 状态。 |
| `docs/change-log.md` | 记录了此 P1-8 延续。 |

### 修改的函数或区域

- `apps/web/src/app/page.tsx`
  - 将页面内容包装器从 `grid gap-4 md:grid-cols-[1fr_360px]` 更改为 `grid gap-4`。
  - `WorkspaceShell` 已经拥有其内部的 workspace/session/task/preview 列，因此健康卡片现在堆叠在全宽工作区外壳下方。

### 变更内容

浏览器 UI 演练显示，外部页面将 `WorkspaceShell` 约束在健康卡片旁边，而 `WorkspaceShell` 也渲染了一个内部右侧预览面板。这使得任务列变得拥挤，并且使得 preview/deploy 控件在桌面宽度下难以操作。

此修复特意保持较小规模：它仅更改了外部页面布局。现有的任务卡片、差异卡片、预览卡片、部署卡片、API 客户端、后端 preview/deploy API、适配器和制品持久化均未更改。

### 原因

P1-7 验证了通过后端 API 的差异后路径。P1-8 验证了用户在真实的 Codex 直接启动运行产生真实差异制品后，能够通过浏览器 UI 操作相同的差异后路径。

### 手动浏览器验证结果

浏览器 UI 在以下位置打开：
```text
http://127.0.0.1:3000/?session=a0b51d27-0473-44f3-b079-bbb02fdf00bb
```
所选会话复用了来自 P1-6/P1-7 的成功真实 Codex 直接启动运行：

- 会话：`a0b51d27-0473-44f3-b079-bbb02fdf00bb`
- Codex 支持的任务：`f9e982c3-df76-4740-b38c-e14e8cb3497c`
- TaskRun：`fa23fb4a-6506-4b0e-a608-3197356d0628`
- 来自真实 Codex 的变更文件：`apps/demo/src/App.tsx`
- Diff 制品 ID：`782e16f4-36b5-46f3-86cf-42c3fb6119e9`
- Diff ID：`5df0273d-f9fc-46b3-bbfa-242d5d185667`

浏览器 UI 检查：

- 真实 Codex TaskRun 的持久化 diff 卡片已显示。
- diff 卡片展开后，变更文件详情保持可见。
- UI 中的 `Start preview` 按钮创建了一个新的健康 Vite 预览。
- UI 中的 `Open preview` 按钮打开了右侧 iframe 面板。
- iframe 从会话工作树加载了 Vite React 演示。
- UI 中的 `Create deploy card` 按钮创建了一个新的持久化模拟部署卡片。
- 页面刷新后，diff、预览卡片和模拟部署卡片保持可见。

新创建的 UI 预览：

- 预览 ID：`810324d7-2ba9-47e6-b676-7391e87cb131`
- 预览制品 ID：`927f3b23-2bea-43a4-a420-13432ae39064`
- URL：`http://127.0.0.1:64067`
- 端口：`64067`
- 健康状态：`healthy`
- 制品状态：`ready`

新创建的 UI 部署：

- 部署 ID：`58c7812c-31f8-49ee-8b08-28d38264cd87`
- 部署制品 ID：`da95fe77-167e-4df2-9ef4-e2d450fa3bb1`
- 提供商：`mock`
- 环境：`preview`
- 状态：`ready`
- URL：`https://mock.agenthub.local/deployments/58c7812c-31f8-49ee-8b08-28d38264cd87`

这通过浏览器 UI 验证了：
```text
real Codex Direct Start -> diff card -> Start preview -> preview iframe -> Create deploy card
```
### 兜底验证

P1-8 期间无需兜底，因为它复用了 P1-6 中成功的真实 Codex
TaskRun。基于兜底的 P0 演示仍由现有测试和先前验证覆盖：
```text
forced Codex failure -> ScriptedMockAdapter fallback -> diff -> preview -> mock deploy
```
### 验证

| 命令 | 结果 |
|---|---|
| `pnpm check` | 通过 |
| `pnpm test` | 通过（90 项测试：22 项 Web + 68 项 API） |
| `git diff --check` | 通过 |

---

## 运行时设置提供者覆盖保存修复

**日期：** 2026-06-08

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/api/app/agent_runtime_config.py` | 在验证运行时提供者覆盖时，将非规划器 AgentProfile 记录视为 role/capability 模板，同时仍要求所选适配器与所选提供者匹配。 |
| `apps/api/tests/test_agent_runtime_config.py` | 增加了回归覆盖，用于保存使用 Claude Code 提供者的前端 Agent，并拒绝过时的 adapter/provider 负载。 |
| `apps/web/src/components/agent-runtime-settings.tsx` | 当用户更改运行时 Agent 配置文件或提供者时，同步提供者、适配器、模式和可用性。 |
| `apps/web/src/components/runtime-settings-page-client.test.tsx` | 增加了 UI 回归覆盖，用于保存配置了 Claude Code CLI 的前端 Agent。 |

### 变更内容

运行时设置现在可以保存内置角色配置文件（例如 `Frontend Agent`）以及用户选择的编码提供者（例如 `Claude Code CLI`）。所选提供者仍然决定运行时适配器，并且 `adapterType` 与所选提供者不匹配的过时负载仍然无效。

---

## P19 规划器路由加固

**日期：** 2026-06-07

P19 加固了规划器/对话路由器，使得明确的开发请求不再受限于固定的演示模板，也不会被弱 API 提供者的 `assistant_reply` 结果所吞没。

通过 P19-4 完成的变更：

- 统一了 API 规划器提供者和 Claude CLI 规划器的规范提示合约。
- 增加了针对问候语和库管理应用/库存风格前端应用请求的少样本路由示例。
- 要求安全的构建/实现/创建/开发/修改软件请求返回 `task_plan` 并附带完整的 `planDraft`。
- 保留了纯聊天、澄清、拒绝和需要批准的结果作为非执行回复。
- 当 LLM 路由将安全的外部前端编码请求错误分类为 `assistant_reply` 时，增加了确定性兜底。
- 记录了规划器兜底证据，包括 LLM 结果类型、兜底原因、提供者元数据、验证结果、安全错误摘要和创建的任务 ID。
- 增加了 P18c 库管理应用路由回归覆盖，并准备了外部前端目标。
- 确认 missing/unregistered 桌面目标要求进行目标设置，而不是写入任意主机路径。

截至目前验证结果：

- 规划器 contract/provider 测试：通过。
- 规划 misroute/evidence 测试：通过。
- 新颖应用路由测试：通过。
- `pnpm check`：通过。
- `pnpm test`：通过，包括 58 项 Web 测试、440 项 API 测试和 5 项演示 API 测试。
- `pnpm demo:api:test`：通过。
- `git diff --check`：通过。
- `openspec validate agenthub-p19-planner-routing-hardening --strict`：通过。

---

## 最小化 Claude Code 适配器

**日期：** 2026-05-17

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/api/app/claude_code_adapter.py` | 添加了一个最小化的 Claude Code 适配器，使用子进程 cwd 隔离和流式 JSON 解析。 |
| `apps/api/app/main.py` | 添加了 `claude_code` 适配器分发支持。 |
| `claude_code` | 允许通过现有命令防护路径执行受限的 Claude CLI 命令。 |
| `apps/api/app/guardrails.py` | 为命令形状、事件流式传输、持久化和标准化失败添加了假运行器测试。 |
| `apps/api/tests/test_claude_code_adapter.py` | 为 Claude Code CLI 形状添加了命令策略覆盖。 |
| `apps/api/tests/test_guardrails.py` | 记录了当前 Claude Code 适配器的状态和限制。 |
| `docs/project-state.md` | 记录了此实现。 |

### 诊断

现有的适配器合约和 `run_adapter_event_stream` 持久化流程已经支持另一个本地 CLI 适配器。缺失的部分是 Claude 特定的子进程运行器、流式 JSON 事件映射器、错误码标准化、命令防护允许以及针对 `adapterType: claude_code` 的分发支持。

### 变更内容

添加了 `ClaudeCodeAdapter` 作为 `CodexAdapter` 的兄弟。它构建了文档化的命令形状：
```bash
claude --print --verbose --output-format stream-json --include-partial-messages \
  --permission-mode dontAsk --allowedTools Read,Edit,MultiEdit \
  --no-session-persistence --max-budget-usd 1.00 "<instruction>"
```
该过程由 `cwd=<session_worktree_path>` 启动。适配器增量解析 stdout，并将 Claude Code 事件映射为标准化 `task.state`、`message.delta`、`completed` 和 `error` 事件。它会规范化缺失 CLI、需要认证、用量限制、中断、超时、解析错误、护栏拦截以及非零退出失败等情况。

未更改前端 UI、提供商市场、部署行为、Codex 行为或 ScriptedMockAdapter 兜底行为。

### 验证

| 命令 | 结果 |
|---|---|
| `pnpm check` | 通过 |
| `pnpm test` | 通过（133 项测试：25 项 Web + 108 项 API） |
| `git diff --check` | 通过 |

### 已知限制

- 测试仅使用假进程运行器；CI 和本地测试不会调用真实的 Claude Code。
- 未运行或声称任何真实的 Claude 变异。
- 真实的 Claude `stream-json` 输出、权限行为、认证失败文本和用量限制文本仍需在演示使用前获得明确批准的冒烟测试。

---

## P2-7：显式 ClaudeCodeAdapter 冒烟预演

**日期：** 2026-05-18

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/api/app/claude_code_adapter.py` | 为真实的 Claude `--output-format stream-json` 执行添加了必需的 `--verbose` 标志，并映射了真实的 `stream_event` 文本增量。 |
| `apps/api/app/guardrails.py` | 在有界 Claude Code 命令允许列表形状中要求 `--verbose`。 |
| `apps/api/tests/test_claude_code_adapter.py` | 更新了 `--verbose` 的命令形状覆盖范围，并添加了流事件 text/thinking 增量覆盖范围。 |
| `apps/api/tests/test_guardrails.py` | 更新了 `--verbose` 的命令策略覆盖范围。 |
| `docs/project-state.md` | 记录了真实的 Claude 冒烟证据和限制。 |
| `docs/change-log.md` | 记录了本次 P2-7 预演。 |

### 诊断

假运行器适配器实现在结构上是正确的，但首次真实的 Claude Code 冒烟测试揭示了一个具体的 CLI 要求：
```text
Error: When using --print, --output-format=stream-json requires --verbose
```
该失败发生在任何文件变更之前。适配器和护栏命令形态已通过最小修复更新：添加 `--verbose`。
成功的冒烟测试还表明，详细输出包含底层 `stream_event` 记录（包括思考增量），因此适配器现在映射文本增量并过滤思考增量，而不是将其作为原始消息保留。

### 冒烟测试方法

创建了一个分离的可丢弃工作树：
```text
/Users/luotianhang/Desktop/agenthub/.worktrees/claude-smoke-96d46af7-dc74-4d71-a062-c9be42cd1332
```
然后通过后端适配器流程运行了一条微小的真实 `ClaudeCodeAdapter` 指令：
```text
change only the primary action button text in apps/demo/src/App.tsx to "Claude smoke"
```
未运行任何宽泛提示、依赖安装、浏览器 UI 流程或重复变更循环。

### 结果

第一次尝试：

- TaskRun：`c66f1f86-2407-487a-b18f-cf01abd3a7f3`
- 最终状态：`failed`
- 错误代码：`CLAUDE_CODE_EXIT_ERROR`
- 错误消息：
  `Error: When using --print, --output-format=stream-json requires --verbose`
- 文件变更：无

`--verbose` 修复后的第二次尝试：

- 会话：`4cf32311-1a9b-4eda-9ec3-ab0d010691fc`
- 任务：`a5557a9a-99de-4962-9d25-86ed548ea7ca`
- TaskRun：`095ae634-c188-4ffc-a502-53a500d20e14`
- AdapterRun：`claude-code-94cc6074-f15d-4290-b050-c2383363f44d`
- 最终状态：`completed`
- 持久化的适配器事件：337
- Diff 制品：`95bb1d0b-12a3-4a0e-be3e-c07cf1bf79d4`
- 差异：`9f69bc39-6b32-42ca-8a86-cf9fbfa62343`
- 变更的文件：`apps/demo/src/App.tsx`
- 差异统计：1 个文件变更，1 处新增，1 处删除

在一次性工作区中直接执行 git diff 仅显示：
```diff
-            Continue
+            Claude smoke
```
### 验证

| 命令 | 结果 |
|---|---|
| `pnpm check` | 通过 |
| `pnpm test` | 通过（134 项测试：25 项 Web + 109 项 API） |
| `git diff --check` | 通过 |

### 已知限制

- 这仅是一次直接的后端冒烟测试，并非完整的浏览器 UI 执行。
- 仅验证了一个微小的真实 Claude 变更。
- Claude `stream-json` 会输出冗长的底层 `stream_event` 记录；文本增量和思考增量过滤已覆盖，但更广泛的流事件形态仍未验证。
- 真实的身份验证失败和使用限制输出仍未验证。

---

## P2-8：Claude Code 直接启动选择

**日期：** 2026-05-18

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/api/app/task_runs.py` | 为基于 codex 的 frontend/backend 编码代理添加了 `AGENTHUB_DEFAULT_CODE_ADAPTER` 选择。 |
| `apps/api/tests/test_task_runs.py` | 增加了对 Claude 默认选择、显式适配器保留、非代码适配器保留以及无效环境变量值的覆盖。 |
| `docs/project-state.md` | 记录了 P2-8 选择行为及当前限制。 |
| `docs/change-log.md` | 记录了本次 P2-8 实现。 |

### 诊断

正常的直接启动通过 `create_task_run()` 创建 TaskRun，除非端点传递了显式适配器，否则会使用已分配代理存储的 `adapter_type`。种子化的前端和后端代理使用 `codex`，因此即使在最小化的 `ClaudeCodeAdapter` 可用后，正常的演示执行仍默认使用 Codex。

### 变更内容

新增了一个 environment/config 开关：
```bash
AGENTHUB_DEFAULT_CODE_ADAPTER=claude_code
```
设置后，frontend/backend 中存储的适配器为 `codex` 的编码代理将使用 `adapterType: claude_code` 创建新的 TaskRun。未设置时，行为保持不变。
显式适配器选择仍然优先，因此强制的 Codex 失败和回退到 ScriptedMockAdapter 的重试机制继续正常工作。包括 `scripted_mock` 在内的非编码适配器不受此环境变量的影响。

未添加前端 UI 选择器、提供商市场、种子重写、Codex 移除或 ScriptedMockAdapter 行为变更。

### 验证

| 命令 | 结果 |
|---|---|
| `pnpm check` | 通过 |
| `pnpm test` | 通过（137 个测试：25 个 Web + 112 个 API） |
| `git diff --check` | 通过 |

### 已知限制

- P2-8 未运行另一个真实的 Claude 变异测试；P2-7 仍然是真实的 Claude 烟雾测试证据。
- 选择方法基于环境。浏览器可见的提供商选择器仍不在范围内。

---

## P2-9：Claude 默认适配器模式文档

**日期：** 2026-05-18

### 修改的文件

| 文件 | 变更 |
|---|---|
| `docs/demo-script.md` | 记录了如何以 Claude Code 作为默认编码适配器启动 API，以及如何在演示中展示该模式。 |
| `docs/project-state.md` | 记录了 P2-9 直接启动选择的证据和剩余限制。 |
| `docs/change-log.md` | 记录了本次 P2-9 文档和演练结果。 |

P2-9 未更改任何应用代码、适配器代码、后端 API 行为、前端 UI、提供商市场或测试行为。

### 诊断

P2-8 添加了选择机制，但演示脚本尚未告知未来的操作员如何以 Claude 默认模式启动 AgentHub。使用 `AGENTHUB_DEFAULT_CODE_ADAPTER=claude_code` 的浏览器直接启动也尚未手动演练过。

### 变更内容

演示脚本现在记录了：
```bash
AGENTHUB_DEFAULT_CODE_ADAPTER=claude_code pnpm dev:api
```
它还区分了已验证的级别：

- P2-7 验证了直接的后端真实 Claude 变更和差异制品。
- P2-8 验证了测试中基于环境变量的选择。
- P2-9 验证了当环境变量设置时，Direct Start 会创建一个 `claude_code` TaskRun。
- 通过 diff/preview/deploy 进行的完整浏览器 UI Claude 默认执行仍未演练。

### 最小化演练

使用 `AGENTHUB_DEFAULT_CODE_ADAPTER=claude_code` 运行了一次内存中的 API Direct Start 检查。该请求未启动真实的 Claude；它仅验证了选择层。

证据：

- 端点：`POST /tasks/{task_id}/runs`
- 响应状态：`201`
- 会话：`1c662ede-d0be-4349-8c86-20f49be6fb53`
- 任务：`c28cda5b-67c7-44a8-bd2b-e43ebbc64217`
- TaskRun：`a1c191ea-1414-4746-95ca-d6c51b36b4f8`
- 适配器类型：`claude_code`
- 状态：`queued`
- 排队事件负载：`{"adapterType":"claude_code","state":"queued"}`

### 验证

| 命令 | 结果 |
|---|---|
| `pnpm check` | 通过 |
| `pnpm test` | 通过（137 个测试：25 个 Web + 112 个 API） |
| `git diff --check` | 通过 |

### 已知限制

- P2-9 未运行真实的 Claude 执行。
- 通过 diff/preview/deploy 进行的完整浏览器 UI Claude 默认执行仍未演练。
- P2-7 仍然是真实的 Claude 变更和差异制品证据。

---

## P2 最终冻结审查

**日期：** 2026-05-18

### 修改的文件

| 文件 | 变更 |
|---|---|
| `docs/demo-script.md` | 更新了引言，包含 P2 稳定化和 Claude 默认模式说明。 |
| `docs/p2-roadmap.md` | 协调了原始 P2 计划与最终完成的 P2 状态及剩余注意事项。 |
| `docs/project-state.md` | 记录了 P2 最终冻结审查结果。 |
| `docs/change-log.md` | 记录了本次冻结审查。 |

在 P2 最终冻结审查期间，未更改任何应用代码、适配器代码、后端 API 行为、前端行为、测试或依赖项。

### 审查结果

审查的文档与当前 P2 状态保持一致：

- P2 稳定化工作已完成至 P2-9。
- P1 真实的 Codex Direct Start 和基于兜底的 P0 路径保持不变。
- Claude 默认模式已通过 `AGENTHUB_DEFAULT_CODE_ADAPTER=claude_code` 记录。
- 剩余注意事项可见：
  - 通过 diff/preview/deploy 进行的完整浏览器 UI Claude 默认执行未演练
  - 真实的 Claude 认证失败和使用限制输出仍未完全验证
  - 广泛的任意自然语言编辑仍不在范围内
  - 生产部署仍不在范围内

### 验证

| 命令 | 结果 |
|---|---|
| `pnpm check` | 通过 |
| `pnpm test` | 通过（137 个测试：25 个 Web + 112 个 API） |
| `git diff --check` | 通过 |

---

## P2-3：自然语言二次变更编排

**日期：** 2026-05-17

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/api/app/planning.py` | 添加了确定性后续意图解析和单任务前端后续规划。 |
| `apps/api/app/main.py` | 为主按钮和演示标题文本变更添加了有界后续任务指令。 |
| `apps/api/app/scripted_mock.py` | 扩展了兜底适配器以应用确定性的按钮和标题文本更新。 |
| `apps/api/tests/test_planning.py` | 添加了后续解析和规划覆盖。 |
| `apps/api/tests/test_task_runs.py` | 为后续按钮和标题变更添加了任务运行指令覆盖。 |
| `apps/api/tests/test_scripted_mock_adapter.py` | 添加了兜底变更和二次差异连续性覆盖。 |
| `docs/project-state.md` | 记录了 P2-3 已验证状态和演练证据。 |
| `docs/change-log.md` | 记录了本次 P2-3 实现。 |

### 根本原因

在 P2-3 之前，规划仅识别初始的 `@orchestrator build a login page for the demo app` 流程。同一会话中的后续消息（例如 `把按钮文案改成 Sign in`）不会创建聚焦的后续任务。兜底适配器也为其按钮更新路径使用了固定副本，因此无法确定性地应用请求的二次变更文本。

### 变更内容

P2-3 为演示安全的后续文本变更添加了一个小的 rule/template 层：

- 主按钮文本变更，包括英文和中文措辞
- 演示 heading/title 文本变更，包括英文和中文措辞

当现有会话已有任务时，受支持的后续请求会创建一个分配给种子前端代理的前端任务。该任务依赖于最新的现有任务，将 `planJson` 限制在 `apps/demo/src/App.tsx` 范围内，并通过正常的 TaskRun 生命周期重用现有会话的工作树。

未添加通用的自主规划器、任意自然语言编辑、新适配器、preview/deploy 重新设计、前端重新设计或提供商工作。

### 手动验证

使用本地 API 和一个隔离的演练会话：

- 会话：`d65fc331-39f2-432b-9828-89723b9f3c32`
- 初始前端任务：`3f7f6f65-9f72-4add-ab0a-c9a944dc3b23`
- 初始兜底 TaskRun：`607ad185-8eb2-4158-8219-e124880e68a7`
- 初始差异制品：`c83c21d5-dad8-4d56-b0b8-cf1bc9de2bc3`
- 初始预览：`511ee0ca-e0dc-4054-8775-e487e81f7303`
- 后续请求：`把按钮文案改成 Sign in`
- 后续任务：`3ce6aa3d-97bf-4e16-b85a-33676e62bef2`
- 后续兜底 TaskRun：`7a4f5763-ebbe-4d51-a207-b36b1fff7091`
- 后续差异制品：`f1ca4318-0b41-48a8-9b27-acb957448734`
- 后续预览：`551aa58f-ab73-49f3-96c2-e6db8994bdd6`
- 后续预览健康状态：`healthy`

后续任务复用了同一个会话工作区，为 `apps/demo/src/App.tsx` 生成了第二个差异，刷新后的预览恢复健康。执行通过 `ScriptedMockAdapter` 兜底而非真实 Codex 验证，以避免此任务期间的配额依赖。

### 验证

| 命令 | 结果 |
|---|---|
| `pnpm check` | 通过 |
| `pnpm test` | 通过（123 个测试：25 个 Web + 98 个 API） |
| `git diff --check` | 通过 |

### 已知限制

- P2-3 仅有意支持狭窄的 button/title 文本变更请求。
- 此任务中未演练后续任务的真实 Codex 执行。
- 第二次变更后的浏览器 iframe 刷新未单独演练；预览刷新通过后端预览 API 验证。

---

## P2-4：验证第二次变更后的浏览器预览 iframe 刷新

**日期：** 2026-05-17

### 修改的文件

| 文件 | 变更 |
|---|---|
| `docs/project-state.md` | 记录了 P2-4 浏览器演练证据和当前限制。 |
| `docs/demo-script.md` | 将过时的第二次变更说明替换为已验证的狭窄后续流程。 |
| `docs/change-log.md` | 记录了此 P2-4 验证结果。 |

P2-4 未更改任何应用代码、后端代码、前端代码、适配器代码、测试或依赖项。

### 诊断

预览刷新路径已具备所需的 UI 行为：

- `Start preview` 为选定的 TaskRun 创建新的后端预览，并将该预览设置为右侧面板 iframe。
- `Open preview` 为右侧面板选择持久化的预览卡片。
- `Refresh preview` 重新读取选定 TaskRun 的持久化预览状态，并在选定的预览属于该运行时更新 iframe 键。

剩余的 P2-3 差距在于验证，而非缺失产品代码。来自早期会话的持久化预览卡片可能比其本地 Vite 进程存活更久，因此 P2-4 在浏览器演练期间使用了全新的 `Start preview` 操作。

### 手动验证

通过浏览器 UI 交互验证：
```text
initial task -> ScriptedMockAdapter fallback -> first diff -> Start preview -> iframe at first preview URL -> follow-up text change -> ScriptedMockAdapter fallback -> second diff -> Start preview -> iframe refreshed to second preview URL
```
证据：

- 会话：`cb653482-c31a-48da-a8ee-31ed8cd367e3`
- 初始前端任务：`5f2c26c2-6511-4b8f-b359-b9de5c9e5a50`
- 初始兜底 TaskRun：`cfeff131-8cbf-4bcc-95b9-1aa84dbf5130`
- 初始差异制品：`737085ee-7b73-4715-8303-df64b3a14132`
- 初始预览：`c077ba2d-7bd4-4c49-8e0c-313e2ecd641c`
- 初始预览 URL：`http://127.0.0.1:61087`
- 后续请求：`把按钮文案改成 Sign in`
- 后续任务：`0f9ff26c-8216-4489-b71a-3628c1a7ab7a`
- 后续兜底 TaskRun：`f8d78651-5347-43de-8553-12b29c8c3647`
- 后续差异制品：`b48b3b33-feb2-4313-805d-89811a5cb51c`
- 后续预览：`44ea9495-04b5-419a-ba64-0701eaa83ec8`
- 后续预览 URL：`http://127.0.0.1:61292`

右侧预览面板的 iframe 从 `http://127.0.0.1:61087` 变为
`http://127.0.0.1:61292`。后续预览状态正常，且以顶层页面打开同一 URL 后，显示了更新后的 `Sign in` 按钮。由于当前应用内浏览器运行时不支持跨域 iframe 的直接 DOM 检查，因此 iframe 内容通过视觉检查和顶层预览 URL 进行了验证。

### 验证

| 命令 | 结果 |
|---|---|
| `pnpm check` | 通过 |
| `pnpm test` | 通过（123 个测试：25 个 Web + 98 个 API） |
| `git diff --check` | 通过 |

### 已知限制

- P2-4 执行未使用真实的 Codex；浏览器排练使用了可靠的强制失败加 `ScriptedMockAdapter` 兜底路径。
- 广泛的任意自然语言编辑仍不在范围内。

---

## P2-5：添加 GitHub Actions CI

**日期：** 2026-05-17

### 修改的文件

| 文件 | 变更 |
|---|---|
| `.github/workflows/ci.yml` | 添加了拉取请求和推送 CI 工作流。 |
| `docs/project-state.md` | 记录了 P2-5 CI 状态。 |
| `docs/change-log.md` | 记录了此 P2-5 实现。 |

P2-5 未更改任何应用代码、后端代码、前端代码、适配器代码、测试行为、部署、Docker 或生产发布工作流。

### 诊断

手动验证反复使用：
```text
pnpm check
pnpm test
git diff --check
```
API 检查与测试脚本期望在 `.venv/bin/python` 处存在仓库本地的 Python 虚拟环境，因此 CI 需要在调用现有 pnpm 脚本之前创建该虚拟环境。

### 变更内容

新增了一个极简的 GitHub Actions 工作流，在 `pull_request` 和 `push` 时触发。该工作流会检出仓库、安装 pnpm 10.33.4、配置 Node.js 22 和 Python 3.11、通过 `pnpm install --frozen-lockfile`, installs API dependencies into `.venv` 安装 JavaScript 依赖，然后运行：
```text
pnpm check
pnpm test
git diff --check
```
### 验证

| 命令 | 结果 |
|---|---|
| `pnpm check` | 通过 |
| `pnpm test` | 通过（123 项测试：25 项 Web + 98 项 API） |
| `git diff --check` | 通过 |

### 已知限制

- 该工作流已通过语法检查和以下本地验证命令在本地完成验证；尚未在 GitHub Actions 上运行。

---

## Claude Code 适配器可行性说明

**日期：** 2026-05-17

### 修改的文件

| 文件 | 变更 |
|---|---|
| `docs/claude-code-adapter-notes.md` | 添加了本地 Claude Code CLI 可行性发现及未来适配器设计说明。 |
| `docs/change-log.md` | 记录了本次仅限文档的调查。 |

未更改任何应用代码、后端行为、前端行为、适配器实现、测试行为或运行时配置。

### 检查内容

适配器架构：

- `apps/api/app/adapters.py`
- `apps/api/app/codex_adapter.py`
- `apps/api/app/scripted_mock.py`
- `apps/api/app/main.py`

安全的 Claude CLI 命令：
```bash
which claude
claude --version
claude --help
claude -p --help
claude auth --help
claude auth status
```
未执行任何真实的提示或文件变更。

### 结果

Claude Code CLI 已在此机器上安装并完成身份验证：

- 二进制文件：`/Users/luotianhang/.npm-global/bin/claude`
- 版本：`2.1.143 (Claude Code)`
- 身份验证状态：`loggedIn: true`，`authMethod: api_key_helper`

帮助输出表明，非交互式执行可通过
`--print`/`-p` 使用，机器可读输出可通过
`--output-format json` 或 `--output-format stream-json` 获取，并且指令可以
作为位置参数传递。未观察到直接的 `--cd` 选项，因此
未来的适配器应将子进程的 `cwd` 设置为 `Session.worktreePath`。

暂定的未来命令格式：
```bash
claude --print --output-format stream-json --include-partial-messages \
  --permission-mode dontAsk --allowedTools "Read,Edit,MultiEdit" \
  --no-session-persistence --max-budget-usd <small-budget> "<instruction>"
```
使用子进程运行 `cwd=<session_worktree_path>`。

### 验证

| 命令 | 结果 |
|---|---|
| `git diff --check` | 通过 |

### 已知限制

- 未捕获真实的 `stream-json` 输出。
- 未运行任何消耗配额的命令。
- 使用限制和未认证失败模式在实现前仍需 real/fake-process 测试覆盖。
- 在任何支持写入的适配器声明之前，权限模式和工具允许列表行为需要有限度的冒烟测试。

---

## P2 路线图规划

**日期：** 2026-05-17

### 修改的文件

| 文件 | 变更 |
|---|---|
| `docs/p2-roadmap.md` | 添加了 P2 稳定性路线图。 |
| `docs/change-log.md` | 记录了本次仅涉及文档的规划变更。 |

未更改任何应用代码、后端代码、前端代码、适配器代码、测试或依赖项。

### 变更内容

创建了 P2 范围计划，重点关注 P1 冻结后的稳定性、已知注意事项和演示可靠性。路线图包含：

- 当前 P1 最终验证状态
- 剩余的 P1 注意事项
- 即时的 P2 任务顺序
- 每个提议任务的目标、范围、受影响的模块、验收标准、验证方法和非目标
- 明确推迟的前端重新设计

### 提议的 P2 任务顺序

1. P2-1 修复区域设置水合警告。
2. P2-2 审批卡片 UI/rehearsal.
3. P2-3 自然语言二次机会编排。
4. P2-4 GitHub Actions CI。
5. P2-5 演示重置/清理状态辅助工具。

### 验证

| 命令 | 结果 |
|---|---|
| `git diff --check` | 通过 |

---

## P2-1：修复区域设置特定的水合警告

**日期：** 2026-05-17

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/web/src/lib/date-format.ts` | 添加了从类似 ISO 的时间戳文本生成确定性紧凑时间戳格式的功能。 |
| `apps/web/src/lib/date-format.test.ts` | 添加了与区域设置无关格式化的单元测试覆盖。 |
| `apps/web/src/components/workspace-shell.tsx` | 将运行时区域设置的会话时间戳格式替换为确定性格式化。 |
| `apps/web/src/components/preview-card.tsx` | 将运行时区域设置的预览检查时间格式替换为确定性格式化。 |
| `apps/web/src/components/preview-card.test.tsx` | 将预览时间戳断言更新为确定性文本。 |
| `docs/change-log.md` | 记录了本次 P2-1 实现。 |

### 根本原因

`workspace-shell.tsx` 和 `preview-card.tsx` 使用了
`new Intl.DateTimeFormat(undefined, ...)`，它会选择当前的运行时
区域设置。在开发 SSR/hydration 期间，服务器以一种区域设置渲染会话日期，
而浏览器以另一种区域设置进行水合，导致文本不匹配，例如
`May 17, 02:06 AM` 与 `5月17日 02:06`。

### 变更内容

P2-1 添加了 `formatCompactDateTime`，它根据源组件格式化类似 ISO 的时间戳，
而不是依赖运行时区域设置默认值。会话列表、所选会话元数据和预览检查时间戳现在渲染稳定的文本，例如：
```text
May 17, 02:06
```
未修改后端 API、任务运行生命周期行为、preview/deploy 逻辑或前端布局。

### 验证

| 命令 | 结果 |
|---|---|
| `pnpm check` | 通过 |
| `pnpm test` | 通过（92 项测试：24 项 Web + 68 项 API） |
| `git diff --check` | 通过 |

### 手动验证

在 `http://127.0.0.1:3000` 处打开并重新加载了 AgentHub UI，该 UI 连接至 `http://127.0.0.1:8000` 处的本地 API。会话列表、选定会话元数据、后端健康卡片和预览面板均成功渲染，且之前特定于语言环境的 hydration 覆盖层未出现。会话时间戳渲染为确定性的紧凑文本，例如 `May 17, 02:06`。

### 已知限制

- 格式化程序有意设计为紧凑且带有英文标签，以确保本地演示渲染的确定性。这并非完整的国际化系统。

---

## P2-2：验证并最小化完成审批卡片 UI/Rehearsal

**日期：** 2026-05-17

### 修改的文件

| 文件 | 变更 |
|---|---|
| `apps/api/app/schemas.py` | 添加了审批 request/decision API 模式，并在 TaskRun 响应中暴露了可选的审批负载。 |
| `apps/api/app/main.py` | 添加了最新的审批请求映射以及 approve/deny TaskRun 端点。 |
| `apps/api/app/guardrails.py` | 修复了对于不包含后续子命令的命令的 `git -C <path>` 解析，保留了白名单行为。 |
| `apps/api/tests/test_task_runs.py` | 为可见的审批负载和 approve/deny 端点添加了 API 覆盖。 |
| `apps/api/tests/test_events.py` | 使用真实的日期时间值保持了新的 SSE 事件测试的确定性。 |
| `apps/api/tests/test_guardrails.py` | 现有的本地防护边缘情况测试现在能通过解析器修复。 |
| `apps/web/src/lib/api.ts` | 添加了审批请求类型和 approve/deny API 客户端辅助函数。 |
| `apps/web/src/lib/api.test.ts` | 为 approve/deny 调用添加了 API 客户端覆盖。 |
| `apps/web/src/components/task-card-list.tsx` | 为 `waiting_approval` 运行添加了一个紧凑的审批卡片。 |
| `waiting_approval` | 添加了审批卡片渲染和操作覆盖。 |
| `apps/web/src/components/task-card-list.test.tsx` | 通过现有的任务刷新流程连接了审批操作。 |
| `apps/web/src/components/workspace-shell.tsx` | 记录了 P2-2 验证状态和演练证据。 |
| `docs/project-state.md` | 记录了本次 P2-2 实现。 |

### 诊断

后端已经具备核心的 P0 审批原语：`ApprovalRequestPayload`、`request_task_run_approval`、`approve_task_run` 和 `deny_task_run`。适配器事件也可以将运行转换为 `waiting_approval` 状态。产品 API 未暴露最新的审批负载，没有公开的 approve/deny 端点，并且前端将 `waiting_approval` 视为仅带有中断控制的通用活动运行。

### 变更内容

TaskRun API 响应现在仅在运行处于 `waiting_approval` 状态时包含 `approvalRequest`。前端将该负载渲染为一个小型审批卡片，显示审批类型、请求的操作、risk/reason 以及存在的 command/path 详细信息。批准和拒绝复用现有的防护服务方法，并刷新选定的任务列表。

未添加企业级 RBAC、策略管理、提供商市场、生产部署审批、前端重新设计或新的审批持久化实体。

### 手动验证

使用了隔离的本地演练会话：

- 会话：`67421999-3b16-44c4-ade3-98cb31331549`
- 已批准的 TaskRun：`5653e8f9-0057-478f-913c-ac25b4484216`
- 拒绝演练 TaskRun：`54bde1de-b9f7-4f2b-9357-98d51b3675c7`

浏览器 UI 渲染了一个 `product_confirmation` 审批卡片，并且“批准”按钮将该运行从 `waiting_approval` 状态移至 `queued` 状态。为第二个运行渲染了一个 `security_approval` 审批卡片；backend/API 测试覆盖了拒绝转换，前端测试覆盖了“拒绝”按钮的接线。

### 验证

| 命令 | 结果 |
|---|---|
| `pnpm check` | 通过 |
| `pnpm test` | 通过（116 项测试：25 项 Web + 91 项 API） |
| `git diff --check` | 通过 |

### 已知限制

- 审批决议仅更新 TaskRun 状态；它不会自动恢复适配器执行。这对于当前的审批卡片演练已足够，并将 scheduler/orchestrator 行为排除在范围之外。
- 在手动演练期间，浏览器自动化的“拒绝”点击不可靠，因此拒绝操作通过 backend/API 测试和前端按钮接线测试进行验证，而非完整的浏览器点击。

### 已知限制

- P1-8 复用了 P1-6 中成功的真实 Codex TaskRun，而不是再执行一次 Codex 运行。
- 浏览器 UI 验证涵盖了差异后制品控件。在 P1-8 期间未从浏览器重新运行 Codex。
- 真实的 Codex 执行仍然依赖于本地 Codex 配额和 CLI 稳定性；请保留 ScriptedMockAdapter 兜底方案以供演示使用。

---

## P1-9：演示就绪性与可复现性检查

**日期：** 2026-05-17

### 修改的文件

| 文件 | 变更 |
|---|---|
| `docs/demo-script.md` | 更新了主演示路径以反映真实的浏览器 UI Codex 流程，并将强制失败路径移至兜底演示路径。 |
| `docs/project-state.md` | 新增 P1-9 干净启动排练状态与证据。 |
| `docs/change-log.md` | 已记录此 P1-9 结果。 |

### 变更内容

文档已更新以匹配当前浏览器 UI 演示行为：

- 主演示路径现在在本地 Codex 可用时，在前端实现任务上使用 `Start run`。
- 强制 Codex 失败加 ScriptedMockAdapter 路径仍作为可靠的兜底路径记录。
- `docs/project-state.md` 现在记录干净启动的 P1-9 证据。

P1-9 未涉及产品代码、后端代码、适配器代码、preview/deploy 服务或依赖项的变更。

### 原因

P1-8 使用一次成功的现有 Codex 运行验证了浏览器 UI 的差异后控制功能。P1-9 则验证全新的浏览器演示能否从干净的 backend/frontend 启动复现完整路径。

### 干净启动手动验证结果

后端和前端已使用文档中记录的命令重启：
```bash
pnpm dev:api
pnpm dev:web
```
浏览器 UI 已在以下位置打开：
```text
http://127.0.0.1:3000
```
全新启动流程：

1. 从 UI 创建了一个新会话。
2. 发送了 `@orchestrator build a login page for the demo app`。
3. 在前端实现任务上点击了 `Start run`。
4. 通过活动状态观察了 Codex 运行进度。
5. 确认运行已完成。
6. 确认差异卡片已出现。
7. 点击了 `Start preview`。
8. 确认右侧 iframe 面板中打开了健康的 Vite 预览。
9. 点击了 `Create deploy card`。
10. 重新加载页面，确认差异、预览和部署卡片仍然可见。

证据：

- 会话：`666fa20b-6f54-4342-b844-39594b903da3`
- 任务：`c90396af-1b9f-42f4-a6dd-9daa4f3913f6`
- TaskRun：`b1882cda-47f6-4035-b12d-ba3d72d67939`
- 适配器：`codex`
- 最终 TaskRun 状态：`completed`
- 错误 code/message：无
- 基础引用：`ad9136f91fe9776c33e839359a2203d64fbbf322`
- 头引用：`ad9136f91fe9776c33e839359a2203d64fbbf322+worktree`
- 差异：`8a0155a6-b865-4cee-987e-82d773b9f20e`
- 差异制品：`c832b249-c2c3-444c-ac97-6b3e811e5c70`
- 变更文件：`apps/demo/src/App.tsx`
- 差异统计：1 个文件变更，14 处新增，4 处删除
- 预览：`b363eb09-7251-4b8e-a5b4-3c59775b58b7`
- 预览制品：`f93ebc25-b8c7-47e9-ac11-aeee777c604e`
- 预览 URL：`http://127.0.0.1:51763`
- 预览 health/status：`healthy`，`ready`
- 部署：`d97e447a-c8d0-41b7-95f8-e40008d83eb0`
- 部署制品：`d85e9bcf-9b92-4c3c-958a-352f855e59a9`
- Provider/environment/status：`mock`，`preview`，`ready`
- 部署 URL：
  `https://mock.agenthub.local/deployments/d97e447a-c8d0-41b7-95f8-e40008d83eb0`

这验证了：
```text
clean start -> real Codex Direct Start -> diff card -> Start preview -> preview iframe -> Create deploy card
```
### UI 就绪说明

- 核心标签对于 judge/demo 场景足够清晰：`Start run`、运行历史、`Start preview`、`Open preview` 和 `Create deploy card`。
- 可见的活动状态简单但足够：当 Codex 运行时，运行显示为 `queued`/`streaming`，并带有 `Interrupt` 控件。
- 如果 Codex 不可用、未认证、使用受限或速度过慢，基于兜底的 P0 演示仍然是安全路径。

### 兜底验证

在 P1-9 期间未使用兜底路径，因为真实的 Codex 已完成运行。基于兜底的 P0 演示仍由现有测试和先前验证覆盖：
```text
forced Codex failure -> ScriptedMockAdapter fallback -> diff -> preview -> mock deploy
```
### 验证

| 命令 | 结果 |
|---|---|
| `pnpm check` | 通过 |
| `pnpm test` | 通过（90 项测试：22 项 Web + 68 项 API） |
| `git diff --check` | 通过 |

### 已知限制

- 真实的 Codex 执行仍然依赖于本地 Codex 配额和 CLI 稳定性。
- P1-9 未重置 SQLite 数据库或删除现有的工作树；它重新启动了 backend/frontend 进程，并从 UI 创建了一个新的会话。

---

## P1-10：演示冻结与最终验收检查清单

**日期：** 2026-05-17

### 修改的文件

| 文件 | 变更 |
|---|---|
| `docs/p1-acceptance-checklist.md` | 添加了最终冻结的 P1 验收检查清单。 |
| `docs/project-state.md` | 将 P1 演示基线标记为冻结，并链接了检查清单。 |
| `docs/change-log.md` | 记录了此 P1-10 冻结结果。 |

### 变更内容

P1 现在已被记录为以下内容的冻结本地演示基线：
```text
real Codex Direct Start -> diff card -> Start preview -> preview iframe -> Create deploy card
```
新的验收清单记录了已完成的能力、具体证据、验证状态、已知未验证项、已知风险、基于兜底的 P0 状态、明确排除在范围外的项，以及推荐的下一阶段。

P1-10 未更改任何应用代码、后端代码、适配器代码、测试、preview/deploy 服务或依赖项。

### 原因

P1-9 证明了演示可以从干净的 backend/frontend 启动中重现。P1-10 冻结了该状态，以便后续工作拥有稳定的演示基线，并清晰记录已验证的内容、仍存在的风险以及排除在范围外的内容。

### 冻结基线

冻结的 P1 路径：
```text
real Codex Direct Start -> diff card -> Start preview -> preview iframe -> Create deploy card
```
冻结证据来自 P1-9 冷启动演练：

- 会话：`666fa20b-6f54-4342-b844-39594b903da3`
- TaskRun：`b1882cda-47f6-4035-b12d-ba3d72d67939`
- 差异制品：`c832b249-c2c3-444c-ac97-6b3e811e5c70`
- 预览：`b363eb09-7251-4b8e-a5b4-3c59775b58b7`
- 部署：`d97e447a-c8d0-41b7-95f8-e40008d83eb0`
- Provider/status：`mock`、`ready`

基于兜底的 P0 路径仍保留：
```text
forced Codex failure -> ScriptedMockAdapter fallback -> real diff -> healthy Vite preview -> mock deploy card
```
### 验证

| 命令 | 结果 |
|---|---|
| `pnpm check` | 通过 |
| `pnpm test` | 通过（90 项测试：22 项 Web + 68 项 API） |
| `git diff --check` | 通过 |

### 已知未验证项

- P1-9 未重置 SQLite 数据库或删除现有工作树。
- 基于兜底的 P0 在 P1-9 期间未手动重新运行，因为真实的 Codex 已完成；它仍受测试和先前验证的覆盖。
- 自然语言的二次变更编排仍是一个已记录的注意事项。
- 审批卡片 UI 不属于冻结的 P1 评判路径的一部分。

### 已知风险

- 真实的 Codex 执行依赖于本地 CLI 的可用性、身份验证、配额和 CLI 稳定性。
- Codex 运行时长可能不同，因此 ScriptedMockAdapter 兜底应随时准备好用于演示。
- 预览的健康状况取决于设置时的演示依赖项。

---

## P1-11：干净状态与兜底演练

**日期：** 2026-05-17

### 修改的文件

| 文件 | 变更 |
|---|---|
| `docs/project-state.md` | 记录了干净的 SQLite 演练、新的会话工作树证据以及兜底演练证据。 |
| `docs/p1-acceptance-checklist.md` | 将干净状态和手动兜底就绪项标记为已验证。 |
| `docs/change-log.md` | 记录了此 P1-11 演练结果。 |

P1-11 未更改任何应用代码、后端代码、前端代码、适配器代码、测试或依赖项。

### 备份/重置方法

- 将活动的 SQLite 数据库移至
  `/tmp/agenthub-p1-11-backup-20260517-095901/agenthub.sqlite3.before-p1-11`。
- 记录了演练前的 Git 工作树注册表和目录清单，位于：
  - `/tmp/agenthub-p1-11-backup-20260517-095901/worktree-list-before.txt`
  - `/tmp/agenthub-p1-11-backup-20260517-095901/worktree-dirs-before.txt`
- 保留现有的 `.worktrees` 检出，以避免干扰 Git 已注册的工作树元数据。
- 使用 `pnpm db:init` 重新初始化了一个干净的 SQLite 数据库。
- 在演练期间通过 UI 创建了新的会话级工作树。

### 干净状态演练

已验证路径：
```text
clean SQLite -> fresh session worktree -> real Codex Direct Start -> real diff -> healthy Vite preview -> mock deploy card
```
证据：

- 会话：`72668a90-74a0-45c6-a0c4-98e8cfa54c27`
- 任务：`7e0a4e97-1b80-404d-bcab-4616418627e3`
- TaskRun：`4c92132f-3c89-47cc-b8a4-3f1395825c39`
- 差异：`bb45131e-42f8-47d7-88eb-c8126d694b0a`
- 差异制品：`243ce682-748b-42ad-9354-dd8eed1f3e67`
- 预览：`a30d07e2-470c-4614-a864-c21ac0b52363`
- 预览 URL：`http://127.0.0.1:58634`
- 部署：`448b7d91-5064-43c2-a849-3e89634e14bd`
- Provider/status：`mock`, `ready`

### 兜底演练

已验证路径：
```text
forced Codex failure -> ScriptedMockAdapter fallback -> real diff -> healthy Vite preview -> mock deploy card
```
证据：

- 会话：`695287ed-2967-4360-8520-a5fdc1be46e3`
- 任务：`1a790664-c817-42eb-a953-d7c0f11cccb0`
- 失败的 Codex TaskRun：`1b50d047-0c08-4ff2-a4d7-12412b36f786`
- 失败运行错误码：`CODEX_DEMO_FORCED_FAILURE`
- 兜底 TaskRun：`c35d52f5-bf27-4656-aee1-b0321eb2bd96`
- 差异：`8a8f05bf-6559-44f4-bafc-fb87881c4750`
- 差异制品：`91b6c898-bf2b-4c0c-b44b-f6a236a72ef0`
- 预览：`e1be7c11-1cc7-42f9-8441-62c7eb0a1b92`
- 预览 URL：`http://127.0.0.1:59152`
- 部署：`cb8c7f95-42f7-4213-8273-4201500bf8b3`
- Provider/status：`mock`, `ready`

重新加载后，浏览器 UI 仍然显示了失败的 Codex 运行、兜底运行、差异、预览和部署卡片。

### 验证

| 命令 | 结果 |
|---|---|
| `pnpm check` | 通过 |
| `pnpm test` | 通过（90 个测试：22 个 Web + 68 个 API） |
| `git diff --check` | 通过 |

---

## 可靠执行平台：通用新项目路径

**日期：** 2026-06-10

### 变更内容

- 新增 selected empty folder provisioning apply 路径：用户选择空目录后，AgentHub 会创建通用 `frontend/` Vite React TS、`backend/` FastAPI、`docs/api-contract.md`、`README.md` 和 `agenthub.project.json`。
- provisioning 成功后注册 role-scoped external frontend/backend targets，并把当前 Session 的 active frontend/backend target 指向新 target。
- planner 在 Session 已绑定 external active targets 时优先使用真实 target 边界，番茄钟、Todo、读书笔记等请求走同一条通用 fullstack routing，不走 Pomodoro 特化。
- provisioned target 继续经过 PlanValidator、ProjectProfile command policy、session queue、target lock 和 run diagnostics；旧的 force failure / fallback retry 入口已收口到共享 scheduler path，避免直接绕过 queue/lock 执行 adapter。
- 运行设置页面增加“新建全栈项目”流程，后端返回的 `plan + registeredTargets + session` 作为 UI 绑定来源。
- 修复中文 `新建全栈项目` 只注册 frontend target 的问题；`全栈` 现在会触发 backend target。若目录已被 AgentHub scaffold 但只注册了部分 target，再次 apply 会复用匹配的已注册 target 并补注册缺失 target。

### 验证

- 新增/更新 API 测试覆盖 provisioning、planner routing、PlanValidator、target lock release 和 fallback scheduler path。
- 新增/更新 Web 测试覆盖 provisioning API client 和运行设置 UI flow。

### 已知限制

- 现有已注册的 `.worktrees` 检出未被移动或删除。P1-11 通过备份 SQLite 数据库并从干净的数据库创建新的会话级工作树，验证了干净的应用程序状态。
- 真实的 Codex 执行仍然依赖于本地 CLI 的可用性、身份验证、配额和 CLI 稳定性。

---

## P1 最终冻结审查

**日期：** 2026-05-17

### 修改的文件

| 文件 | 变更 |
|---|---|
| `README.md` | 将过时的 P0 直接启动说明更新为已验证的 P1 直接 Codex 状态，并添加了 P1 reset/restore 注释。 |
| `docs/demo-script.md` | 添加了 P1-11 恢复细节和非阻塞区域设置水合警告说明。 |
| `docs/project-state.md` | 添加了恢复注释和最终冻结审查摘要。 |
| `docs/p1-acceptance-checklist.md` | 添加了最终冻结审查验证槽和区域设置水合警告说明。 |
| `docs/change-log.md` | 记录了本次冻结审查。 |

最终冻结审查未更改任何应用程序代码、后端代码、前端代码、适配器代码、测试或依赖项。

### 变更内容

审查发现来自 P0 冻结时代的一个过时的 README 说明：它仍然声称 `Start run` UI 仅创建一个已排队的 TaskRun，并且完整的制品路径仅用于兜底。这在 P1 之后已不再正确。README 现在与 P1 已验证的状态一致：
```text
Start run -> real Codex Direct Start -> real diff -> healthy Vite preview -> mock deploy card
```
文档现在也明确说明了 P1-11 的 SQLite 恢复方法，以及在 P1-11 期间观察到的非阻塞的特定区域水合警告。

### 冻结审查结果

- P1-11 已提交至 `faca556`。
- 当前没有标签指向 P1-11 HEAD。
- 只要以下验证保持绿色，P1 即可准备冻结。
- 剩余注意事项可见：
  - 自然语言二次变更编排仍是一个注意事项
  - 审批卡片 UI 不在已冻结的 P1 裁判路径内
  - 生产部署不在范围内
  - 观察到了特定区域的开发水合警告，但未阻塞演练

### 验证

| 命令 | 结果 |
|---|---|
| `pnpm check` | 通过 |
| `pnpm test` | 通过（90 个测试：22 个 Web + 68 个 API） |
| `git diff --check` | 通过 |
