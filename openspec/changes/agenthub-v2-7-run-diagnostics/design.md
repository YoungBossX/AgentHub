## 总体设计

V2.7 在现有 TaskRun、TaskRunEvent、SessionExecutionLedger、Review、Diff、
Preview、Deployment 和 MissionTrace 之上增加一个诊断投影层。它不负责执行
任务，也不改变 adapter、scheduler、preview 或 deploy 的真实行为；它负责把
已有事件、状态、错误码和制品证据归一化成用户可理解的运行诊断。

目标响应形态：
```text
TaskRun + TaskRunEvent + artifacts + scheduler/provider/preview/deploy evidence
  -> RunDiagnosticsService
  -> failure classification
  -> run timeline
  -> health summary
  -> next-step suggestions
  -> safe API/UI view
```
V2.7 应优先复用已有数据源。只有在现有事件缺少必要信息时，后续实现才补充小型诊断事件或 metadata 字段；不得为了诊断而重写执行内核。

## 诊断边界

### 输入

Run Diagnostics 可以读取：

- TaskRun 状态、error code、started/completed 时间、adapter metadata；
- TaskRunEvent 的 phase、message、metadata、timestamp；
- provider gateway 结果、fallback 证据和 provider availability；
- scheduler readiness、dependency、queue、target lock、approval 信息；
- diff/review/preview/deploy artifacts；
- SessionExecutionLedger 和 MissionTrace 中已有的执行摘要。

### 输出

诊断输出应分为四个层次：

- 顶层摘要：状态、最可能失败分类、严重级别、是否可重试、用户可读说明。
- Run Timeline：按时间排序的阶段事件，带来源、状态和安全详情。
- Health Summary：provider、queue、lock、preview、deploy 等子系统健康信号。
- Next-step Suggestions：基于分类生成的可行动建议，例如重试、检查 provider auth、释放锁、查看 preview 日志、修改需求或等待审批。

### 非目标

V2.7 不做：

- 分布式 tracing、指标系统或外部 observability 集成；
- 自动修复 provider 配额、认证或部署配置；
- 自动 stash/discard dirty worktree；
- 自动绕过 approval、validation、lock 或 protected path；
- 新 adapter、新 provider marketplace、Docker sandbox、WebSocket 或 PR 创建；
- 将 fallback 成功伪装成真实 provider 成功。

## Failure 分类

诊断分类需要稳定、可测试、可本地化。建议最小集合：

- `provider_auth`：缺少或无效 provider 凭证。
- `provider_quota`：provider 限流、配额耗尽或付款/计划限制。
- `provider_unavailable`：provider binary/API 不可用、配置缺失或健康检查失败。
- `adapter_timeout`：max runtime 或 idle timeout。
- `adapter_interrupted`：用户或系统中断。
- `adapter_error`：adapter 返回未知非零退出或无法解析错误。
- `queue_stale`：worker lease 过期、stale recovery 或服务重启导致失败。
- `queue_blocked`：依赖、approval 或调度条件未满足。
- `lock_timeout`：target lock 长时间不可用或锁恢复失败。
- `worktree_dirty`：工作树状态阻止安全执行、diff 应用或收集。
- `validation_failed`：PlanValidator、policy、target registry 或命令/路径规则拒绝。
- `approval_denied`：用户拒绝审批或审批过期。
- `preview_failed`：build/dev server/health check/iframe preview 失败。
- `deploy_failed`：本地 staging 或 mock-backed deploy 失败。
- `deploy_blocked`：外部部署 provider 未配置或需要手动交接。
- `artifact_collection_failed`：diff/review/artifact 收集失败。
- `unknown`：缺少足够证据时的保守分类。

分类逻辑应保留 raw error code，但 UI 主显示用户可读分类和说明。若多个问题同时存在，诊断应区分：

- `primaryFailure`：导致 TaskRun 终态失败的主因；
- `contributingFactors`：后处理或环境中的相关问题；
- `downstreamImpact`：被阻塞的后续任务、preview 或 deploy。

## Run Timeline

Run Timeline 是用户理解“跑到哪一步坏了”的主界面。事件应按时间排序，并尽量映射到以下 phase：

- `queued`
- `scheduler_check`
- `dependency_wait`
- `lock_wait`
- `approval_wait`
- `validation`
- `provider_check`
- `worker_claim`
- `adapter_start`
- `adapter_stream`
- `adapter_finish`
- `artifact_collection`
- `diff`
- `review`
- `preview`
- `deploy`
- `finalize`
- `recovery`

每个 timeline item 应包含：

- stable id；
- timestamp；
- phase；
- status：pending、running、success、warning、failed、skipped；
- title；
- short description；
- source：task_run、event、provider、scheduler、artifact、preview、deploy；
- safe metadata；
- 可选 artifact reference。

timeline 不应暴露 raw secrets、tokens、完整受保护 host path 或未脱敏日志。长日志只展示摘要，并链接到已有安全制品或事件详情。

## Health Summary

Health Summary 用于回答“系统哪一段不健康”。V2.7 至少覆盖：

- Provider：provider id、adapter type、auth/config 状态、availability、fallback 是否发生、真实 provider 是否成功。
- Queue：queued 时长、worker claim、lease、heartbeat、stale/recovery 状态。
- Lock：target id、lock owner、等待时长、是否 timeout。
- Preview：preview status、port/url 是否可用、build/dev server/health check 摘要。
- Deploy：provider、environment、status、blocked/failed/ready、source preview 或 artifact 关联。

健康状态使用小集合：`healthy`、`degraded`、`blocked`、`failed`、`unknown`。没有证据时应显示 unknown，而不是推断成功。

## Next-step Suggestions

建议必须来自诊断分类，不应是泛泛的“请重试”。示例：

- provider_auth：检查 runtime settings 中对应 provider 凭证，或切换到可用 fallback adapter。
- provider_quota：等待配额恢复、换 provider、或使用 ScriptedMock fallback 继续 demo，但明确它不是真实 provider 成功。
- adapter_timeout：重试更小范围任务、查看 adapter stream、检查是否卡在安装或长命令。
- worktree_dirty：查看 diff，确认是否继续、重试或创建新 Session。
- validation_failed：修改需求或目标，避免受保护路径/命令。
- approval_denied：重新请求审批或调整任务范围。
- preview_failed：打开 preview 日志，修复构建错误后重试 preview。
- deploy_blocked：完成 provider 配置或选择 manual handoff/local staging。

建议应包含：

- action id；
- label；
- description；
- kind：retry、open_settings、open_artifact、request_approval、change_request、choose_fallback、wait、manual_handoff；
- enabled/disabled 与原因；
- 可选目标链接或 artifact id。

V2.7 只定义建议模型和 UI，不要求实现所有动作的一键自动修复。

## API 与 UI

后续实现可以采用窄 API，例如：

- `GET /task-runs/{task_run_id}/diagnostics`
- `GET /sessions/{session_id}/run-diagnostics-summary`

若现有 TaskRun 详情 API 已足够，也可将诊断嵌入现有响应，但必须保持字段稳定、脱敏和向后兼容。

前端展示建议：

- Task card 上显示诊断摘要 badge，而不是只有 failed/errorCode；
- 右侧 panel 增加 Run Timeline 和 Health Summary；
- preview/deploy 卡片失败时链接到同一个诊断视图；
- mission panel 中对失败任务显示“最可能原因”和“下一步”。

UI 不应把诊断写成教程或营销说明；应像开发工具一样紧凑、可扫描、可操作。

## 数据安全

诊断层必须复用既有安全边界：

- 不暴露 raw secrets、API keys、tokens；
- 不暴露受保护 host paths；
- 不将 `.env`、`node_modules`、`secrets/` 或系统路径写入可见诊断；
- 不展示 provider 原始 stderr 中的敏感片段；
- 不声称未验证的真实成功。

## 测试策略

V2.7 后续实现应覆盖：

- classification 单元测试；
- timeline 构建测试；
- health summary 构建测试；
- API 脱敏与 backward compatibility 测试；
- 前端失败诊断渲染测试；
- provider auth/quota/unavailable、timeout、worktree dirty、lock timeout、validation failed、approval denied、preview failed、deploy blocked/failed 的场景测试；
- strict OpenSpec validation 与 freeze review。
