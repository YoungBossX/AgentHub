# 消息文件与图片附件验收

范围：`agenthub-message-attachments` 1.1，2026-10-09。本项补齐本地消息附件从
上传、显示、规划/执行输入到实际文件结果的链路，已完成本地验收，未提交/推送。
本页区分实际模型结果、线格式测试及尚未消除的运行限制。

## 实现与边界

- 新增 `MessageAttachment` 支持表；SQLite `create_all` 增量创建，旧表没有重写。
  原始字节、处理图像、提取文本、哈希、Session/Message 身份持久化；绑定一次后
  不再修改。批量绑定在消息事务内完成，外会话、重复、已发送及失效 ID 整体拒绝。
- 原始字节上传不接受本机路径。限制扩展名和真实格式、8 MiB/文件、4 份/消息、
  256 份/会话及 128 MiB 原始文件总量。文本 512 KiB，PDF 100 页，图片 1200 万
  像素/单边 10000；解析子进程 15 秒超时，不继承模型凭据，不执行文件内容。
  PDF 解压流与递归另有限制。这不是 Docker/OS 沙箱，也不是通用恶意文件隔离器。
- 图像统一方向、白底合成透明区域，缩到最长边 2048 并编码 JPEG。只读图片预览
  与原文下载分开，均按 Session 验证身份；下载带 nosniff、no-store 和 sandbox。
- 当前/引用/置顶/最近消息的附件使用同一权威选择器。只取同会话数据库记录，
  忽略伪造的附件对象。先过滤保护内容，再截断；24,000 序列化字符、12,000
  字符/文本、最多 4 图/8 MiB 图像输入。保留来源、哈希、截断与省略记录。
  这些内容是 `conversation_reference`，不会升级为系统指令或工具授权。
- Canonical context 和持久化请求只记录文字及来源。二进制通过私有类型传给
  Provider，不写入 JSON 快照或事件。HTTP Responses、兼容 Chat 和 Anthropic
  图像结构通过线格式单测；这些测试不等同实际远端模型推理。
- Codex 使用 stdin 文本和严格匹配的服务端临时 `--image` 文件，未扩大
  `--add-dir` 或沙箱权限；结束、启动失败及中断后清理。Claude 附件请求使用
  stream-json stdin，保留既有工具策略，忽略回显用户图像的输入确认事件。
  大文件内容不放进 Windows 命令行。ScriptedMock 的无附件路径保留；有附件时
  显式失败，不能假装读懂文件。
- 输入框显示上传、就绪、失败、移除状态；同会话草稿可恢复，跨会话异步响应
  不串线。已发送历史显示图片、下载、提取状态及来源。规划失败但已持久化时，
  恢复消息并清除绑定过的草稿，避免重复发送。长任务标题导致消息网格溢出的
  问题一并收敛为 `min-width: 0` 与明确单列网格。

限额的 128 MiB 指原始上传量，不代表 SQLite 总文件大小；处理后图像和文本另占
空间。已绑定文件不会被后台清理；未绑定文件仅在同会话后续上传时清理过期项。
刷新不会恢复未发送的浏览器草稿。扫描 PDF 只显示未提取到文字，没有 OCR。

## 新鲜原生结果

验收固定文本只包含标题 `Aurora Workshop 617`，固定图片像素只包含按钮文案
`Cedar Beacon 842`；用户任务指令没有重复这两个值。

| 路径 | 新 TaskRun | 确认结果 |
| --- | --- | --- |
| 直接路由 → Codex 文件与图片输入 | `543adcb8-629c-4e22-bce2-8ef87cd0e6e0` | 实际源码与 Diff 同时出现标题和按钮文案；健康 Vite DOM 与工作台 iframe 均匹配 |
| 真实 Claude Planner → Claude 编码，文本附件 | `a9d723ac-4a05-40ec-b52b-70f3a5cc429f` | 原生规划从文件取得标题，编码源码/Diff/健康 Vite DOM 匹配 |

Codex 一例是直接任务路由，不能声称验证了真实图像 Planner。Claude 一例只证明
该本机路由的文件文本能力，不证明 Claude CLI 背后一定使用 Anthropic 模型。
实际图片探针被当前模型以 `Model only support text input` 拒绝，改为优先提取
结构化终态错误，显示 `PLANNER_IMAGE_UNSUPPORTED`，不会用 stderr 模型名警告
遮蔽原因。这是保留的模型能力限制，不伪造视觉成功。

## 浏览器与持久化

实际 Edge 验证了上传/发送、原文下载 SHA-256、历史重载、上传错误阻止发送及
删除未发送附件。1440/390/320 像素宽度的亮暗主题共 6 组均无消息气泡横向溢出，
图片解码成功，无捕获到的页面 JavaScript 错误。后续异步切换/无文字 PDF/
真实不支持图片的错误恢复结果记录在 `attachment-edge-cases.json`。

重启前后核对了上述两次运行的完整 metrics 哈希及原文/规范图像哈希，完全一致；
升级前已存在的 91 条 Message、35 条 Diff、44 条 TaskRun 全字段保持一致。
新生成的消息、Agent 档案、任务与 Preview 属于本项操作，不声称整个数据库不变。

一次临时 API 验收进程停止在关闭端口阶段，未完成退出。核验 PID/命令归属后，
只终止该进程及它启动的预览子进程；新服务恢复后重新启动两份健康预览，实际 DOM
和工作台 iframe 通过。此记录证明附件在进程恢复后持久化，不把该次退出称为正常
关闭通过；临时验收启动脚本另设有界 graceful-shutdown 等待，未改生产启动行为。

## 检查与证据

- 附件、命令/传输、模型边界及异常上下文定向：45 passed；之后增加 Codex 中断
  清理检查，纳入最终全量。
- Web 全量：29 文件、242 passed；本地工具 17 passed，实际 `doctor:local`
  依赖/端口检查通过，包含新增的 PDF/图像解析依赖；根 `pnpm check` 和
  Next 16.3.8 构建通过。
- API 最终全量：**1,814 passed / 1 POSIX-only skipped**，1124.36 秒。
  初次暴露支持表允许列表及异常 context 字典兼容问题，
  均已修复；下一轮的单个失败位于既有归属围栏测试的 1 秒准备等待，单独重现通过。
  准备等待改为 10 秒，原 0.5 秒替换归属阻断断言保持不变。
- 实际 UI 补测发现恢复后的规划错误被通用网络提示遮蔽，改用既有 API 错误类型，
  真实拒图重测确认显示原因、保留一条消息/附件、清空草稿且未创建假任务。
- strict OpenSpec、空白检查通过；源码、文档、验收材料及未改动基线均按 SHA-256
  冻结核验。机器相关辅助脚本仅用于追溯这次验收，不是新的推理结果或通用重放器。

参考实现约束来自 [pypdf 安全配置](https://pypdf.readthedocs.io/en/stable/user/security.html)、
[Pillow 安全说明](https://pillow.readthedocs.io/en/stable/handbook/security.html)、
[OpenAI 图片输入](https://developers.openai.com/api/docs/guides/images-vision)、
[Anthropic 图像输入](https://platform.claude.com/docs/en/build-with-claude/vision) 和
[Claude CLI 参数](https://code.claude.com/docs/en/cli-reference)；原生链路另以实际 CLI
与 UI 运行验证。冻结文件索引为 `docs/evidence/message-attachments/validation-index.json`。

本项不包括消息重新生成、通过对话创建 Agent、用户编辑并应用任意 Diff、上线部署、
多人平台或 MCP 市场。整体项目剩余工作保留在 [交付表](local-project-delivery.md)。
