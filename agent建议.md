# AgentHub 架构抽象分析：AGENTHUB_REUSE_SUGGESTIONS

下表把公司项目中的做法抽象为 AgentHub 可以采用的工程思想。

| 公司项目中的工程做法 | 可以抽象成什么思想 | AgentHub 中怎么落地 | 需要注意的风险 |
|---|---|---|---|
| Maven 多模块但单 Jar 部署：`dataflow-web` 聚合 `modules/core/dao/domain/entity/common` | 模块化单体优先 | 先做 `agenthub-web` + `agenthub-modules` + `agenthub-core` + `agenthub-domain` + `agenthub-dao`，不要过早微服务化 | 模块边界容易被跨层依赖破坏，需要依赖方向约束 |
| `dataflow-web` 只做启动、拦截器、响应包装、日志切面 | Web Shell / API Gateway 内置化 | `agenthub-web` 只处理 auth、context、response、exception、trace，不写业务编排 | 壳层过厚会变成“上帝模块”，业务逻辑要下沉 |
| `AuthenticationInterceptor` 解析 token 并注入 `DFAccount` | 请求上下文自动注入 | 注入 `RequestContext(tenantId, workspaceId, userId, roles, traceId)` | 异步任务不能依赖 request，需要持久化 context snapshot |
| `DynamicDataSource.switchDataSource(account.poolName)` | 租户隔离与上下文路由 | workspace/tenant 级逻辑隔离，必要时演进到 schema/db 隔离 | 物理多库运维复杂；先明确数据隔离级别 |
| `PermissionManager` + `PermConfigManager` + Casbin | 资源动作权限模型 | 对 Agent、Run、Artifact、ToolCredential 建 `resource + action + role` policy | Agent 自动执行工具时必须二次鉴权，否则容易越权 |
| 创建资源后自动给 root/创建者 owner | 资源生命周期内置授权 | 创建 Agent/Run/Workspace/Artifact 时自动 grant owner/member | 授权回收要和资源删除、成员移除联动 |
| `ControllerResponseHandler` 自动包装成功响应 | 统一 API envelope | 返回 `code/message/data/traceId`，前端统一处理 | SSE、文件下载、流式输出需要跳过自动包装 |
| `GlobalExceptionHandler` + 错误码枚举 | 可预期错误治理 | 定义 validation/auth/policy/provider/tool/runtime/quota 错误码 | 错误码不要无限膨胀，保持领域分类 |
| DTO/VO/Req/Enum/ErrorCode 集中在 `dataflow-entity` | API contract 与领域对象分离 | 建 `agenthub-contract`：REST req/res、状态枚举、错误码、event DTO | Contract 包不能反向依赖业务 service |
| MapStruct mapper：Req -> DTO -> VO | 显式数据转换层 | AgentHub 中用 mapper 转换 API model、domain model、provider DTO | 过度 mapper 会增加样板，小项目可先手写关键转换 |
| `DatasourceServiceImpl` 调 SDK 创建资源，再写本地 `DFDatasource` 与 `DFDataSummary` | 外部资源和本地资源双写映射 | Tool/Provider/KnowledgeBase 注册时，外部 asset 创建成功后保存本地 Resource + Summary | 双写失败要有补偿或幂等重试 |
| `ExternalPublishRepository` 保存 `externalDataId -> dataId` | 幂等导入映射 | 建 `external_resource_mapping(provider, external_id, internal_id)` | 外部 ID 变更、删除、权限变化要能同步 |
| `ConnectorRequestServiceImpl` 封装 URL、签名、请求、响应类型 | Gateway 隔离协议细节 | ProviderGateway/ToolGateway/ConnectorGateway 统一封装外部 API | 不要让业务 service 直接拼 HTTP 请求 |
| `ExternalServiceImpl` 把外部连接器数据转换为内部资源 | Anti-corruption Layer | 外部工具、知识库、数据集统一转 AgentHub Resource/Artifact | 外部模型字段可能不稳定，转换层要容错 |
| `ConfigManager` 聚合配置并初始化 SDK/账号/数据源 | 启动编排与配置聚合 | 启动顺序：DB -> tenant config -> provider registry -> scheduler -> worker recovery | 全静态 ConfigManager 难测，建议拆成小配置 bean |
| `application.yaml` 大量 env override | 环境配置外置 | 用 env/profile 管理 provider、runtime、queue、storage 配置 | 密钥不能直接写入 repo，要接 secret manager |
| `DataImportCacheManager` 按配置选择 memory/db 实现 | 配置化策略实现 | `RunCache`、`ToolResultCache`、`CredentialCache` 支持 memory/redis/db | 开发/生产实现差异可能掩盖并发问题 |
| `ExecutorServiceProvider`、`ForkJoinPoolProvider` | 共享执行池 | 为工具调用、索引、后台小任务配置命名线程池 | 无界 cached thread pool 对 AgentHub 风险较大，应加限流 |
| `DFSystemTask` + Quartz + `DFSystemTaskLog` | 可持久化后台任务 | `SystemTask` 管理清理、索引、同步、巡检、评估任务 | Quartz 不等于实时任务队列，Run worker 不建议只靠 Quartz |
| `JobExecutor` 模板方法处理 execute/afterExecute/日志/状态 | Worker 执行模板 | `RunExecutor` / `StepExecutor` 统一写状态、日志、指标、失败原因 | afterExecute 失败不能污染主任务结果，要分级处理 |
| `AppReadyEventListener` 启动后恢复任务并加分布式锁 | 崩溃恢复与单主启动任务 | worker 启动后恢复未完成 Run，scheduler 用分布式锁防重复扫描 | 锁过期和进程挂起会造成双执行，要设计 lease |
| Disruptor `BizEventData` + 多 handler | 事件总线解耦副作用 | `DomainEvent` 驱动审计、通知、指标、memory indexing、artifact indexing | 进程内事件不可靠，关键事件用 outbox + durable queue |
| `SchemaInitializedEvent` 表示数据库初始化完成 | 生命周期事件 | `DatabaseReadyEvent`、`ProviderRegistryReadyEvent`、`WorkerReadyEvent` | 启动事件顺序要可测试、可观测 |
| `SBEInitiatorServiceImpl` 用状态枚举推进沙箱任务 | 业务状态模型 | Run/Step/Approval/ToolCall 都有状态枚举 | 状态转移散落会失控，建议集中到 `StateTransitionService` |
| `SBETaskPartnerStageEnum` 区分数据配置、算法审核、结果审核 | 多参与方协作阶段 | Multi-agent run 分为 planning、execution、review、approval、handoff | 阶段和状态不要混用，阶段表示流程位置，状态表示当前结果 |
| `sbeTaskRecordService.addRecord` 写任务操作记录 | Timeline / Operation Log | Run timeline 记录创建、成员变化、工具调用、审批、结果产物 | 用户可见日志与安全审计日志要分开 |
| `WebLogAspect` 记录 URL、参数、用户、耗时 | 请求级可观测性 | HTTP、Run、Step、ToolCall 全链路 trace | 工具参数可能含密钥/隐私数据，必须脱敏 |
| 审计模块 + `OpLogEventHandler` 异步写日志 | 审计与主流程解耦 | 审计事件异步消费，失败进入重试/死信 | 审计不能只在内存队列，合规场景要保证落盘 |
| 连接器同步失败 catch 后继续处理下一条 | 批处理容错 | 外部资源同步逐条隔离失败，记录失败项，下一轮重试 | 静默跳过会难排查，要暴露 sync report |
| `SyncFinished` 线程轮询等待同步表出现 | 同步-异步桥接 | 用户发起资源创建后，可返回 pending 状态并由后台事件更新 | 不建议长时间阻塞 HTTP；AgentHub 更适合异步完成 |
| `sandboxStatusReportService.taskReport` 上报任务信息 | 外部平台状态同步 | Run 状态可同步到 Slack/GitHub/企业系统 | 外部上报失败不能影响核心状态推进 |
| `dataflow-miniapp` 作为可选扩展业务包 | 插件化业务模块 | AgentHub 插件包：评估、审批、企业知识库、第三方工具集 | 插件不能直接访问核心表，最好通过接口/事件 |
| `dataflow-sso` 独立模块 | 身份适配可插拔 | OIDC/SAML/企业微信/飞书等身份模块化 | 登录态、租户绑定、外部账号映射要统一 |
| `scripts/init_dataflow_orgs.sh` 与初始化 SQL | Tenant provisioning 自动化 | `agenthub tenant create` 初始化 workspace、roles、default agents、quotas | 初始化脚本必须幂等 |
| Dockerfile + start/stop/status 脚本 | 简单可运维交付 | API 和 Worker 分镜像，健康检查、日志、配置挂载标准化 | 单 Jar 简单，但长任务与 API 混跑会影响稳定性 |

## 建议的 AgentHub 初版模块图

```text
agenthub-web
  -> auth/context/response/exception/trace

agenthub-modules
  -> agents
  -> runs
  -> tools
  -> approvals
  -> artifacts
  -> workspaces
  -> audit

agenthub-core
  -> scheduler
  -> worker
  -> eventbus
  -> policy
  -> provider-gateway
  -> tool-gateway
  -> memory/resource-manager

agenthub-domain
  -> Agent
  -> Run
  -> Step
  -> ToolCall
  -> Artifact
  -> Workspace
  -> Credential
  -> AuditLog

agenthub-dao
  -> repositories / query views

agenthub-contract
  -> req / dto / vo / enum / errorcode / event dto

agenthub-common
  -> config / id / time / crypto / retry / lock / trace utilities
```

## 推荐优先级

1. 先落地统一上下文、统一响应、错误码、权限模型。
2. 再落地 Run/Step/ToolCall 的状态机和执行日志。
3. 然后做 Provider/Tool Gateway，把外部系统隔离起来。
4. 最后引入事件总线和后台调度，把审计、通知、索引、评估从主流程拆出。

最重要的取舍：AgentHub 的核心不是“更多模块”，而是把 Agent 运行过程做成可恢复、可审计、可授权、可替换外部 provider 的平台内核。
