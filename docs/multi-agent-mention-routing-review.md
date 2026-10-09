# 多 Agent 显式指派修复

日期：2026-10-08。对应 `agenthub-multi-agent-mention-routing` 1.1。

原来 `parse_mentions` 可以解析多个角色，但 `plan_for_message` 只使用第一个。
这让群聊联系人选择和实际执行不一致。当前多个明确角色进入
`explicit_group_v1`，使用现有任务、依赖、队列、目标锁和执行链路。

## 行为与边界

- 群聊点击联系人按选择顺序保留多个别名和正文，重复点击不重复添加。
  单聊选择会替换开头的角色列表；切换模式不会发送或执行。
- 每个明确编码角色都有任务，写入保持顺序。评审排在全部写任务之后；
  同时涉及前后端时分别生成绑定对应目标的评审任务，不扩大单次只读范围。
- 一次请求最多两个写角色、两个评审角色，每个评审角色最多覆盖两个目标，
  共六个执行任务。内置 Orchestrator 可在任意 mention 位置，协调来源明确为确定性。
- 全组任务、目标/路径/能力、自定义档案和依赖检查后，与协调消息一起提交。
  未知、禁用、同角色不同档案、越界目标或平台维护请求失败不保留部分任务。
  原始用户消息仍保留，延续现有消息 API 的行为。
- 自定义执行角色保留档案 ID/名称/别名，并在 TaskRun 创建、实际启动时沿用原生
  工具策略和权限检查。外部目标的自动文件提示只包含允许路径。
- 编码任务自动生成的脚本报告不能替显式评审角色完成任务。内置 QA/Review
  使用现有 ScriptedMockAdapter 的只读分支，生成自己的运行和报告；不修改文件，
  不声称调用模型或运行测试。真实自定义 Claude 评审仍走既有受限路径。
  评审任务的 Diff 是当前目标的累计 Git 快照，不代表评审产生了新的文件改动。
- 本任务保持显式指派的手动启动方式；请依次启动就绪任务。没有原生 Planner 调用、
  任意 DAG 构建或新增 Agent 平台。自定义 Planner 与执行角色混合指派目前明确拒绝，
  可单独使用其别名进入原生规划；其整组规划后续单独实现。

## 验证

最终 API 全量 **1,511 passed / 1 skipped**，465.11 秒；Web **167 passed / 20 files**，
demo-api **5 passed**。`pnpm check`、strict OpenSpec、`git diff --check` 和持久证据
SHA-256 核对通过。新增整组测试 **20 passed**，DAG/执行工作树/整组定向 **55 passed**。
针对性测试覆盖顺序、去重、HTTP 恢复、事务回滚、
自定义身份、外部目标/跨工作区、失败依赖、评审来源和真实临时 Git 写入后只读评审。
新增只读状态导致原有继承测试适配器缺少初始化，已修正测试夹具调用父类初始化，
并保持普通 ScriptedMock 工厂的无参构造形式；原有安全门禁没有放宽。
最初全量因该兼容问题中止；文件提示过滤修正后重新启动最终全量，没有累计初轮
未完成测试作为成功。Windows 首次 demo-api 命令因 PATH 中缺少 Bash 未执行测试，
使用已有 Git Bash 的过程级 PATH 后上述 5 项通过，没有安装依赖。

最终全量日志位于本机临时验收目录的 `api-group-full3.log`；证据清单保留可核对
结果和截图哈希，不将本机临时目录当作远程交付。OpenSpec 1.1 已完成，未提交或推送。

## 本轮浏览器与真实运行

在既有独立验收 SQLite、8006 API 与 3000 Web 中新建 Session
`d30788d8-2434-435e-a2ed-4c590a34e9f6`，由联系人选择形成
`@frontend @qa 把演示应用的按钮文案改成 Group workspace`。

Frontend 任务 `45bebce6-953c-4cf2-9763-46609ed6aede` 的真实 Codex 运行
`a44eaf3a-b58d-48ff-9d8b-ed5c2d977f1a` 完成，匹配 Diff
`cc9664b1-8607-420d-b4c7-20615a6f0a53`。自动生成脚本报告后，显式 QA 仍未完成。
随后独立 QA 任务 `629c32f2-62f5-4fbc-903a-e90843325924` 的只读 ScriptedMock 运行
`b1af7b2a-9f1a-404d-b49a-c8e4ab6b8a7c` 完成，生成自己的评审记录
`84017326-68b9-4cb2-a685-9270b21130be`。

评审前后的 `App.tsx` SHA-256 都是
`1b61ef659f4d3e40293a4d69edb351109f3a619a555bc8b5bb934c913e110446`。
刷新后任务、依赖和报告保持可见，平台整组请求返回 400，任务数未增加。
最终源代码启动的 API 再次重启后，上述完成状态、角色、依赖和脚本报告仍可从
SQLite 恢复；浏览器显示“只读脚本评审完成”，没有新增运行。
首次浏览器验证连接的旧 reload worker 仍使用此前路由，未纳入成功证据；
核对并重启自有 8006 进程后完成上述新会话验收。

证据入口：[runtime.json](evidence/multi-agent-mention-routing/runtime.json)、
[write.png](evidence/multi-agent-mention-routing/write.png)、
[review.png](evidence/multi-agent-mention-routing/review.png)。
本轮没有新的 Preview/部署、真实 Claude 或 LLM Planner 验收。
