# 预览重启恢复验收

范围：`agenthub-preview-restart-recovery` 1.1，本地 Vite React Preview 生命周期。
实现、实际浏览器验收和最终全量回归完成；本地未提交。

## 修复

API 重启后，内存中的 Popen 记录丢失，数据库中的 PID 不能证明进程归属。
新增 `tracked` 诊断：未知 PID 不进行 HTTP 信任或发出停止信号，旧 Preview
标记为 unavailable/unhealthy 并保留原 Artifact、来源和明确的 ownership 提示。
已观察到的进程退出仍保留退出码和脱敏输出；运行后退出不再误称“启动前失败”。

正常 API 退出关闭当前 Runner 创建的进程树及日志句柄。锁与关闭标志处理启动/
清理竞争；清理失败保留当前进程句柄供重试，禁止带着未清理进程重开 Runner。
群聊 worker 异常也不跳过清理。服务重新进入 lifespan 时使用新的 Runner。
不增加 PID 接管、扫描/终止未知宿主进程或数据库迁移。

显式刷新先读取后端最新健康状态：有健康 Preview 时复用，没有时创建并选中
新的 Preview。异常或停止卡片显示“重新启动预览”，继续阻止打开和部署。
Diff/Review/Preview 分批读取时保留显式选择，防止新预览尚未进入列表就被面板
跳转到评审报告。会话切换继续清空选择。

实际 Windows 分配到 1719 时，后端 HTTP 健康检查通过，Edge iframe 被禁止。
1719 在 [Chromium 官方限制列表](https://chromium.googlesource.com/chromium/src/+/133.0.6943.98/net/base/port_util.cc)
中。默认分配现在直接尝试随机 `16384..65535` 候选端口，实际 bind 检查占用，
最多尝试 64 次，耗尽明确失败；不依赖可能始终位于低段的系统临时端口范围。
端口检查与 Vite 启动之间仍存在分配竞争；既有启动/健康检查如实失败并允许重试，
不把“预留”声明为持有监听套接字直到 Vite 启动。

## 实际验收

使用已完成的原生编码会话 `ac5dccd4-55ed-4c4a-b0be-bd33ff94636d` 和写运行
`5542f62c-70cf-45d5-a6dd-419e175c5b3c`；本轮不新建模型执行。
页面实际按钮为 `Organization Native 20261008`，与 canonical 文件哈希对应。

- 浏览器持有健康 Preview `e3c4956c-97ab-4ec0-8f16-daea8aa679e3`（51261）。
  受控异常退出本轮测试 API 后，旧 Vite 仍 HTTP 200，PID 创建时间不变。
- 新 API 读取旧记录后显示 ownership unavailable，清空记录的 processId；旧
  Vite 仍存在，证明没有接管、误停或把其 HTTP 响应当作本实例健康预览。
- 保持原浏览器，一次显式动作、恰好一个 Preview POST 创建
  `c83fdbe8-e16e-4421-bb73-7273fdb31e24`（21480）。新 iframe 加载实际按钮，
  旧记录保留；刷新、暗色交互和 390×844 窄屏无页面错误/横向溢出。
- 通过 Uvicorn 正常退出执行 lifespan：21480 及当前服务创建的进程关闭；
  失去归属的旧 Vite 仍存在。本轮测试进程另经 PID/创建时间校验后单独清理，
  不把测试清理描述为产品自动终止未知进程。
- 再次启动 API，从异常卡片一键恢复并刷新，恰好一个 POST、新健康 iframe
  和打开/部署门禁通过。最终仅保留当前 API 拥有的健康预览供本地查看。

恢复前、浏览器恢复后、正常退出/重启后和最终冷启动恢复后，完整 Session、
Message、TaskRun API 记录逐项相等，源码字节哈希相同。Preview GET 可能更新
Preview/Artifact/Event/ledger 元数据，不声明整个数据库只读或完全不变。
Scope、依赖/集成、保护路径与部署约束沿用已有逻辑。

当时即时截图呈现暗色成果卡片白底浅字，本轮暗色验收仅证明恢复操作与页面加载。
后续 [主题一致性核查](theme-transition-consistency-review.md) 证明稳定配色正常，
实际为切换瞬态色差，已通过新任务修复并逐帧复验；原始截图继续作为历史证据保留。
个人项目启动入口/文档与最终全工作流交付继续独立推进。

## 检查与复现

最终定向 API **60 passed**（2.75 秒）、Web **212 passed / 26 files**（7.57 秒）；
最终全量 API **1,676 passed / 1 skipped**（923.15 秒）；跳过项为当前 Windows
无法表达的 POSIX 精确大小写语义。`pnpm check`、strict OpenSpec、Git 空白、
源码/证据哈希及私有 SDK 配置值排除检查通过。
测试包含未知归属不信任/不停止/只发一个失败事件、历史保留、退出文案、
关闭幂等/失败重试/启动竞争、worker 异常清理、候选端口占用/耗尽，以及
缓存健康状态变化、健康复用和成果分批到达时的选择保持。

本地复现：启动 API/Web，选择已有完成的 frontend TaskRun 启动预览，正常
停止 API 后重启，打开原会话成果，点击“重新启动预览”。应创建新 Preview，
保留旧制品及编码/评审记录，页面展示同一源码；不会自动重跑模型。
不要通过结束未知 PID 来替代恢复。异常退出可能留下旧进程；新实例不会认领它。

早期浏览器脚本的英文 iframe 标题、选择第一份历史卡片以及临时验收服务器的
Python import path/端口占用问题不计为通过。实测揭示的面板选择竞争、1719
浏览器限制和低段系统端口范围均已修复并重新验收。
此前全量检查分别为 1,672 passed / 2 skipped、1,674 passed / 1 skipped 和
端口调整中间版本（1,676 passed / 1 skipped）；这些记录不替代最终当前源码
的完整复验结果。
未安装依赖、提交、推送或部署生产。

证据：[索引](evidence/preview-restart-recovery/validation-index.json)、
[实际浏览器](evidence/preview-restart-recovery/browser.json)、
[退出清理](evidence/preview-restart-recovery/graceful-shutdown.json)、
[记录与源码](evidence/preview-restart-recovery/execution-lineage.json)、
[真实按钮](evidence/preview-restart-recovery/visible-source.png)。
