## 总体设计

V2.4 在现有 `project_analyzer.py`、`external_workspaces.py`、`target_registry.py`
和 `project_command_policy.py` 之间增加一个正式的 ProjectProfile 合同层。

目标链路：

```text
项目根目录
  -> Project Analyzer
  -> ProjectProfile
  -> External Target registration
  -> Target Registry
  -> PlanValidator / Command Policy / Instruction Builder / Preview
```

ProjectProfile 不是新的安全边界。它负责描述项目事实和建议策略；真正的执行允许
仍由 Target Registry、PlanValidator、Guardrails、Provider Gateway 和后续 Policy
Engine 决定。

## ProjectProfile 合同

建议最小字段：

- `profileId`：稳定 profile 标识，例如 `vite-react`、`nextjs-react`、
  `fastapi-python`、`generic-repo`。
- `displayName`：用户可读名称。
- `projectType`：沿用现有类型或新增 generic。
- `detectedFramework`：检测到的框架。
- `packageManager`：`pnpm`、`npm`、`yarn`、`uv`、`poetry`、`pip`、`unknown`。
- `allowedPaths`：建议的 target-scoped 可写路径。
- `deniedPaths`：保护路径，必须包含 `.git`、`.env*`、`node_modules`、`secrets`
  等默认拒绝项。
- `commands`：`dev`、`test`、`check`、`build`、`preview` 等 profile 派生命令。
- `previewStrategy`：`vite-dev-server`、`next-dev-server`、`python-api`、
  `static-none`、`custom` 或 `none`。
- `confidence`：`high`、`medium`、`low`。
- `status`：`ready` 或 `needs_confirmation`。
- `warnings`：检测不完整、缺测试、缺可写路径、未知项目等提示。

字段命名可以在 Python 内部使用 snake_case，在 API/schema 输出时保持现有
camelCase 风格。

## 内置 Profile

### Vite / React

- 检测：`vite.config.*` 或 `vite` + `react` 依赖。
- 默认路径：`src`、`public`、`tests`、`test` 中实际存在的目录。
- 命令：从 package scripts 派生 `dev`、`test`、`check/lint`、`build`。
- 预览：优先 Vite dev server，使用端口占位符时由 preview 层填充。

### Next.js / React

- 检测：`next.config.*`、`next` 依赖或 scripts 中的 Next 标记。
- 默认路径：`app`、`pages`、`components`、`src`、`public`、`tests`、`test` 中
  实际存在的目录。
- 命令：从 package scripts 派生。
- 预览：Next dev server；V2.4 可先只记录策略，不要求完成完整 Next preview
  iframe 能力。

### FastAPI / Python

- 检测：`requirements.txt` / `pyproject.toml` 中的 FastAPI，或入口文件包含
  `FastAPI`。
- 默认路径：`app`、`src`、`tests` 中实际存在的目录。
- 命令：`pytest`、`python -m compileall .` 和可选 uvicorn dev command。
- 预览：API service strategy；V2.4 不要求将 API preview 做成网页 iframe。

### Generic Repo

- 检测：无法识别为以上 profile，但用户显式注册了 target。
- 默认状态：`needs_confirmation`。
- 默认命令：不自动允许任意命令；只有用户显式配置的命令可以进入 command policy。
- 默认路径：只接受注册时显式传入并通过校验的相对 allowedPaths。

## Command Policy

ProjectProfile 可以派生命令，但命令执行仍需要满足：

- 命令类型在允许集合内，例如 `dev`、`test`、`check`、`build`、`preview`；
- 命令与 target/profile 中配置的规范化命令完全匹配；
- 命令运行目录位于注册 target root；
- 命令不包含 secrets、`.env`、`node_modules`、生产部署或外部网络行为的隐式授权；
- 未来 V2.5 Policy Engine 可以在此基础上返回 approval/deny。

V2.4 不开放用户自建任意 shell command agent，也不允许 planner 直接绕过 command
policy。

## Target Registry 接入

External target 转换为 `TargetProject` 时应携带 profile 摘要：

- `project_type`、`detected_framework`、`package_manager` 和 `analysis_status` 继续
  保留；
- 新增或派生 `project_profile` / `profile_id` / `preview_strategy` 等字段；
- allowed agents 仍由 target type 决定；
- allowed paths 和 denied paths 仍来自 target registry；
- AgentHub platform target 仍需要 platform maintenance approval。

## Planner 与指令影响

Planner 可看到 profile 摘要，用于更准确地拆分任务，但不能把 profile 当作授权。

Provider instruction 可以包含：

- target id/root；
- project profile；
- allowed paths；
- validation commands；
- preview/build strategy；
- denied paths 和 guardrails。

正常聊天不应触发 coding agent。coding agent 只在经过 ConversationOutcome(task_plan)
和 PlanValidator 后执行。

## UI/API 边界

如果当前 UI 已展示 target analysis，V2.4 可以只补充 profile 字段和测试；不要求做大
规模 UI 重设计。

应避免把设置页做复杂。用户需要看到：

- target 当前识别成什么 profile；
- 哪些路径允许；
- 哪些命令会被 AgentHub 用于 check/test/build/preview；
- 是否 ready 或 needs_confirmation。

## 安全与非目标

V2.4 不做：

- Docker sandbox；
- WebSocket；
- provider marketplace；
- production deploy；
- 任意命令代理；
- cloud secret manager；
- 完整 Next/FastAPI preview 产品化；
- 替换 scheduler、provider gateway 或 run diagnostics。

V2.4 必须保留：

- Target Registry / PlanValidator / Guardrails 硬边界；
- `.git`、`.env*`、`secrets`、`node_modules` 默认拒绝；
- platform maintenance approval；
- ScriptedMock fallback 只作为 fallback；
- 不伪造 Claude/Codex 成功。

## 测试策略

建议测试：

- ProjectProfile 单元测试：Vite、Next、FastAPI、Generic。
- Analyzer 兼容测试：现有 analyzer 返回仍向后兼容。
- External target API 测试：注册后返回 profile 摘要。
- Target Registry 测试：external target 转换保留 profile 和命令。
- Command Policy 测试：允许 profile 配置命令，拒绝未知/不匹配命令。
- PlanValidator 或 instruction builder 窄测试：profile 上下文存在但不绕过 path/role。
