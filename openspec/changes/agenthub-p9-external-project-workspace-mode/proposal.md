## 为什么

P6 证明了 AgentHub 能够协调一个有限的全栈迷你 CRM，针对内置的演示前端和演示后端。P7 通过目标项目注册表使这些目标显式化，P8 增加了依赖感知调度、目标写入锁、失败阻塞和调度器 UI 跟踪。然而，AgentHub 仍然主要在内置的演示目标上运行：

- `demo-frontend`: `apps/demo`;
- `demo-backend`: `apps/demo-api`;
- `agenthub-platform`: AgentHub 维护。

P9 是必要的，以便用户选择的本地项目能够成为一流的 AgentHub 工作区。这是一项实际的执行能力升级：Claude Code 和 Codex 应能够在已注册的外部项目目标上工作，并具备明确的路径边界、检测到的命令、调度器锁、审查检查以及证据制品。

## 变更内容

- 为本地项目根目录添加外部工作区注册功能。
- 添加项目分析器，用于检测 framework/type、安全命令、包管理器、默认允许路径及不确定性。
- 将外部目标与现有目标项目注册模型集成，使规划器、指令构建器、审查和调度器使用统一的目标形态。
- 为外部前端、后端、QA 和审查任务构建目标感知指令，不假设 `apps/demo` 或 `apps/demo-api`。
- 允许编排器和显式的 `@frontend`、`@backend`、`@qa`、`@review` 分配，针对已注册的外部目标创建可执行任务。
- 扩展外部目标的证据流水线，在配置时支持 git diff、check/test 输出、构建输出和预览 URL。
- 扩展审查功能以强制执行外部 allowed/denied 路径，并如实报告失败的检查项。
- 在保留 P6/P7/P8 内置演示行为的前提下，针对本地示例外部项目进行 P9 演练。

P9 必须超越保守的纯元数据绑定。目标是让注册的外部本地项目成为可运行的 AgentHub 目标，当用户选择运行它们时，能够通过 `ClaudeCodeAdapter` / `CodexAdapter` 接收真实的编码任务。

## 能力

### 新能力

- `external-workspace`: 外部本地项目工作区的注册、分析、目标注册表集成、角色指令、任务执行、证据、审查和预演。

### 修改后的能力

- 目标注册中心消费者必须支持外部目标元数据，同时保留内置的 `demo-frontend`、`demo-backend` 和 `agenthub-platform`。
- 规划器/编排器应在明确选择时，将已注册的外部工作区请求路由到外部目标。
- 调度器目标锁必须适用于外部目标。
- 审查必须强制执行外部路径策略和命令证据。

## 影响

OpenSpec 制品：

- `openspec/changes/agenthub-p9-external-project-workspace-mode/proposal.md`
- `openspec/changes/agenthub-p9-external-project-workspace-mode/design.md`
- `openspec/changes/agenthub-p9-external-project-workspace-mode/tasks.md`
- `openspec/changes/agenthub-p9-external-project-workspace-mode/specs/external-workspace/spec.md`

P9 后续应用时的预期实现影响：

- 后端：
  - 持久化的外部工作区/目标注册；
  - 项目分析服务；
  - 动态外部目标注册表条目；
  - 支持外部目标的规划与直接提及分配；
  - 用于命令输出的外部证据制品；
  - 针对路径策略和命令结果真实性的外部审查检查。
- 前端：
  - 外部项目注册 UI；
  - 项目 analysis/confirmation UI；
  - 聊天和任务界面中选中的 workspace/target 指示器；
  - 在可用时显示 diff/check/test/build/preview 的外部证据卡片。
- 运行时：
  - 适配器仅在显式注册的外部目标根目录或其分配的工作树内执行；
  - 禁止路径包括 `.env`、`.env.*`、`secrets`、`.git`、`node_modules`、`.venv`、生成的依赖目录以及不安全的系统路径；
  - 外部目标锁防止同一目标的写入冲突；
  - 失败的命令必须如实记录，不得转换为成功声明。
