## ADDED Requirements
### Requirement: 外部工作区注册
系统 MUST 允许在代理执行之前，将本地外部项目根目录注册为一等 AgentHub 工作区目标。

#### Scenario: 本地项目已注册
- **WHEN** 用户注册了一个本地外部项目根目录
- **并且** 该根目录不是系统目录、主目录、仓库父目录或其他不安全的宽泛路径
- **THEN** 系统 MUST 持久化一个外部目标，包含 `targetId`、`name`、`rootPath`、`projectType`、`allowedPaths`、`deniedPaths`、`devCommand`、`testCommand`、`checkCommand`、`buildCommand`、`previewCommand`、`packageManager` 和 `detectedFramework`
- **并且** 该外部目标 MUST 可被选中用于未来的 sessions/tasks.

#### Scenario: 不安全的根被拒绝
- **WHEN** 用户尝试将文件系统根目录、主目录、系统目录或宽泛的父目录注册为外部项目
- **THEN** 系统 MUST 拒绝该注册
- **并且** 拒绝操作 MUST 说明外部项目根目录必须是明确的项目目录。

#### Scenario: 被拒绝的路径始终存在
- **WHEN** 已注册一个外部目标
- **THEN** 其禁止路径 MUST 包括 `.env`、`.env.*`、`secrets`、`.git`、
  `node_modules`、`.venv`、生成的依赖目录以及生成的
  构建输出目录
- **并且** 这些禁止路径 MUST 不允许被适配器编辑。

### Requirement: 项目分析器
系统 MUST 在不安装依赖或运行任意命令的情况下分析外部项目结构。

#### Scenario: 分析 JavaScript 前端项目
- **WHEN** 分析器找到 `package.json` 以及 Vite 或 Next.js config/scripts
- **THEN** 它 MUST 推断出前端项目类型，例如 `vite-react` 或
  `nextjs`
- **并且** 它 MUST 推断出包管理器、检测到的框架、安全源路径，
  以及在可用时配置的 check/test/build/preview 命令候选。

#### Scenario: Python 或 API 项目被分析
- **WHEN** 分析器找到 `pyproject.toml`、`requirements.txt`、FastAPI
  入口点或 Node API 入口点
- **THEN** 它 MUST 推断出 `fastapi`、`node-api`、`python-package` 或 `unknown`
  视情况而定
- **并且** 当可用时，它 MUST 推断出安全的 source/test 路径和验证命令候选。

#### Scenario: 分析器不确定
- **WHEN** 项目类型、安全允许路径或命令推断不确定
- **THEN** 分析器 MUST 将结果标记为需要确认或显式配置
- **且** 目标 MUST 在不确定性解决之前**不得**执行。

### Requirement: 外部目标注册表集成
系统 MUST 通过用于内置目标的同一目标注册表模型暴露外部目标。

#### Scenario: 外部目标已解析
- **WHEN** 在 workspace/session 上下文中请求了一个已注册的外部目标 ID
- **THEN** 目标注册表 MUST 返回一个与内置目标兼容的目标元数据对象
- **并且** 规划器、指令构建器、审查器和调度器 MUST 能够使用它。

#### Scenario: 内置目标仍然可用
- **WHEN** 外部目标已注册
- **THEN** `demo-frontend`、`demo-backend` 和 `agenthub-platform` MUST 仍保持可解析
- **并且** 它们的权限和调度器行为 MUST 不得退化。

#### Scenario: 外部目标锁已激活
- **WHEN** 针对某个外部目标存在一个活跃的写入 TaskRun
- **且** 针对同一外部目标的另一个写入任务变为可运行状态
- **THEN** 调度器 MUST 不会启动第二个任务
- **且** 第二个任务 MUST 暴露一个与外部目标 ID 对应的 `waiting_target_lock` 等价物。

### Requirement: 外部目标指令
系统 MUST 根据外部目标元数据构建角色特定的指令，
而非假设内置的演示路径。

#### Scenario: 前端任务针对外部前端
- **WHEN** 前端任务指向已注册的外部前端项目
- **THEN** 指令 MUST 包含外部根目录、允许路径、拒绝路径、项目类型、包管理器、检测到的框架、原始用户请求以及验证预期
- **且** 指令 MUST 不假定 `apps/demo`，除非该路径是已注册的目标根目录。

#### Scenario: 后端任务指向外部后端
- **WHEN** 后端任务指向已注册的外部 backend/API 项目
- **THEN** 指令 MUST 包含外部后端根目录、允许路径、禁止路径、已配置命令、原始用户请求及验证预期
- **且** 不允许编辑 AgentHub 平台后端 `apps/api`，除非任务明确指向 `agenthub-platform`。

#### Scenario: 审查任务指向外部证据
- **WHEN** 一个 QA 或审查任务针对外部项目
- **THEN** 指令 MUST 包含最新的差异元数据、命令证据、允许路径策略、禁止路径策略，以及可用的选定制品上下文。

### Requirement: 外部项目任务执行
系统 MUST 允许已注册的外部目标通过现有的 AgentHub 路由和适配器路径接收可执行任务。

#### Scenario: 直接前端分配使用活跃的外部目标
- **WHEN** 用户发送 `@frontend` 且外部前端目标处于活动状态
- **THEN** 系统 MUST 创建一个针对该外部目标的前端任务
- **并且** TaskRun 执行 MUST 限定在目标 root/worktree 及允许的路径范围内。

#### Scenario: 直接后端分配使用活跃的外部目标
- **WHEN** 用户发送 `@backend` 时，若外部后端目标处于活动状态
- **THEN** 系统 MUST 创建一个针对该外部目标的后端任务
- **并且** 除非显式选择了平台模式，否则它 MUST 不得修改 AgentHub 平台后端。

#### Scenario: 编排器路由正常请求
- **WHEN** 用户发送一个正常的无提及请求，同时外部工作区目标处于激活状态
- **THEN** 编排器 MUST 决定是创建外部目标任务、提出澄清问题，还是诚实地拒绝不支持的工作
- **并且** 不支持或模糊的请求 MUST 不得静默执行。

### Requirement: 外部证据管道
系统 MUST 根据注册的目标能力记录外部项目证据。

#### Scenario: 外部编码任务完成
- **WHEN** 外部编码 TaskRun 完成
- **THEN** 系统 MUST 收集限定于外部目标的 git diff
- **并且** 它 MUST 记录已更改的文件，但不包含被拒绝或依赖目录。

#### Scenario: 验证命令已配置
- **WHEN** 外部目标已配置检查、测试或构建命令
- **THEN** 系统 MUST 能够记录命令输出证据
- **并且** 失败的命令退出 MUST 被如实记录为失败证据。

#### Scenario: 预览不可用
- **WHEN** 外部目标没有预览命令
- **THEN** 系统 MUST 不要求提供预览证据
- **并且** 任务仍可能生成有效的差异、命令和审查证据。

### Requirement: 外部项目评审
系统 MUST 根据已注册的目标策略审查外部目标差异和命令证据。

#### Scenario: 检测到允许路径违规
- **WHEN** 外部差异包含目标允许路径之外的文件
- **THEN** 审查 MUST 报告警告或失败
- **且** 发现结果 MUST 识别违规路径。

#### Scenario: 检测到被拒绝的路径编辑
- **WHEN** 外部差异包含 `.env`、`.env.*`、`secrets`、`.git`、
  `node_modules`、`.venv`、依赖目录、生成的构建输出或其他被禁止的路径
- **THEN** 审查 MUST 失败或发出警告，并明确提示存在被禁止的路径。

#### Scenario: 命令证据失败
- **WHEN** 检查、测试或构建命令的证据存在且失败
- **THEN** 审查 MUST 将该失败包含在其 summary/findings 中
- **并且** 系统 MUST 未声称验证成功。

### Requirement: 外部工作区基线保留
系统 MUST 保留 P6/P7/P8 内置行为，同时添加外部工作区模式。

#### Scenario: 执行外部项目预演
- **WHEN** P9 已审查完毕，准备冻结
- **THEN** 一个本地示例外部项目 MUST 需完成注册与演练
- **并且** 证据 MUST 需记录注册信息、分析器输出、task/run ID、差异对比、审查记录、命令证据、配置预览时的预览证据及注意事项
- **并且** 仅在实际运行时 MUST 才能声明真实 Claude/Codex 成功
- **并且** P6/P7/P8 内置演示基线 MUST 需保持完整

#### Scenario: 请求超出范围的能力
- **WHEN** 请求需要云仓库导入、多用户项目共享、生产部署、Docker 沙箱、提供商市场、PR 创建、企业级 RBAC 或不受限制的文件系统访问
- **THEN** P9 MUST 应如实拒绝或推迟该请求
- **并且** 它 MUST 不得在已注册的外部目标之外静默执行。
