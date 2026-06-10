## 1. P9 外部项目工作区模式

- [x] 1.1 P9-1 外部工作区注册。
  - 目标：让本地外部项目根目录成为一等 AgentHub 工作区目标。
  - 范围：
    - 为外部项目目标添加持久化注册；
    - 存储 `targetId`、`name`、`rootPath`、`projectType`、`allowedPaths`、
      `deniedPaths`、`devCommand`、`testCommand`、`checkCommand`、
      `buildCommand`、`previewCommand`、`packageManager` 和
      `detectedFramework`；
    - 拒绝不安全的根目录，例如主目录、文件系统根目录、系统
      目录以及无限制的父目录；
    - 在执行前要求显式允许的路径或分析器推断的允许路径；
    - 为已注册的外部目标暴露 read/list API。
  - 验收标准：
    - 本地示例项目可以注册为外部目标；
    - 被拒绝的路径包括 `.env`、`.env.*`、`secrets`、`.git`、
      `node_modules`、`.venv` 以及生成的 dependency/build 目录；
    - 注册不会授予对任意文件系统路径的访问权限；
    - 内置的 `demo-frontend`、`demo-backend` 和 `agenthub-platform` 目标
      保持可用。
  - 验证：
    - 注册 service/API 测试；
    - 不安全根目录拒绝测试；
    - `pnpm check`；
    - `pnpm test`；
    - `git diff --check`；
    - `openspec validate agenthub-p9-external-project-workspace-mode --strict`。

- [x] 1.2 P9-2 项目分析器。
  - 目标：在不执行任意命令的情况下推断外部项目的形态和安全默认值。
  - 范围：
    - 检查 `package.json`、`vite.config.*`、`next.config.*`、
      `pyproject.toml`、`requirements.txt`、锁文件以及 source/test 布局；
    - 推断项目类型：`vite-react`、`nextjs`、`fastapi`、`node-api`、
      `python-package` 或 `unknown`；
    - 推断包管理器、框架、允许路径、拒绝路径以及安全命令候选；
    - 当推断不确定时生成 `needs_confirmation`；
    - 分析期间绝不安装依赖项。
  - 验收标准：
    - 分析器能检测具有代表性的 Vite React、Next.js、FastAPI、Node API
      和 Python 包测试夹具；
    - 未知项目在执行前需要 confirmation/config；
    - 分析器输出包含警告和置信度状态；
    - 分析器绝不将 dependency/build 输出目录视为允许写入路径。
  - 验证：
    - 分析器夹具测试；
    - 不确定推断测试；
    - `pnpm check`；
    - `pnpm test`；
    - `git diff --check`；
    - `openspec validate agenthub-p9-external-project-workspace-mode --strict`。

- [x] 1.3 P9-3 外部目标注册表集成。
  - 目标：使外部目标能够通过与内置目标相同的目标注册表模型使用。
  - 范围：
    - 在注册表读取中合并内置目标和持久化的外部目标；
    - 将外部元数据映射到目标注册表字段；
    - 更新规划器、指令构建器、审查和调度器查找，以接受外部目标 ID；
    - 确保 P8 目标锁适用于外部目标 ID；
    - 保持 `agenthub-platform` 保护不变。
  - 验收标准：
    - 已注册的外部目标可以通过目标 ID 解析；
    - 外部目标元数据对上下文包和指令可见；
    - 相同外部目标的写入任务由 P8 锁序列化；
    - 内置演示目标行为保持不变。
  - 验证：
    - 注册表集成测试；
    - 调度器外部锁测试；
    - 内置目标回归测试；
    - `pnpm check`；
    - `pnpm test`；
    - `git diff --check`；
    - `openspec validate agenthub-p9-external-project-workspace-mode --strict`。

- [x] 1.4 P9-4 外部目标指令构建器。
  - 目标：为已注册的外部目标生成有意义的角色指令，且不假设演示路径。
  - 范围：
    - 更新 frontend/backend/qa/review/manager 指令路径以消费外部目标元数据；
    - 保留原始用户请求；
    - 包含允许路径、拒绝路径、命令、项目类型、包管理器、检测到的框架、选定的制品、最新差异、调度器状态和验证预期；
    - 为外部后端目标准备后端指令，但不允许编辑 AgentHub 平台后端；
    - 保持内置演示指令正常工作。
  - 验收标准：
    - 外部前端指令引用外部 root/allowed 路径，且除非该路径是已注册的目标，否则不提及 `apps/demo`；
    - 外部后端指令引用外部后端目标元数据，且不允许 `apps/api`；
    - 审查指令包含命令证据预期；
    - 不支持的外部任务要求澄清或诚实地失败。
  - 验证：
    - 指令构建器测试；
    - 上下文包测试；
    - 内置指令回归测试；
    - `pnpm check`；
    - `pnpm test`；
    - `git diff --check`；
    - `openspec validate agenthub-p9-external-project-workspace-mode --strict`。

- [x] 1.5 P9-5 外部项目任务执行。
  - 目标：允许已注册的外部目标通过现有适配器接收可执行的 coding/review 任务。
  - 范围：
    - 选中时将 `@frontend` 路由到活跃的外部前端目标；
    - 选中时将 `@backend` 路由到活跃的外部后端目标；
    - 将 `@qa` / `@review` 路由到面向读取的外部审查任务；
    - 让编排器为选中的工作区创建外部目标任务；
    - 保留 `CodexAdapter`、`ClaudeCodeAdapter` 和 `ScriptedMockAdapter` 的行为；
    - 将适配器执行范围限定在已注册的外部目标工作树或根目录以及显式允许的路径内。
  - 验收标准：
    - 直接提及的任务可以指向已注册的外部项目；
    - 编排器至少能创建一个有界的外部目标任务；
    - TaskRun 指令保留用户的原始请求；
    - 不支持或模糊的外部请求不会静默执行。
  - 验证：
    - 路由测试；
    - TaskRun 请求测试；
    - 不支持的请求测试；
    - `pnpm check`；
    - `pnpm test`；
    - `git diff --check`；
    - `openspec validate agenthub-p9-external-project-workspace-mode --strict`。

- [x] 1.6 P9-6 外部证据流水线。
  - 目标：根据目标能力记录外部项目证据。
  - 范围：
    - 收集外部目标工作的 git diff；
    - 为检查、测试和构建命令输出添加证据制品；
    - 仅在配置了预览时支持预览 URL / 健康检查；
    - 不要求每个外部项目都支持预览；
    - 如实记录失败的命令；
    - 在现有 artifact/message 卡片模式中展示外部证据。
  - 验收标准：
    - 外部 diff 被收集并限定在允许的路径范围内；
    - check/test/build 输出可作为证据存储；
    - 失败的命令证据作为 failed/warning 证据可见；
    - 如果存在 diff 和命令证据，不支持预览的目标仍然有效。
  - 验证：
    - 证据制品测试；
    - 失败命令证据测试；
    - 无预览目标测试；
    - `pnpm check`；
    - `pnpm test`；
    - `git diff --check`；
    - `openspec validate agenthub-p9-external-project-workspace-mode --strict`。

- [x] 1.7 P9-7 外部项目审查。
  - 目标：对照已注册的目标策略审查外部差异和证据。
  - 范围：
    - 检测允许路径之外的编辑；
    - 检测对禁止路径的编辑，包括 `.env`、`.env.*`、`secrets`、
      `.git`、`node_modules`、`.venv`、生成的 dependency/build 目录，
      以及不安全的主机路径；
    - 在审查摘要中包含 check/test/build 证据；
    - 如实报告失败的命令证据；
    - 不得伪造 Claude/Codex 成功。
  - 验收标准：
    - 允许路径违规导致审查失败或警告；
    - 禁止路径编辑导致审查失败；
    - 失败的 tests/checks/builds 在审查状态和结果中可见；
    - 审查与内置的 P6/P7/P8 演示目标保持兼容。
  - 验证：
    - 外部审查测试；
    - 禁止路径测试；
    - 失败命令证据审查测试；
    - 内置审查回归测试；
    - `pnpm check`；
    - `pnpm test`；
    - `git diff --check`；
    - `openspec validate agenthub-p9-external-project-workspace-mode --strict`。

- [x] 1.8 P9-8 外部项目端到端预演与冻结审查。
  - 目标：在不回归 P6/P7/P8. 的前提下验证外部工作区模式。
  - 范围：
    - 在内置演示目标之外，创建或使用一个本地示例外部项目；
    - 将其注册为外部工作区目标；
    - 如果可行，运行一个有边界的真实代理任务；
    - 如果真实的 Claude/Codex 被 auth/quota/runtime 阻塞，记录确切的错误，并仅使用受控兜底来获取管道证据；
    - 验证差异、审查、test/check/build 证据，以及在配置时的预览证据；
    - 验证目标锁定是否适用于外部目标；
    - 验证内置演示基线保持不变。
  - 验收标准：
    - 外部项目注册和分析证据已记录；
    - 至少演练了一条外部 task/run/evidence 路径；
    - 仅当实际运行时，才声称真实的 Claude/Codex 成功；
    - P6/P7/P8 内置的迷你 CRM / 注册表 / 调度器基线保持不变；
    - 记录剩余的注意事项。
  - 验证：
    - 根据实际情况进行有针对性的 API/browser 预演；
    - `pnpm check`；
    - `pnpm test`；
    - `pnpm demo:api:test`；
    - `git diff --check`；
    - `openspec validate agenthub-p9-external-project-workspace-mode --strict`。

## 2. P9 的明确非目标

- 云端仓库导入。
- 多用户项目共享。
- 生产环境部署。
- Docker 沙箱。
- 提供商市场。
- PR 创建。
- 任意无限制的文件系统访问。
- 企业级 RBAC。
- 完整的多租户工作区系统。
- 飞书、微信、Slack 或其他外部即时通讯集成。
- Payment/auth/multi-tenant 应用生成。

## 3. P9 完成定义

- 本地外部项目可注册为一等 AgentHub 目标。
- 项目分析器可检测常见项目类型，并在不确定时要求确认。
- 外部目标通过现有的目标注册表模型进行消费。
- 规划器、指令构建器、审查和调度器可使用外部目标元数据。
- `CodexAdapter` 和 `ClaudeCodeAdapter` 可接收绑定到允许路径的有意义外部目标编码指令。
- 外部证据包括差异以及配置后的 check/test/build 和预览。
- 外部审查强制要求 allowed/denied 路径和命令证据真实性。
- 目标锁定适用于外部目标。
- 内置的 P6/P7/P8 演示目标继续正常工作。
- 不声称任何未经验证的 Claude/Codex 成功。
