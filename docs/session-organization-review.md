# 会话与关键消息整理验收

范围：`agenthub-session-organization` 1.1。本地单用户、SQLite/SSE；只增加
Session/Message 的展示元数据，不新增表、依赖、适配器或部署能力。
实现、真实运行、浏览器、重启及最终回归验证完成；本地未提交。

## 行为与边界

- 会话可置顶、取消置顶、归档、恢复。最近列表默认不含归档会话；归档视图和
  明确会话 URL 保留访问。两种列表支持搜索，置顶优先，其余按最近消息排序。
- 归档不改变 Session.status、updated_at、last_message_at、工作树、目标或记忆
  快照，不中断 Agent，也不删除消息、任务、运行或成果。恢复不重新执行任务。
- 消息置顶列表保留原对话顺序，可跳回原消息；置顶不修改内容、父消息、上下文
  或运行来源，不把消息自动加入可信记忆或 Agent 指令。
- 独立 PATCH 只更新显式提交的列，重复相同操作保持原置顶/归档时间。严格布尔
  输入，拒绝空请求、null、未知字段和跨会话消息；并发置顶与归档不会相互覆盖。
- 老 SQLite 数据库以可重复的增量升级补齐 nullable 字段，历史默认未置顶、
  未归档。状态来自后端持久化；SSE 较早读取响应不能覆盖刚保存的消息置顶。
  旧会话置顶请求延迟返回时，不覆盖或阻断新会话的首次历史消息加载。

## 实际运行

新会话 `ac5dccd4-55ed-4c4a-b0be-bd33ff94636d` 发送一次多 @ 请求。
测试在 TaskRun streaming 状态观察到含唯一请求标记的实际 Claude CLI 进程，
随后置顶会话、归档和置顶用户消息。进程命令行未导出。

整理期间执行字段与快照不变。真实 Planner、Claude 编码、独立原生只读评审及
原生协调汇总依次完成；每个任务只有一次运行，按钮实际改为
`Organization Native 20261008`。评审完整 Read 的文件摘要与最终文件一致。
已归档会话仍能查询任务、成果和完成汇总。

浏览器验收包含置顶/取消置顶、恢复/再次归档、关键消息跳转、刷新、桌面亮暗
和 390×844 窄屏，无嵌套按钮或页面横向溢出。重启 API 后会话、消息、运行、
评审及汇总记录完全相同；最终置顶/归档时间和源文件哈希保留，无重复执行。

## 验证记录

新增 API **17 passed**，覆盖旧库升级、排序/视图、幂等与可逆操作、严格输入、
会话边界和并发列更新。Web **184 passed / 24 files**，含置顶/归档、关键消息、
过期 SSE 响应保护及旧会话延迟置顶返回；`pnpm check` 通过。

首次全量 API **1 failed / 1,667 passed / 1 POSIX-only skipped**（989.48 秒）。
失败为既有 stale-event 围栏测试等待适配器启动的 1 秒超时；单独复跑通过。
该测试验证旧完成事件不能越过过期租约，未规定一秒启动 SLA。将启动等待上限
改为 10 秒，保留原围栏断言与清理。最终全量 API **1,668 passed / 1 POSIX-only
skipped**（948.60 秒），strict OpenSpec、Git 空白和源码/证据哈希检查通过。
早期新增测试缺少
intent_type 的夹具错误和前端类型错误均已修复，不计通过结果。

证据入口：[索引](evidence/session-organization/validation-index.json)、
[真实执行](evidence/session-organization/runtime.json)、
[浏览器](evidence/session-organization/browser.json)、
[重启](evidence/session-organization/restart.json)。

本项原生评审与汇总未运行测试，CLI 平台不证明模型厂商；未新增 Preview 或
部署验收。改动留在本地，未安装依赖、提交或推送。
