## 背景

P8 已冻结。AgentHub 现在拥有有界的本地全栈执行循环、
支持注册表感知的目标权限以及调度器保护：

```text
requirement -> Orchestrator -> app contract / tasks -> target-aware execution
-> diff -> review -> preview when supported -> mock deploy
```

当前的目标宇宙仍主要内置于 AgentHub 中：

- `demo-frontend` 指向 `apps/demo`；
- `demo-backend` 指向 `apps/demo-api`；
- `agenthub-platform` 保护 AgentHub 控制平面。

P9 扩展了此模型，使得内置演示目标之外的本地项目能够作为一等 AgentHub 工作区目标进行注册、分析、选择和操作。

## 目标 / 非目标

**目标：**

- 将本地外部项目根目录注册为一级 AgentHub 工作区目标。
- 分析常见项目布局，推断项目类型、框架、包管理器、安全命令及安全允许路径。
- 当分析结果不确定时，要求用户明确确认或配置。
- 通过规划器、指令构建器、审查器和调度器所消费的同一目标注册表形态，表示外部目标。
- 允许 `@frontend`、`@backend`、`@qa`、`@review` 以及编排器创建的任务对选定的外部目标进行操作。
- 在代理指令中保留用户的原始请求。
- 让 Claude Code / Codex 在明确的外部允许路径内执行有意义的编码工作。
- 收集外部证据：git diff、check/test/build 输出，以及配置后的预览 URL。
- 审查外部变更的路径安全性和命令证据真实性。
- 在保留 P6/P7/P8. 的前提下，使用本地示例外部项目进行演练。

**非目标：**

- 云仓库导入。
- 多用户项目共享。
- 生产环境部署。
- Docker 沙箱隔离。
- 提供商市场。
- PR 创建。
- 任意无限制文件系统访问。
- 企业级 RBAC。
- 完整的多租户工作区系统。
- 外部即时通讯集成。
- Payment/auth/multi-tenant 应用生成。

## 外部工作区模型

外部工作区注册应持久化足够的元数据，以确保安全执行，同时避免将用户的主目录或任意文件系统暴露给代理。

建议的字段：

```text
targetId
workspaceId
name
rootPath
projectType
detectedFramework
packageManager
allowedPaths
deniedPaths
devCommand
testCommand
checkCommand
buildCommand
previewCommand
baseUrl
allowedAgents
requiresApproval
analysisStatus
analysisWarnings
createdAt
updatedAt
```

第一个实现可以将此信息存储在 SQLite 中，使用专用的
`ExternalProjectTarget` 表，或者如果届时已有目标元数据表，则扩展该表。
运行时目标注册表应通过一个统一的读取 API 暴露内置目标和外部目标。

## 项目分析器

分析器应检查项目根目录，无需安装依赖项或执行任意命令。

输入：

```text
rootPath
user-provided target name
optional user command overrides
optional user allowed-path overrides
```

检测来源：

- `package.json`;
- `vite.config.*`;
- `next.config.*`;
- `pyproject.toml`;
- `requirements.txt`;
- `src/`、`app/`、`pages/`、`tests/`、`test/`;
- 常见的后端入口点，例如 `main.py`、`app/main.py`、
  `server.ts`、`src/server.ts`;
- 锁定文件，例如 `pnpm-lock.yaml`、`package-lock.json`、`yarn.lock`、
  `uv.lock`、`poetry.lock`。

初始项目类型：

- `vite-react`；
- `nextjs`；
- `fastapi`；
- `node-api`；
- `python-package`；
- `unknown`。

分析器应推断出：

- `packageManager`: `pnpm`、`npm`、`yarn`、`uv`、`poetry`、`pip` 或
  `unknown`；
- 当 config/scripts 中存在时，安全默认的 `checkCommand`、`testCommand`、`buildCommand` 和
  `previewCommand`；
- 允许的源路径，例如 `src`、`app`、`pages`、`components`、
  `tests` 或后端应用包文件夹；
- 始终包含 `.env`、`.env.*`、`secrets`、`.git`、
  `node_modules`、`.venv`、`dist`、`build`、`.next`、覆盖率输出以及
  生成的依赖目录的拒绝路径。

如果分析器无法自信地推断出安全默认值，则应生成
`analysisStatus: needs_confirmation`，并在执行前要求用户确认或显式
配置。

## 目标注册表集成

P9 不应引入并行的外部目标机制。外部目标必须适配到现有的目标注册表模型中，以便下游代码能够使用相同的元数据结构：

```text
targetId
name
type
root
allowedPaths
deniedPaths
allowedAgents
devCommand
testCommand
checkCommand
buildCommand
previewCommand
baseUrl
requiresPlatformMode
requiresApproval
relatedTargetIds
```

内置目标是静态的。外部目标是动态且持久化的。

注册表查找应合并当前 workspace/session 上下文中的内置目标与已注册的外部目标。

来自 P8 的目标锁适用于外部目标 ID。针对同一目标的写入任务必须保持串行。

## 指令构建器

外部目标指令必须停止假设演示路径。

角色特定的期望：

- 前端：
  - 使用外部目标根目录和允许路径；
  - 使用检测到的框架和包管理器；
  - 仅在收到指令时运行已配置的 check/test/build 命令；
  - 仅在可用时使用已配置的预览命令。
- 后端：
  - 使用外部后端目标根目录和允许路径；
  - 除非明确针对 `agenthub-platform`，否则不要编辑 AgentHub `apps/api`；
  - 保留已配置的 API 入口点和测试。
- 质量保证/审查：
  - 检查外部差异和命令证据；
  - 如实报告失败的命令；
  - 检测被禁止的路径编辑。
- 管理器/编排器：
  - 当外部工作区处于活动状态时，将常规请求路由到选定的外部目标；
  - 当多个外部目标可能适用时，请求澄清；
  - 如实拒绝不受支持或不安全的请求。

每条指令必须保留原始用户请求，并包含目标元数据、允许路径、禁止路径、所选制品上下文、最新差异、调度器状态以及可用的验证预期。

## 外部任务执行

P9 应同时支持显式分配和编排器规划：

- `@frontend` 针对活跃的外部前端目标创建一个前端任务。
- `@backend` 针对活跃的外部后端目标创建一个后端任务。
- `@qa` 和 `@review` 针对外部目标和证据创建面向阅读的审查任务。
- 未提及的消息路由到编排器，由其决定是创建外部任务、请求澄清，还是拒绝不支持的工作。

适配器执行边界：

- `CodexAdapter` 和 `ClaudeCodeAdapter` 仅在指定的外部目标 worktree/root 边界内运行。
- 代理只能编辑明确允许的路径。
- 代理不得编辑被禁止的路径。
- 代理不得逃逸到系统目录或用户主目录中，除非已确认该确切注册根目录且允许路径仍受约束。

## 证据流水线

外部项目证据应基于能力，而非假设每个项目都可预览。

证据类型：

- git diff 制品；
- 检查命令输出；
- 测试命令输出；
- 构建命令输出；
- 预览 URL / 健康状态（当配置了预览时）；
- 审查制品，总结路径策略和命令证据。

失败的命令必须作为失败证据存储，并呈现给 review/UI.
它们不能仅仅因为存在差异就被转换为成功。

Mock deploy 仍然是内置的演示行为。P9 不应为外部项目添加生产环境部署。

## 审查策略

外部审查必须检查：

- 变更的文件始终位于允许的路径内；
- 禁止路径未被触及；
- `.env`、`.env.*`、`secrets`、`.git`、`node_modules`、`.venv`、生成的
  dependency/build 目录以及锁保护的控制平面路径未被修改；
- 当目标配置了 check/test/build 命令时，存在命令证据；
- 失败的 check/test/build 命令会产生警告或失败的审查状态；
- 审查不会在没有 TaskRun 证据的情况下声称真实的 Claude/Codex 成功。

除非后续变更添加了阻塞性审批关卡，否则评审仍为建议性质。

## UI / UX

第一个 P9 UI 应可运行，而非营销页面：

- register/select 外部本地项目；
- 显示分析器结果及所需确认；
- 显示目标元数据：根目录、项目类型、检测到的框架、允许路径、禁止路径、命令、包管理器；
- 在 chat/task 界面中显示活跃的外部目标；
- 当存在 diff/check/test/build/preview/review 时，显示证据卡片；
- 使用 P8 UI 界面显示外部目标的调度器状态和目标锁。

## 风险 / 权衡

- **风险：任意文件系统变更。** 缓解措施：要求显式注册，默认拒绝 home/system 根目录，并仅允许指定路径。
- **风险：分析器推断出不安全命令。** 缓解措施：不确定时优先使用 `needs_confirmation`；分析期间绝不安装依赖或执行任意命令。
- **风险：外部项目差异巨大。** 缓解措施：从常见 Vite/Next/FastAPI/Node/Python 模式入手，将未知项目视为可配置但不可自动运行。
- **风险：命令执行扩大攻击面。** 缓解措施：按目标进行命令白名单管理，禁止 shell 插值，限定工作目录范围，并如实记录失败证据。
- **风险：破坏内置演示基线。** 缓解措施：保持内置目标行为不变，并在 P9 冻结期间运行 P6/P7/P8 回归验证。

## 迁移计划

1. 持久化外部目标注册与分析器结果。
2. 将外部目标合并到目标注册表读取中。
3. 教导规划器和指令构建器使用活跃的外部目标。
4. 添加外部 TaskRun/evidence 命令制品。
5. 扩展审查与调度器以支持外部目标。
6. 添加 UI 注册与证据展示。
7. 使用本地示例外部项目进行演练，并验证 P6/P7/P8 基线。

回滚策略：禁用外部目标选择，同时保留内置
目标注册表条目和 P8 调度器行为。
