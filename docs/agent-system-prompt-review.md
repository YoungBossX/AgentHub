# Agent System Prompt 修复验收

日期：2026-10-07。OpenSpec：`agenthub-agent-system-prompt` 1.1。

## 问题与实现

原有 Agent.system_prompt 虽然有种子数据，但编码 instruction builder 没有使用。
运行设置也缺少工作区提示词字段。现在既有 Planner、Frontend、Backend、Review
配置支持多行 System Prompt、保存和取消；留空继承默认，禁用配置不使用覆盖值。
字段复用 AgentRuntimeConfig.roles_json，无新增表或依赖，最大 8000 字符，拒绝
非字符串和 NUL。保存设置与更换提供方不会丢失提示词。

编码 TaskRun 创建时冻结有效文本、工作区/Agent/角色、来源与 SHA-256。准备请求
只读取该绑定，调用者的 planContext 不覆盖它；配置修改影响新运行，重试重新解析。
旧 queued TaskRun 在首次准备请求时，通过既有上下文持久化/CAS 冻结。已有绑定的
身份或摘要损坏会在调用 Provider 前失败。公共 metrics 仅返回 source/hash/字符数
receipt，原文保持私有，不进入 runtimeConfigResolution。

提示词作为行为说明进入 Codex/ClaudeCode 的既有执行指令；目标、角色、验证和
Guardrails 始终保留，权限门禁没有变化。LLM Planner 使用同一有效值解析规则，
经过既有脱敏与 prepared payload 流程，四条既有 transport 把提示词置于强制
JSON/规划安全契约之前。确定性 Planner、脚本兜底和脚本 Review 不执行模型提示词。

## 真实本地运行

使用上一项验收专用的独立 SQLite/API :8006 和 Web :3000，没有修改用户原数据库。
浏览器在 `/settings/runtime` 选择内置 Frontend/Codex，保存中文多行提示词，刷新
后文本保持，修改后取消恢复原文。原文额外要求最终回复包含
`AH_SYSTEM_PROMPT_20261007`，用户聊天消息不包含该标记。

- Session：`cb667e1e-fe2a-4761-bcdc-9ece7d8edc77`。
- Task：`4d781bbc-b36f-4a4c-8bc2-e827cd7075d2`。
- 新真实 Codex Run：`55ec6ecc-52db-4528-a408-cb0153b6096f`，completed。
- Diff：`9b0e67d8-be36-4603-a886-ad0e2532d563`，按钮从 Enter project 改为 Enter workspace。
- Prompt receipt：workspace_override，135 字符，SHA-256
  `8f2922edff1f09afc840b54d5a12af0967583680fae716e519f2c833dd8879e6`。
- 精确持久事件：`74ec440d-616d-4210-af91-ed415d598685`，message.delta 包含
  Codex 原生 item.completed / agent_message；最终回复为中文，并包含指定标记。

最初浏览器脚本使用过严的 label 匹配，修正定位器后保存检查通过；它又错误地
把 diagnostics 摘要当作完整模型日志。该接口有意省略全文，因此补查精确
TaskRunEvent 确认最终回复，没有重跑、替换或伪造此次实际 Run。

证据：[运行 JSON](evidence/agent-system-prompt/runtime.json)、
[设置截图](evidence/agent-system-prompt/settings.png)、
[完成截图](evidence/agent-system-prompt/real-run.png)。
截图不替代实际事件与文件差异。本项没有重新验收健康 Preview，也没有真实
Claude/LLM Planner 演练；Planner transport 生效目前由构造与契约测试证明。
验收结束已将专用工作区的临时 Frontend 提示词和运行覆盖恢复为继承默认；
历史 Run 的私有冻结文本与公共 receipt 保持不变。

## 自动验证

- 聚焦配置/执行/继承/损坏绑定：18 passed。
- 相邻回归：547 passed，覆盖完整 TaskRun、运行围栏、记忆与 Planner/provider 构造。
- Web：160 passed / 18 files。
- `pnpm check`：通过，包含 Web ESLint/TypeScript、API compile、demo 前后端检查。
- strict OpenSpec、`git diff --check`：通过。
- 修改后全量 API：**1,465 passed / 1 POSIX-only skipped**，441.65 秒；新增 API
  保存/拒绝用例也已包含在内。不重复累计前述聚焦回归。

本项只闭合提示词配置与执行。可执行自定义 Profile、工具集约束、联系人 mention
绑定仍是下一项独立任务；未增加 Adapter、市场、生产部署或任意工具权限。
