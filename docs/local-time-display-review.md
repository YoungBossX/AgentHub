# 本地时间显示验收

范围：`agenthub-local-time-display` 1.1，前端时间解析和既有时间展示。
实现、边界测试、实际浏览器与最终检查完成；本地未提交。

## 时间契约

后端 `utc_now()` 和 SSE 的 `_naive_utc_now()` 都生成无时区的 UTC datetime，
现有 SQLite/Pydantic 响应保持该契约。本轮不改后端存储、API、执行租约、记忆
快照或原生执行。前端把无偏移时间明确解释为 UTC，Z/显式偏移按实际 instant
解析，不使用浏览器本地 `Date.parse` 猜测。

共享解析器拒绝非法日期、时分秒、偏移和只有日期的字符串，避免把 2 月 30 日
滚动成 3 月。JS 展示精度为毫秒；完整原始 API 小数字符串保留在悬停详情中。
排序和 TaskRun 生命周期重叠沿用 instant 比较，展示与搜索采用同一本地时区。
SSE 仍只保留允许的事件字段，原始时间不会使私有 payload 进入界面。

侧栏最近时间、Preview 检查时间和执行事件统一使用 `<time>`：正文为本地时间，
datetime 为标准 UTC instant，悬停含完整显示时间、IANA 时区、该时刻偏移、
UTC 和原始值。侧栏、Preview、事件列表有时区标识；预览时间单独占一行，
防止窄成果面板截断正文。未知/无效值保持原文，缺失值显示等待/暂无状态。

服务端及客户端首次快照固定 UTC，通过 useSyncExternalStore 的 server snapshot
在 hydration 后读取浏览器时区；不使用 suppressHydrationWarning 掩盖差异。
实际浏览器发现 Node 的 `GMT` 和浏览器的 `GMT+00:00` 使 title 首次加载不一致，
现已统一为 `UTC+00:00`，最终三时区均无 hydration 或页面错误。

## 验证

Web **209 passed / 25 files**（5.91 秒），包括无偏移/微秒/Z/显式偏移、相同
instant 的排序、跨年跨日、纽约 DST 跳跃/回拨、14 类非法输入、原始值保留、
SSR/本地 hydration、事件与重叠严格校验及侧栏显示时间搜索。
`pnpm check`、strict OpenSpec、Git 空白、源码/证据哈希通过。

实际 Edge 浏览器使用现有已完成会话
`ac5dccd4-55ed-4c4a-b0be-bd33ff94636d`，分别在 Asia/Shanghai、America/New_York
和 UTC 环境读取实际 API/SSE。相同 `2026-10-08T05:25:18.739767` 在侧栏显示
13:25、01:25、05:25；原始微秒值和 UTC datetime 相同。60 条事件均能对应
实际 SSE 时间，刷新、亮暗和 390×844 窄屏通过。开始和结束的 Session、Message、
TaskRun 完整 API 记录相同，未新建运行或修改历史。

Preview 验收使用会话 `cb667e1e-fe2a-4761-bcdc-9ece7d8edc77` 的实际已有记录，
`2026-10-07T15:13:23.929900` 显示为上海时间 10 月 7 日 23:13，正文、
datetime 与 API 响应对应。该历史 Preview 在当前服务重启后为 unhealthy，
界面诚实显示失败；本轮验证时间展示，不声称重新启动或健康 Preview 验收。
既有 Preview GET 的健康检查可能更新其健康元数据，时间组件本身没有写请求。

首次 Web 为 **1 failed / 207 passed**，因原测试要求整段拼接文案；现改验语义
datetime、原始值、状态和动作。早期浏览器脚本误用按钮名、误选含“成果”的侧栏
会话，以及等待所有响应体的无上限问题均已修正；这些运行不计为最终通过。

本轮未修改 API 源码，上一项冻结的 9 个 API 文件哈希与当前版本相同；没有重复
全量 API 或模型执行，不把上一轮 API 数量作为本轮新测试结果。未安装依赖、
提交或推送；本地启动/恢复与最终完整工作流交付仍需独立验收。

证据：[索引](evidence/local-time-display/validation-index.json)、
[实际浏览器与记录](evidence/local-time-display/browser.json)、
[测试](evidence/local-time-display/web-tests.txt)、
[静态检查](evidence/local-time-display/static-checks.txt)、
[窄屏事件](evidence/local-time-display/events-narrow.png)。
