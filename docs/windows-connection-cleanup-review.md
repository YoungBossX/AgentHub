# Windows 连接清理与退出验收

日期：2026-10-09；对应 `agenthub-windows-connection-cleanup` 1.1。
1.1 已完成（本地未提交）。范围为本地 Windows API 的一个已观察到的连接清理失败。

## 问题与修复边界

上一轮附件验收的原始 API 日志在 `_ProactorBasePipeTransport._call_connection_lost`
中记录了真实 `ConnectionResetError: [WinError 10054]`，位置为
`self._sock.shutdown(socket.SHUT_RDWR)`；后来服务停在 `Shutting down`。
本机 Python 3.12.7 的这条语句位于 finally 中，异常会跳过后续 socket.close、
Server._detach 和完成标记，导致 Server.wait_closed 等待未释放的连接。
该行为与 [CPython 3.12.7 源码](https://raw.githubusercontent.com/python/cpython/v3.12.7/Lib/asyncio/proactor_events.py)
一致。历史日志不能单独证明当时所有内部状态；控制实验补充验证了这条失效路径。

`scripts/local-api.py` 原本已有 5 秒优雅退出超时，外层启动器也有清理期限。
本次没有增大期限或更改事件循环策略，而是在 API lifespan 内安装局部异常处理器：

- 仅匹配 Windows Proactor、标准库真实绑定回调、WinError 10054、关闭中但未完成的
  transport，以及 traceback 中上述 socket.shutdown 源码行。
- 只补全 socket.close 和所属 Server 的 detach，标记已完成；不再次调用协议回调。
  按已安装的 detach 签名适配旧计数形式和较新的 transport 参数形式。
- 无法识别的运行时结构、其他异常和清理失败交回原处理器；恢复会留下明确日志。
- 正常退出、启动失败、清理失败均恢复原处理器；后装的新处理器不被覆盖。

未改 Python 安装目录、全局类、任务取消/租约逻辑、SSE、适配器、数据库结构或预览归属规则。
较新 detach 参数形式只有兼容单测及[上游源码](https://raw.githubusercontent.com/python/cpython/3.13/Lib/asyncio/proactor_events.py)
核对，本次实际运行环境是 Windows / Python 3.12.7，不宣称完成其他 Python 版本实机验收。

## 三类运行证据

1. **历史自然故障**：保留原始日志的有关片段、行号和原文件 SHA-256，见
   [historical-reset.txt](evidence/windows-connection-cleanup/historical-reset.txt)。
2. **普通断连压力样本**：独立 API 对 100 次 health 和 100 次 SSE 请求主动 TCP RST，
   没有复现该竞争条件，0.22 秒退出。此负面样本不能否定历史故障。
3. **精确故障注入**：保留真实标准库 transport、回调、实际服务端连接登记和正式
   `scripts/local-api.py` 入口，仅在 socket.shutdown 注入与历史相同的 10054。
   无新增产品故障路由。对照使用独立 SQLite 副本，baseline 仅关闭新恢复处理器。

| 正式入口对照 | 修复前 | 修复后 |
| --- | --- | --- |
| 注入连接的登记变化 | 多出 1 个、未释放 | 加入后释放，回到原值 |
| socket.close / 协议回调次数 | 0 / 1 | 1 / 1 |
| 退出日志 | 触发 graceful shutdown timeout | 无该超时，记录恢复 |
| 本次从 stop 输入到退出 | 6.285 秒 | 1.126 秒 |
| 进程退出 / API 与自有 Vite 端口释放 | exit 0 / 通过 | exit 0 / 通过 |

时间仅是这一组控制实验的观察值，包含预览清理，不是普遍性能提升指标。
两组均通过实际 Edge：SSE 历史回放 36 条，Last-Event-ID 后续 35 条且排除首条，
建立/关闭 EventSource，以及真实 Vite 标题和按钮 DOM。详见
[managed-report.json](evidence/windows-connection-cleanup/managed-report.json)。

## 当前工作台与持久化

确认当前 API 没有活动 TaskRun 并核对进程归属后，正常停止旧验收 API，使用正式
`local-api.py` 包装入口在 8006 启动新代码。保留既有 Web 3000 和无关 API 8000。
当前工作台重新创建两个自有 Preview；Codex/Claude 历史成果的 Vite DOM 和实际
工作台 iframe 均通过，浏览器无 pageerror。这里复用上一项已验证的真实模型输出，
没有进行新的模型推理。

原库、两份独立对照库及当前库重启后，对以下完整行集按 ID 排序计算哈希：
32 个 Session、98 条 Message、46 个 TaskRun、37 个 Diff、9 个 MessageAttachment，
均与重启前一致。附件二进制在行哈希前先取 SHA-256；同时验证没有非终态运行。
这不代表整个数据库字节不变：创建 Preview 会增加 Preview/Artifact 等记录。
历史模型成果的文件 SHA-256 在证据冻结时另行复核，不以 DOM 检查替代文件校验。

## 验证与冻结

- 新增 13 项连接清理测试；连同聊天事件、事件回放和 Preview，共 **62 passed**。
  覆盖真实标准库等待泄漏、重复回调、错误分类、清理失败可见、处理器所有权、
  detach 参数兼容和 lifespan 三种退出分支。
- 本地启动器/依赖安全测试 **17 passed**；根 `pnpm check` 退出 0。
- 全量 API 回归：**1,827 passed / 1 POSIX-only skipped**，1021.18 秒；本次退出码 0。
  原有 datetime.utcnow 等弃用警告仍存在，没有将其隐藏或作为本任务范围扩展。
- OpenSpec strict、空白检查和证据哈希通过，详见
  [冻结索引](evidence/windows-connection-cleanup/validation-index.json)。

冻结目录保存原始测试输出、对照日志/数据、历史哈希、浏览器结果/截图及验收脚本。
临时 SQLite 副本和私有 SDK 配置不进入证据。上一项附件验收索引保持原样；本项
另记允许变化的入口/文档以及未变化的 Agent 核心、附件和 Web 文件哈希。

整体项目尚有重新生成、通过对话创建 Agent、受限代码编辑和最终工作流验收，
见 [本地交付表](local-project-delivery.md)。本项不声明上线、多人或所有网络异常已解决。
