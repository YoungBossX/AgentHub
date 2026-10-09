# 任务组结果汇总验收

范围：`agenthub-group-result-summary` 1.1。本地单用户、SQLite/SSE，复用
现有 Message 和 Planner transports；未新增适配器、表、依赖或部署能力。
实现、实际原生运行、浏览器/恢复和最终回归已完成；本地未提交。

## 行为

- 新任务组在服务端计划消息中私有冻结协调器身份、提示词及 provider 参数。
  API 不返回原始提示词或私有配置。历史计划未授权该机制，不被自动改写。
- 根据最新 TaskRun 和同次 Diff/Review、版本及内容哈希生成有界输入；明确区分
  全部完成、部分失败、失败、等待继续。运行仍活动时不生成最终汇总。
- 完成要求所有最新运行和必要制品存在。Review 执行完成与评审判定分开：
  `passed`、`warning`、`failed` 都是已生成的评审结果，不表示运行失败或测试通过。
  只读 Diff 是快照，脚本评审和用户编辑结果都明确标注。
- 有原生协调模型时实际无工具调用，严格校验 JSON、组 ID、输入指纹和结果。
  未配置模型时显示确定性执行记录；配置模型失败时显示错误，允许单独重试汇总。
  汇总不改变已有 TaskRun 的成功、失败或中断状态。
- SQLite writer lock 下领取 owner/lease；提交前复核最新证据、冻结策略及协调器
  身份和目标权限。拒绝重复完成、旧 owner、过期租约、过期版本及撤销权限。
  重试保留历史，过期领取可在服务恢复后重新领取。
- SSE 在同次事务保存汇总事件与消息；首次运行前拒绝时由有限的 pending 状态轮询
  补充刷新。GET 不写数据库或调用模型；发布不改 Session.updated_at，以保留其它
  活动执行的冻结快照。

## 真实运行与浏览器

最终新会话 `572639f7-5771-427a-a151-1ff0b1bff368` 仅发送一条多 @ 消息。
真实 Claude CLI Planner、Claude 编码、指定原生只读评审和同一原生协调器汇总
先后完成。按钮实际改为 `Group Summary 20261008`，Diff 非空；评审完整 Read
文件哈希与最终源文件相同。汇总含冻结提示词的
`NATIVE_GROUP_PROMPT_20261008`，providerSource=real_llm，providerType=claude_cli，
引用的独立运行、制品和原生评审均与后端记录匹配。

浏览器显示实际解释、下一步、运行/制品详情及未运行测试说明；亮暗切换与刷新
通过。重启 API 后相同消息、输入/输出哈希、运行和源文件哈希保留，未增加重复
运行或汇总。SSE started/completed 各一条、指纹和消息 ID 一致，Last-Event-ID
跳过已有帧。

首次开发预演会话 `5892afce-bbc3-4717-b1bc-9012a83847a8` 发现 Review 制品
状态被误按 Diff 的 ready 检查，导致全部完成被误判为等待继续。该次不计验收成功；
修复了 Review 判定后，最终验收使用上述新会话及新模型执行。早期失败和停止的
测试运行均不计为通过。

## 验证

新增定向 API **31 passed**（194.42 秒），覆盖来源/自身制品、无工具冻结提示词、
无效输出、provider 错误与显式重试、重复领取/回调、过期 owner/lease、证据变化、
权限撤销、只读 GET/会话边界、历史计划及各原生 transport 的汇总契约。
Web **174 passed / 22 files**，包含结果卡片、历史/重试和 pending 轮询清理。
最终全量 API **1,651 passed / 1 POSIX-only skipped**（722.26 秒）；
`pnpm check`、strict OpenSpec、Git 空白检查和源码/证据哈希通过。

证据入口：[索引](evidence/group-result-summary/validation-index.json)、
[原生运行](evidence/group-result-summary/runtime.json)、
[浏览器](evidence/group-result-summary/browser.json)、
[重启与 SSE](evidence/group-result-summary/history.json)、
[开发历史](evidence/group-result-summary/development-history.json)。

静态模型评审和汇总未运行测试；原生 CLI 平台不证明底层模型厂商。本项没有新的
Preview/部署验收，没有安装依赖、提交或推送。
