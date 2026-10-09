# 对话创建 Agent 验收

日期：2026-10-09；`agenthub-conversational-agent-creation` 1.1 完成（本地未提交）。

## 当前行为

聊天侧栏联系人旁增加“对话创建”，进入 Agent 目录的创建对话。输入职责、目标和
输出偏好后，使用工作区当前 Planner 返回澄清问题或完整配置草稿。可以继续补充
需求，也可以直接修改名称、别名、提示词、目标和工具策略；后续生成携带当前手工
修改。普通编程聊天不变，配置请求不会误入代码任务派发。

配置助手沿用已有 Planner 传输，使用无工具 JSON 契约。Claude CLI 禁用工具、MCP
扩展与自动项目配置，创建上下文通过 stream-json stdin 传入，避免 Windows 命令行
长度限制。API 提供方使用对应配置结果 schema。没有新 adapter、依赖或数据库列。

角色、目标、工具策略、提供方、能力和别名必须通过与正式保存相同的验证；目标
不得是平台维护目标，自定义 Planner 还受其目标范围限制。生成调用后重新核对
当前规划身份与配置。JSON 重复键、未知字段、超长、权限越界或不完整输出均拒绝。
对话最多最近 10 条、连同新请求 16,000 字符；单条 4,000 字符，模型输出 32 KiB。
只传配置对话和注册目录，不附加其他 Session、文件、记忆或凭据。

生成不保存 Profile、Message、Task 或工作树修改。草稿默认停用，用户检查配置后
可勾选启用并显式保存，复用既有自定义 Agent 接口。保存成功但目录刷新失败时明确
告知已保存；编辑器记住已返回的 Profile ID，避免再走创建请求。未配置或已停用
Planner 时明确引导运行设置，不以模板假冒模型生成；手动配置继续可用。

草稿、最近对话和手工编辑存于按后端/工作区隔离的 sessionStorage。同一标签页
刷新后打开创建对话即可恢复，存储不可用时提示仅保留当前页面。生成期间禁用提交
和表单修改；作用域切换/离开后的迟到响应不更新其他草稿。收起不丢弃正在生成的
对话，重新开始需要确认，且不删除已保存的 Agent。关闭标签页不是服务端草稿归档。

## 自动检查

- 新增后端 **28 passed**：无生成副作用、手工编辑/多轮、显式保存、重复别名、
  权限/角色/目标/字段边界、坏 JSON/重复键/超长、提供方失败/禁用/配置变更、
  请求预算，以及真实 CLI 命令构造与 API schema。
- 现有自定义 Agent、旧草稿、Planner 提供方和结果汇总回归 **123 passed**。
- 新增前端 7 项；与编辑器合计 10 passed，Web 全量 **256 passed**。覆盖恢复、
  澄清/失败保留、手工编辑续接、重复点击、工作区切换、保存后刷新失败和损坏存储。
- 全量 API **1,872 passed / 2 skipped**，1,087.69 秒。两个跳过分别是 Windows 上
  不适用的 POSIX 大小写用例，以及该次宿主未暴露瞬态目录位。35,391 条既有 UTC
  时间弃用警告保留。根 `pnpm check`、Next 16.3.8 生产构建、strict OpenSpec 与
  空白检查通过。
- 第一轮新增测试因超长参数被 pytest 用作环境变量中的测试 ID，触发 Windows
  32,767 字符限制；改为短测试 ID 后 28 项通过，测试输入长度和拒绝断言不变。

## 新鲜原生与浏览器证据

首先实际验证未启用 Planner 返回 409，草稿输入保留。首次验收脚本尝试启用 Planner
时漏传已有 Agent Profile ID，被既有运行设置校验拒绝；未发生模型调用或创建。
修正验收脚本为选定现有规划 Agent 后，通过真实模型生成和二次调整。

生成结果为 `claude_file_edit`、`demo-frontend` 的前端 Agent；第一轮没有保存档案，
第二轮保留手工职责说明 `MANUAL_DESCRIPTION_731`。再次手工改名后刷新，名称与
System Prompt 恢复。通过真实主题按钮切暗色，1440px/390px/320px 截图和创建表单
DOM 溢出检查通过；保存后的状态、目录与提示准确。

用户显式勾选启用、点击保存，创建 Profile
`faab6604-01ed-492a-9016-fb24162b0cda`，别名 `created-front-731`。
随后在新 Session `e0adc0ee-f427-4c98-9fc1-7c4fa40e867b`，通过真实规划 Agent 和
这个新前端 Agent 修改标题；任务请求未包含预期标题文字，而是要求采用该 Agent
自己的系统约定。运行 `620bfd10-454d-4f3c-a211-6c1bc6eb0b77` 的冻结身份、
`claude_file_edit` 工具策略、提示词来源 `custom_profile` 和 Profile ID 匹配。

实际源码、Diff `d8fba886-576b-495c-a611-ff333bbb0df0`、Vite 页面及工作台 iframe
都显示 `Created Agent 731`；源码 SHA-256 为
`659ad96c50c7dd98f9eacc37acd155cfa2dd0fd5aef2e5b3591c4061ca948a69`。
这证明该样本提示词进入实际执行，不以配置保存或 UI 展示代替运行验证。

## 持久化与范围

验收临时启用工作区 Planner，完成生成后通过正常接口恢复原配置。原配置内容
完全恢复，只有正常保存引起的 updated_at 更新；另一个旧 Task 的 updated_at
由既有调度器更新。原 1 Workspace / 35 Session / 109 Message / 65 Task /
48 TaskRun / 39 Diff / 11 Attachment / 5 自定义档案的其他字段和行内容保持一致。

当前 API 已通过正式入口正常停止并重新启动。新 Profile 的完整行、原生会话消息、
任务、运行、Diff 和源文件哈希在重启前后相同；未重跑模型。运行设置恢复为原来的
Planner 停用状态，避免验收改变用户默认行为；已保存的新 Agent 可由别名显式使用。
重启后的实际目录编辑器仍显示相同提示词，新预览
`4e85db0f-5f1d-4efa-9ea5-daef23a29aee` 健康，工作台 iframe 仍显示 `Created Agent 731`。

证据、首次诊断与实际浏览器截图见 [证据目录](evidence/conversational-agent-creation/)，
代码、文档和检查记录由 [冻结索引](evidence/conversational-agent-creation/validation-index.json)
标明。SQLite 备份和 SDK 凭据不进入证据目录。未提交或推送。

整体项目仍有受限代码编辑/应用 Diff 和工作流/UI 终验，见
[本地交付表](local-project-delivery.md)。此项不扩展多人平台、任意工具或部署能力。
