# 可执行自定义 Agent 验收

日期：2026-10-08。OpenSpec：`agenthub-custom-agent-execution` 1.1。

## 修复范围

原有安全草稿只能保存名称与能力，不能执行。现在复用 AgentProfileDraft 表，
增加 system_prompt、mention_alias、tool_policy 和工作区内别名唯一索引；旧数据库
补列/索引保留原记录，旧草稿保持不可执行。没有新增表、适配器或依赖。

Agent 目录支持创建、编辑、启用/禁用、取消与刷新恢复。自定义名称和 ASCII @ 别名
与固定 frontend/backend/review/orchestrator 角色分开；配置限定已注册目标、
角色能力、现有提供方与原生工具策略。拒绝保留/重复别名、未知或跨工作区目标、
平台写入、额外能力和任意工具配置。联系人只列出已启用档案，点击插入真实别名。
运行设置可选择兼容自定义档案，提供方与其工具策略绑定。

显式别名会记录 Task.agentProfileId；运行设置或显式选择均进入实际 TaskRun 创建，
不会仅改变展示名称。每次运行冻结档案身份、名字、提供方、能力、工具策略和提示词。
不关联的角色覆盖不会进入显式自定义指令；档案修改不会改变已创建运行。
提示词绑定必须匹配冻结档案身份。公开运行只显示名称、选择信息和摘要 receipt，
不含原文。历史任务名称使用运行快照。

请求准备和原有 SQLite 最终启动围栏内检查档案状态；即使请求准备后、执行绑定
提交后才禁用，也阻止适配器启动。工作树、队列、目标锁、文件范围、输出/Diff、
执行租约、完成判定及脚本兜底门禁保留。自定义脚本兜底只允许 demo frontend，
实际 adapter 来源继续明确记录。

## 工具与 Planner 边界

- Codex 编码沿用当前原生编码工具、CLI 沙箱、网络关闭与输出检查，没有声称移除 shell。
- Claude 文件编辑保留 Read/Write/Edit/MultiEdit；只读评审在 --tools 和
  --allowedTools 中均仅为 Read，并使用不支持文件编辑或 shell 的同一适配器变体。
  Review 的网关角色匹配与后台只读执行经受控适配器测试通过。
- 自定义 Planner 使用现有 Claude CLI，原生工具为空、strict MCP 配置，输出 JSON
  再交平台验证。请求与返回任务均受冻结的声明目标范围约束；确定性兜底继续明确
  标为 fallback，不作为自定义模型执行证明。

本地 `claude --help` 确认 tools、allowedTools 与 strict-mcp-config 开关存在。
工具策略和 Planner 输入/命令的验证是源码与测试证明，本项没有新真实 Claude 或
LLM Planner 执行验收，也没有新健康 Preview 验收。

## 真实浏览器与 Codex

继续使用验收专用 SQLite/API :8006 和 Web :3000。浏览器创建中文自定义名称、
别名、提示词、目标和能力，完成编辑、取消、刷新、默认运行档案选择及恢复。
联系人插入别名后发送演示应用按钮改动，手动开始运行：

- Profile：`6c880742-065f-40df-9eb3-deedb2083cda`，@ux-custom-20261008。
- Session：`cb667e1e-fe2a-4761-bcdc-9ece7d8edc77`。
- Task：`a6e92084-b17d-4501-9f39-83dcd4bff8e0`。
- 新真实 Codex Run：`7d091c25-63c5-452b-a84f-50315ec5e0a5`，completed。
- Diff：`224863a4-69b2-4a6f-b94b-8b9d37df36fc`，按钮改为 Custom workspace。
- 提示词：63 字符，custom_profile 来源，SHA-256
  `f03cebdb24c0fe1dd3c024bbec69c608358883c913f22af4ba7aa61e9111a647`。
- 精确持久原生事件：`3ad22b20-25d7-438b-8fa6-58af6cda7d5c`，最终模型消息包含
  仅来自提示词的标记 `AH_CUSTOM_AGENT_20261008`。

浏览器禁用后，新的 @ 别名消息返回 400，联系人移除；已完成运行仍保留冻结身份。
恢复原 Frontend 运行配置，并重启专用 API，档案的禁用状态和历史结果保持。
证据见 [runtime.json](evidence/custom-agent-execution/runtime.json)、
[设置](evidence/custom-agent-execution/settings.png) 与
[完成及 Diff](evidence/custom-agent-execution/real-run.png)。

初次浏览器请求命中旧 API worker，404；清理已核实归属的旧 worker、以同一专用
数据库启动后通过。截图脚本曾遇到同名标题的定位歧义，限定标题级别后通过，
没有重复执行模型任务。测试中发现的 Review 网关角色问题已实际修复；旧模型字段
契约断言也更新。

## 验证结果

- 最终全量 API：**1,491 passed / 1 POSIX-only skipped**，446.28 秒。覆盖既有
  作用域、锁、队列、租约、完成判定和三条适配器路径。
- 新增档案验证最终定向 **24 passed**；后台原生只读工厂/网关与最终启动后禁用
  围栏均通过。随后测试初始化改为仅使用覆盖数据库，避免新增 API 测试触发全局初始化。
- Web：**163 passed / 19 files**；新增编辑器的保存、同身份禁用、取消和拒绝用例通过。
- `pnpm check`：通过；最后 Web lint/TypeScript 再检通过。
- strict OpenSpec、`git diff --check`：通过；持久证据文件 SHA-256 已核对。

本项验收完成，改动仍在本地，未提交或推送。会话置顶/归档、多 Agent mention
的实际执行语义及真实 Claude/LLM Planner 验收继续留在后续独立任务中。
