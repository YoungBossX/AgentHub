# Fixed Validation Containers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为两个内置固定验证配置增加可选 Docker 执行路径，保留三种 Adapter、默认 native 行为和所有既有数据。

**Architecture:** 在 TaskRun 验证协调器下选择 native 或 Docker；共享受限源码捕获，使用两个不可变镜像执行固定命令。容器产物通过有界字节协议交给原生浏览器检查；沿用事件、QA 和启动身份，不更改模型 Adapter 或数据库结构。

**Tech Stack:** FastAPI / SQLModel / SQLite、Python 标准库 subprocess/threading/file locks、Docker CLI/Linux containers、Node 22、Python 3.12、现有 TypeScript/Vite/Node/ASGI harness、现有 React/TypeScript QA UI。

**Spec:** [OpenSpec design](../../../openspec/changes/agenthub-container-validation/design.md)；[requirements](../../../openspec/changes/agenthub-container-validation/specs/container-validation/spec.md)。

状态：2026-10-18 用户已批准设计和 Native 顺序实施；代码基线 main `8392b7f`。
先完成实现，环境由用户稍后准备；不安装、不提交或推送。真实 Docker 验收仍未完成。

## Global Constraints

- 默认 `AGENTHUB_VALIDATION_BACKEND=native`；允许值仅 native/docker。
- Docker 只承接内置 demo-frontend / demo-backend 的上述固定配置。
- CodexAdapter、ClaudeCodeAdapter、ScriptedMockAdapter 的协议、参数、权限和路由不变。
- 不改 models.py、固定 migration、seed、数据库 URL、已有 Agent/Workspace 设置。
- 预览、Provider CLI 与浏览器需求检查仍在原生路径；不新增端口映射。
- 单容器固定：10001:10001、init=true、只读根、network none、cap-drop ALL、no-new-privileges、
  默认 seccomp、1 CPU、1024 MiB 内存及同等 memory-swap、128 PID。
- /work tmpfs 512 MiB、/tmp tmpfs 64 MiB；nosuid/nodev/noexec。
- 每阶段 60 秒、Profile 180 秒、管理调用 10 秒；每 daemon/用户容量 1、等待 30 秒。
- 每阶段公开日志 12,000 字节；导出最多 512 文件、32 MiB 解码、单文件 5 MiB、
  48 MiB 传输、深度 16。
- 执行 pull=never；无运行时安装、自由 shell、远程 daemon、宿主敏感路径或 socket 挂载。
- 一次执行一个 OpenSpec 任务。任务结束只记录检查点；未单独授权不得 git commit/push。
- 测试一律用外部临时库/工作树；不使用产品数据库或以删除数据清理失败。
- 新增 API 文件无 import-time daemon 操作；pure doctor 不导入 app.db 或创建数据库。
- 文件列表为原计划；当前实现和未验收范围以 tasks/verification 与下列勾选状态为准。

## Review Focus

1. Docker context 在运行中变化或被环境变量覆盖：冻结本地 endpoint，任何远程或错绑都拒绝（1.2、1.4）。
2. 数据库终态 runner_id/锁行变化：用冻结启动绑定核对历史回执，不能误借/误废弃证据（1.5）。
3. 取消发生在 create 成功、记 ID 前或导出中：有可恢复 journal，不留失控容器或误删别人的资源（1.4、1.6）。
4. 导出带 Windows ADS、大小写冲突、巨型 base64 或篡改摘要：限量解析、独占写入、绝不覆盖（1.4）。
5. 没 Docker 的旧安装与旧 JSON 回执：默认路径不触碰 daemon/数据，显示历史环境缺失；配置变更只读过期（1.2、1.5、1.6）。

## File structure and interfaces

| 文件/目录 | 责任 |
|---|---|
| apps/api/app/validation_inputs.py（新） | 两个目标的纯源码/可信配置捕获，复用既有路径与文件预算 |
| apps/api/app/validation_policy.py（新） | 类型、固定预算、执行绑定与后端选择；无 DB/daemon 副作用 |
| apps/api/app/sandbox_cli.py（新） | 只读 doctor、显式 prepare/verify 开发者入口 |
| apps/api/app/container_runtime.py（新） | Docker argv、执行/日志限额、inspect 和精确取消 |
| apps/api/app/container_lifecycle.py（新） | 容量文件锁、私有 journal、归属及崩溃窗口恢复 |
| apps/api/app/container_exports.py（新） | 有界 JSON/base64 和独占目录物化 |
| apps/api/app/docker_validation.py（新） | 固定 Profile 调用顺序和结果组装 |
| apps/api/app/validation_browser.py（新） | 原生浏览器检查的公共封装，不扩大浏览器能力 |
| apps/api/app/validation_process.py（新） | 固定验证自有进程的 POSIX group / Windows Job Object 生命周期；不改 Adapter |
| containers/validation/（新） | 两个 Dockerfile、依赖/recipe 锁、固定 Node/Python 控制程序 |
| automatic_validation.py / backend_validation.py | 保留 facade 和 runner 注入；连接源码捕获与新分支 |
| qa_assessment.py / qa-evidence.tsx / lib/api.ts | 增量回执身份校验和最小环境展示 |
| scripts/sandbox.sh / package.json | 开发者包装；不进入 Agent 命令允许列表 |
| .github/workflows/container-validation.yml（新） | 明确手动触发的真实容器验证，默认 CI 不变 |

1.2 定义公共类型，后续任务不得自行换名：
- `SourceSnapshot(target_id: str, profile: str, files: Mapping[str,str], contents: Mapping[str,bytes], source_fingerprint: str, policy_inputs: Mapping[str,str])`，冻结 dataclass；先复制再以只读 MappingProxyType 包装，规范摘要时转为普通 dict，不共享可变输入。
- `ValidationIdentity(task_run_id: str, adapter_run_id: str, execution_attempt_id: str, generation_fingerprint: str)`，摘要来自已验证的 taskRunExecutionAccessBinding。
- `ImageBinding(image_id: str, recipe_fingerprint: str, platform: str, context_name: str)`。
- `ExecutionBinding(backend: Literal["native","docker"], profile: str, image: ImageBinding | None, policy_fingerprint: str, operation_id: str)`。
- `FixedValidationRequest(snapshot: SourceSnapshot, identity: ValidationIdentity, execution: ExecutionBinding)`。
- `ProfileExecutionResult(status: str, commands: list[dict], execution: dict, output_fingerprint: str | None)`；
  status 只用既有 passed/failed/cancelled/stale/unavailable/incomplete。
- `DockerValidationBackend.execute(request: FixedValidationRequest, cancelled: threading.Event, *, export_dir: Path) -> ProfileExecutionResult`。
- 阻塞后端不接收 DbSession、ownership_guard 或任意用户 argv。DB 与监督检查仍由 run_automatic_validation 所在线程处理。

下文 Files 中 Python 应用文件的短名均位于 `apps/api/app/`，API 测试短名均位于
`apps/api/tests/`；其余文件使用显式仓库路径。这是文件映射约定，不允许创建同名根文件。

---

## Task 1.2: 输入/策略边界、原生兼容与只读 doctor

**Files**
Create: validation_inputs.py、validation_policy.py、sandbox_cli.py、scripts/sandbox.sh。
Modify: apps/api/app/config.py、automatic_validation.py、backend_validation.py、package.json、
AGENTS.md（只增加服务器固定验证专项例外）、docs/change-log.md。
Test: apps/api/tests/test_validation_policy.py、test_sandbox_doctor.py、
已有 test_automatic_validation.py / test_backend_validation.py。

**Interfaces**
Consumes: 设计中的两个 Profile 及现有文件捕获/路径 guards。
Produces: 上述冻结类型；`capture_profile_inputs(root: Path, profile: str) -> SourceSnapshot`；
`resolve_backend_settings() -> dict`；
`bind_execution(snapshot: SourceSnapshot, identity: ValidationIdentity, settings: dict) -> ExecutionBinding`（纯本地策略冻结）；
`doctor(*, context_name: str | None, image_ids: dict[str,str]) -> dict`。
保留公开 capture/validate facade 默认 native 和 runner 参数；doctor 的 readiness 不含隔离证明。

- [x] 写红灯：test_native_without_docker_never_spawns_cli、test_invalid_backend_is_not_native、
  test_doctor_does_not_import_db_or_mutate_daemon、test_remote_or_overridden_context_refused、
  test_docker_capture_does_not_require_host_node_or_host_python_package_metadata。
- [x] 锁定 doctor 断言：schemaVersion=agenthub.container_doctor.v1、
  status=metadata_ready/unavailable/unsupported、runtimeIsolationVerified=false，
  静态准备成功才返回退出码 0；所有失败不创建数据库/容器或自动启用 native。
- [x] 用独立进程测试 doctor 的 import/调用前后 app.db、数据库文件和 Docker mutation argv；
  用 mock CLI info/context JSON 覆盖 Windows named pipe、Unix socket、TCP/SSH 和未知 OS/架构。
- [x] Run: `pnpm test:api tests/test_validation_policy.py tests/test_sandbox_doctor.py -q`；
  预期相关新接口缺失而失败，不能只保留收集错误。
- [x] 实现 Settings 三个 image/context 配置项及 backend 选择，image ID 用严格 sha256 格式，
  Docker 必须显式配置 contextName，缺少时 unavailable，不跟随默认 context；
  Docker 未选择时不做任何 image/context 探测。分离源码 bytes 与 native/Docker policy，
  保持既有大小写、链接、配置、512/16 MiB 和签名兼容。
- [x] 实现只读 doctor：10 秒调用超时、最小受信 Docker 客户端环境、受支持平台 Linux/amd64、
  配方标签与本地 image inspect。不存在 Docker/镜像给结构化 unavailable；不自动修复。
- [x] 增加仅开发者 `sandbox:doctor` 包装；AGENTS 专项例外仍不允许 Agent 调 Docker。
- [x] Run: 上述新测试及 `pnpm test:api tests/test_automatic_validation.py tests/test_backend_validation.py -q`；
  预期全通过、旧 runner 测试仍有效；记录新 facade 的 native 行为及当前不可用 doctor 输出。
- [x] 更新当前任务记录/变更日志；按已批准的 Native 顺序进入下一任务，不自动提交。

## Task 1.3: 两个可信镜像和显式准备

以下代码/单元步骤完成；2026-10-19 用户准备 E 盘 Docker 后已开始实际构建，
后端不可变 image ID 已实际核验，前端下载未完成，OpenSpec 1.3 仍未完成。
操作记录见专项 verification；完整 native 回归2712 pass/17 skip，不替代真实资格。

**Files**
Create: containers/validation/frontend.Dockerfile、backend.Dockerfile、
recipe-lock.json、backend-requirements.lock、frontend-control.mjs、backend-control.py。
Modify: sandbox_cli.py、scripts/sandbox.sh、package.json、docs/sandbox-options.md、docs/change-log.md。
Test: apps/api/tests/test_sandbox_prepare.py；
containers/validation/control.test.mjs；apps/api/tests/test_container_control.py。

**Interfaces**
Consumes: SourceSnapshot、ImageBinding、固定资源/阶段枚举。
Produces: `prepare_images(output_dir: Path) -> dict`；
`pnpm sandbox:prepare --output <新建外部目录>`。
两个控制程序共享 prepare/check/build/test/export/hold 协议；backend 不支持 build；
export 返回设计规定的 agenthub.container_export.v1。

- [x] 写红灯：test_build_context_contains_only_trusted_inputs、test_prepare_refuses_existing_or_managed_output、
  test_prepare_does_not_send_user_source_or_env、test_image_binding_uses_built_id_not_tag、
  test_control_rejects_arbitrary_stage_or_path、test_host_dependency_symlink_is_never_mounted。
- [x] Run: `pnpm test:api tests/test_sandbox_prepare.py tests/test_container_control.py -q` 和
  `node --test containers/validation/control.test.mjs`；确认缺失能力对应失败。
- [x] 由官方镜像源查询两个受支持补丁版本及 linux/amd64 repo digest，写入 recipe-lock.json；
  Python 锁固定 FastAPI 0.121.3、HTTPX 0.28.1 的所有传递依赖及 wheel 哈希。
  实施时记录真实解析来源/结果，不能用 latest、范围版本或假 digest 占位。
- [x] 构建 context 只复制根/demo package、workspace/lock、必要 patches 和固定 harness；
  不发送整个 checkout、宿主 node_modules 或任何目标源码。前端 frozen pnpm 10.33.4 安装，
  后端 pip --require-hashes；仅镜像准备阶段允许下载。
- [x] 控制程序在只读镜像中；hold 有 180 秒生命周期，prepare 复制 /input 到 /work，
  Node 依赖链接只指向镜像内位置。阶段映射只允许原可信 harness 和固定参数，
  不运行目标脚本/pytest/config；export 限制和摘要与设计一致，拒绝异常后台进程。
- [x] 实现准备命令的独占外部回执：基础 digest、recipe/锁/harness 哈希、实际 build/inspect
  image ID、平台和客户端 context。不自动写 .env 或修改选中的 Adapter。
- [x] Run 新增单元测试。若用户已准备 Docker，再在新外部目录实际构建/inspect 两个镜像；
  未具备环境时保留“镜像准备未验收”，不伪造完成状态或擅自安装。
- [x] 更新记录后顺序继续；本任务不触发新 TaskRun 或修改数据库。

## Task 1.4: 受限 runtime、归属清理和产物导出

**Files**
Create: container_runtime.py、container_lifecycle.py、container_exports.py、docker_validation.py。
Test: apps/api/tests/test_container_runtime.py、test_container_lifecycle.py、
test_container_exports.py、test_docker_validation.py。
Modify: docs/change-log.md。

**Interfaces**
Consumes: 1.2 请求/类型，1.3 控制程序与 ImageBinding。
Produces:
`DockerRuntime.create(request, input_dir: Path) -> OwnedContainer`、
`exec_stage(owned, stage: str, cancelled: Event) -> dict`、
`export_bytes(owned, cancelled: Event) -> bytes`、
`cleanup(owned) -> None`；
`OwnedContainer(container_id: str, operation_id: str, context_name: str, journal_path: Path)`；
`acquire_validation_slot(context_fingerprint: str, cancelled: Event)` 上下文管理器；
`materialize_export(raw: bytes, destination: Path, expected_source: str, *, expected_files: Mapping[str,str]) -> str`（返回输出摘要）。
DockerValidationBackend.execute 实现公共签名；所有原始 argv 构造只在 DockerRuntime 内。

- [x] 写 test_runtime_uses_exact_profile_flags_and_no_shell、test_mount_csv_metacharacters_refused、
  test_runtime_does_not_inherit_credentials_or_remote_context，断言固定 flags、pull=never、
  单一只读输入挂载及禁止的命令/环境，空格和中文路径仍保持单个 argv。
  写 test_runtime_deadlines_and_bounded_logs，覆盖
  stage 60/Profile 180/CLI 10/等待 30 秒、每阶段 12,000 字节且持续排空日志。
  写 test_exec_exit137_without_daemon_evidence_is_not_confirmed_oom，防止错误诊断。
- [x] 写 test_capacity_is_cross_process_and_cancellable、test_crashed_owner_releases_os_slot_but_requires_cleanup，
  覆盖跨进程容量 1（不是线程 semaphore）、等待期间取消、OS 锁在进程退出后释放；
  遗留容器未核验清理时下一个验证不得开始。
- [x] 写 test_cleanup_crash_windows_with_matching_journal、test_reused_pid_or_foreign_labels_never_cleanup、
  test_context_drift_blocks_exec_or_cleanup，覆盖 create 已成功但记 ID 前崩溃、start/exec/导出异常、PID 复用、
  label/image/mount 不符、context 漂移、未知 journal；不误删外部资源、不调用 prune。
- [x] 写 test_export_rejects_invalid_envelope_or_budget、test_export_paths_are_portable_and_exclusive、
  test_export_source_hashes_cover_exact_copied_inputs，覆盖重复 JSON 键、base64/摘要错误、
  总传输/解码/文件数/深度、链接、NFC/大小写冲突、Windows 设备名/尾部点空格、
  ../、盘符、ADS、反斜线与已有输出覆盖；失败不在目标目录外留下文件。
- [x] Run: `pnpm test:api tests/test_container_runtime.py tests/test_container_lifecycle.py tests/test_container_exports.py tests/test_docker_validation.py -q`；确认相关 red 断言。
- [x] 实现固定 create/start/exec/inspect/kill/remove argv、双层 deadline、最小环境、
  实际 OOM/exit 原因和每步归属复核。线程收到取消后清理容器，不只是终止 exec 客户端。
- [x] 实现私有 journal 的创建前意图、原子状态更新、死亡进程身份核验、严格标签查找、
  finally 和下次容量取得时精确回收；不复用 SQLite 维护锁、不让任务控制 journal 路径。
- [x] 实现活容器固定 export exec；不使用 docker cp/tmpfs、tar、extractall 或暂停容器。
  宿主在全新目录严格解码/自算 hash/独占创建；异常先终止归属容器再清理已验证目录。
- [x] Run 新增测试全通过；模拟 CLI 只能证明参数/逻辑，不记录 OS 隔离成功。
- [x] 更新记录后顺序继续。

## Task 1.5: TaskRun 回执、旧库兼容和环境展示

**Files**
Create: validation_browser.py；apps/api/tests/test_container_validation_integration.py。
Modify: automatic_validation.py、qa_assessment.py、apps/web/src/lib/api.ts、
apps/web/src/components/qa-evidence.tsx、apps/web/src/components/qa-evidence.test.tsx；
test_automatic_validation.py、test_backend_validation.py、test_layered_qa.py、
docs/change-log.md。
完整回归追加最小兼容文件：review_repairs.py 比较旧原生检查摘要；test_review_repairs.py
保留真实修复恢复断言。test_task_runs.py 只增加调度延迟样本与启动同步等待裕量，不改续租断言。
run_engine.py 的调用方式和三个 Adapter 不变；如确需调整只能传递原有启动身份。

**Interfaces**
Consumes: DockerValidationBackend、严格 export 输出目录、现有 validation.started/completed 和 ownership_guard。
Produces: design §8 的 execution JSON、纯本地 currentness 比对、
`run_browser_validation(output_dir: Path, contract: dict, cancelled: Event, *, runner=run_command) -> dict`。
新 UI 可选字段 execution 与 functional.execution；旧数据不补写。

- [x] 红灯：test_default_native_keeps_existing_runner_hooks、test_explicit_docker_unavailable_does_not_run_native、
  test_all_three_adapters_reach_same_post_execution_boundary、
  test_lease_loss_during_container_run_never_publishes_completed。
- [x] 红灯：test_native_receipt_cannot_be_relabelled_docker、test_other_launch_binding_cannot_supply_validation、
  test_terminal_runner_rotation_does_not_invalidate_matching_frozen_launch_binding、
  test_image_or_policy_change_expires_receipt_without_writing_old_rows。
- [x] 红灯：test_legacy_execution_missing_is_readable_without_docker_probe、
  test_legacy_receipt_under_docker_policy_expires_without_relabeling、
  test_requested_docker_unavailable_is_not_marked_executed、
  test_missing_native_browser_leaves_docker_commands_passed_but_qa_incomplete、
  test_export_fingerprint_binds_native_browser_result。
- [x] Run: `pnpm test:api tests/test_container_validation_integration.py tests/test_layered_qa.py -q`；
  选择对应新断言确认 red。
- [x] 在原线程选择配置、验证并冻结启动绑定，在原有 started 事件记录执行元数据；
  阻塞后端只在 worker 运行。复用现有 shield/cancel/final ownership 检查，
  unavailable 不回退 native，失败不被模型评审覆盖。
- [x] 基于 metrics.taskRunExecutionAccessBinding 及原事件比对 generation/执行环境；
  将 Docker policy 与 host native policy 分离，不在 GET/currentness 时调用 daemon。
- [x] 从现有前端路径抽取同一个受信浏览器封装，Docker 的核验 dist 直接交给它，
  不再次原生构建，不拷回 canonical；functional 明确 native 和输出指纹。
- [x] 写 UI 前读取 apps/web/AGENTS.md 指向的已安装 Next 指南；
  最小增加“原生固定验证 / Docker 固定验证 / 历史验证（环境未记录）”及
  “原生浏览器检查”标签，保留现有 QA、主题与键盘行为。
- [x] Run API 新/旧验证、QA、任务租约和三个 Adapter 回归；
  `pnpm test:web src/components/qa-evidence.test.tsx --maxWorkers=1 --no-file-parallelism`；
  `pnpm check`。预期通过且 models/migrations/seed/Adapter 协议无差异。
- [x] 更新记录后顺序继续。

## Task 1.6: 真实 Docker、数据保留与交付验收

**Files**
Create: apps/api/tests/test_container_validation_real.py、
test_container_validation_data.py、.github/workflows/container-validation.yml；
docs/container-validation.md（为此文件增加精确 .gitignore 白名单）。
Modify: sandbox_cli.py、scripts/sandbox.sh、package.json、docs/change-log.md、
docs/project-state.md、OpenSpec tasks/verification。
Test: 原有完整回归及上述真实容器测试。

**Interfaces**
Consumes: 全部前序能力、操作员已准备的两个 image ID。
Produces: `pnpm sandbox:verify` 的强制真实验证入口、有界外部证据与准确 UI/README；
手动 workflow_dispatch 的专用 job，permissions contents:read，不含 Provider 凭据。

- [x] 先写资格用例：两类正确/有缺陷源码，实际固定命令及解析覆盖；
  源码/策略/执行身份变化不能建立当前验收。
- [x] 写数据资格用例：独立 current 数据库预置自定义工作区、Agent 设置、Skills/MCP、
  消息/附件 BLOB 和旧 TaskRun/回执，分别追加新 native/Docker 任务；
  比较既有行 ID/值/BLOB、完整性/外键、head/schema，并确认旧报告只读。
- [x] 写实际边界用例：只读 root/input、宿主 sentinel/.env/socket/端口不可达、
  无外网、CPU/PID/内存 enforcement、阶段/总超时、日志/产物限额、容量竞争、
  取消及 API 进程在 create/exec/export 各窗口被终止后的精确恢复。
  资源负例用固定测试 probe，由资格测试自身操作自有容器，不成为生产 API/Agent 命令。
- [x] 实现强制资格开关：默认 native CI 可明确跳过 real-container 文件；
  `sandbox:verify` 和专用 job 设置 `AGENTHUB_TEST_CONTAINER_VALIDATION=1`，
  无 daemon、镜像或能力时必须失败，不能 skip。测试记录实际镜像和策略。
  sandbox.sh verify 只设置开关并复用 scripts/test-api.sh，指定上述 real/data 文件，
  使用新外部测试库及 JUnit；不直接运行连接产品库的 pytest。
- [x] 准备环境由用户单独安排 Docker Desktop/WSL 或既有 Linux daemon；
  不擅自安装、启动 daemon、重启电脑或使用不安全参数。
- [x] 专用 workflow 在显式触发时准备最小镜像并执行真实测试；
  默认 ci.yml 和 native 路径保持原有行为。容器不继承 workflow/Provider 凭据。
- [x] 在实际可用 Linux Docker 环境 Run: `pnpm sandbox:verify`；
  一次受控 ScriptedMock 真实修改 → Diff → Docker 固定验证 → 原生需求检查/预览。
  只有实际观察过的 CLI/浏览器环境才记为已验证；模拟 Adapter 不能写成真实 LLM 成功。
- [x] Run: `pnpm check` 及完整 `pnpm test`（本机内存紧张时按组成顺序运行，
  完整 Web 加 --maxWorkers=1 --no-file-parallelism；不删用例或降低断言）。
  冻结源码后不重复已覆盖专项，失败先定位再回归；保留真实 Docker 与 native 结果分母。
  本轮最后完整API2714通过/19环境跳过，无失败；首次3项临时环境异常和随后3项及完整复验分别保留。
- [x] 核对只改本期文件、产品库未操作、旧数据测试通过，记录真实 image ID、recipe、
  flags/inspect、退出/OOM断言、回执/产物绑定和归属清理；对应SHA的远程CI结果另待授权。
- [x] 只有真实资格与兼容回归通过才勾选 1.6、标记第一阶段本机完成；
  缺环境时明确未验收，不以文档、mock 或默认 CI 通过替代。
- [ ] 单独获授权后再提交/推送并跟踪具体 SHA 的默认和专用 CI；否则保留本地成果。

2026-10-19 本机实际强制入口18项通过、零跳过/失败，结果见 verification。
规格要求真实Linux Docker测试，不要求未授权的远程提交。最后一项远程交付独立保留，
本机验收不冒充对应SHA的GitHub Actions；最终原生兼容全量已通过，本机1.6完成。

## Coverage / rollback / handoff

| 规格 | 任务 |
|---|---|
| 可选后端、默认与 Adapter 边界 | 1.2、1.5、1.6 |
| 可信镜像/显式准备/只读 doctor | 1.2、1.3 |
| 无网络与资源、生命周期、容量 | 1.4、1.6 |
| 有界输出、原生浏览器衔接 | 1.3、1.4、1.5、1.6 |
| 执行身份与旧回执/数据 | 1.5、1.6 |
| 实际 Docker 和证据限制 | 1.6 |

回退：明确选择 native，仅影响新运行；不删除数据或改写旧评审，不移除现有 Adapter。
如需调整预算/镜像/依赖，先更新受信策略并重跑相关资格测试，旧证据自然过期。
设计与计划需由用户审阅；执行方式建议 Native，原因是共享执行身份、生命周期和导出接口
联系紧密，顺序实现便于核对。用户随后批准 Native 顺序实现；每次只执行一项，通过该项检查后顺序继续。
