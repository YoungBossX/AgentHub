# Claude 原生执行修复验收

当前单任务：`agenthub-claude-native-execution` 1.1 完成（2026-10-08，本地未提交）。

## 问题与修复

Windows 编码适配器及两种健康检查此前可能直接启动 npm shim；CreateProcess
无法执行 `.cmd`。新增共享定位器，优先使用已安装的原生 `claude.exe`，兼容显式
路径和 POSIX，不引入 shell。Planner 与编码及检测使用相同定位规则。

真实 restricted 探针还暴露了凭据缺失：该模式忽略用户 settings，控制面的环境又
没有 Anthropic 凭据。服务端现在只从用户 `settings.json` 的 `env` 中复制明确允许
的 SDK 凭据、base URL、模型及模型别名；只接受绝对配置目录，文件读取限 256 KiB，
忽略缺失、无效或超大文件。显式进程环境覆盖设置，显式凭据不混入另一种设置凭据。
不导入项目设置、hooks/plugins/MCP/permissions、apiKeyHelper、NODE_OPTIONS 或
其他 provider/control-plane 密钥；不修改用户配置。

保持 restricted/safe mode、Read 或文件编辑工具、strict MCP、无会话持久化、预算和
精确命令守卫。stdout/stderr 使用 UTF-8。流增量与完整 assistant 快照按消息/文本块
合并，防止重复；凭据前缀跨增量缓冲脱敏，启动时环境用于后续精确脱敏。成功结果延后
至进程退出；非零退出、晚到错误、无结果和非对象 JSON 都不会产生成功完成事件。

## 验证记录

- 最终定向启动/配置/流/完成/守卫/档案/Planner/健康检查：235 passed。
- 最终静态检查与 strict OpenSpec 已通过。
- 最终源码新会话 `eeec9afc-6511-4ca8-80ac-3468abf4b348` 的真实编码与只读评审通过。
  编码 Run `418591c4-1353-4032-a045-1f9c6c1d7c85` 修改按钮并生成真实非空 Diff；
  评审 Run `1688109b-1246-4027-bde3-9c74b8287699` 使用原生 Read 策略及自己的回复。
  两个原生 completed 事件均在退出后记录 `exitCode=0`，容量最终释放，没有执行兜底。
- 两次回复中的仅来自配置的标记各出现一次；评审前后三个 demo 源文件 SHA-256 相同。
  `App.tsx` 为 `55a616bef82f083db84be53391515e95eadf7b31e02470d09b3dde41a2205c81`。
- 浏览器实际显示两次 Claude 运行与分开标注的脚本报告；刷新不新增运行。
  持久 SSE 重放还原两份输出各一次，末游标的 Last-Event-ID 不重复旧事件。
- 最终全量 API：**1,564 passed / 1 POSIX-only skipped**，741.79 秒，进程退出 0。
  `pnpm check`、strict OpenSpec、空白检查、源码与证据哈希核对通过；归档 JSON 无
  导入的 provider 密钥。未重复未变更的 Web/demo-api 测试，未安装依赖、提交或推送。

初轮真实写入和只读运行均 completed，源文件相等断言通过；验收脚本随后错误地从
Session Message 查找标记，而原生文本保存在 TaskRunEvent，因而断言失败。修正证据读取
位置后，使用新会话验证最终源码。初轮全量回归在补充完成事件围栏时停止，不计为通过。

## 证据边界

原生只读 Claude 的文本回复与后端自动创建的脚本 Review artifact 分别记录来源。
后者仍标记 `scripted_mock`，不能把脚本产物改称模型评审。CLI 是实际调用的执行
平台，用户所配置的 SDK 路由不证明具体模型厂商。本项没有新 Preview、部署或生产
环境验收；不把 provider/tool 限制声明为通用 OS/container sandbox。

持久证据：[运行与源码摘要](evidence/claude-native-execution/runtime.json)、
[执行界面](evidence/claude-native-execution/execution.png)、
[脚本报告来源](evidence/claude-native-execution/scripted-report.png)、
[验证索引](evidence/claude-native-execution/validation-index.json)。
