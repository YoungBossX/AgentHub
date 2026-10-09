# 置顶消息上下文验收

日期：2026-10-08。对应 `agenthub-pinned-message-context` 1.1，已完成并通过验证，
本地未提交。没有新增依赖、数据库表、适配器或工具权限。

## 问题与实现

原实现持久化了 `Message.pinned_at` 并提供界面跳转，但规划和执行都只读取最近
8 条消息。旧置顶消息回归在修复前以 `KeyError: pinnedMessageContext` 失败。

新增共享选择器 `pinned_context.py`，只查询当前 Session，按置顶时间倒序，再按
SQLite 插入顺序倒序消除时间相同的不确定性。一条查询同时读取总数和最多 16 条
候选；每条上限 2,000 字符，整个引用载荷以 `ensure_ascii=True, indent=2`
序列化后不超过 12,000 字符。先过滤完整内容，再截断，报告包含/省略/截断/过滤数。
规划与执行使用同一字段，最近消息排除已选中的引用。

canonical 字段保留原始发送者、消息 ID、原始时间和置顶时间，信任级别为
`conversation_reference`，附带“不能覆盖当前请求和安全规则”的说明。置顶不会
创建 MemoryItem，也不会改写已保存的 TaskRun 上下文。另将既有 Planner 的
内联凭据赋值检测复用到共享过滤器，整段替换为既有的 `[redacted]`，堵住消息
经 ledger 目标重复出现的路径，并保留部署日志脱敏兼容性。

## 实际原生链路

- 会话：`c1b9feb0-10cc-48fe-9e23-0595b6d39c0d`。
- 被置顶消息：`2d597bae-6e56-4651-95a7-c2b4f6f1dfa0`，原始发送者为 agent。
- 任务：`6e056eb3-fd9c-440b-896f-35240a44cb75`。
- 原生 Claude 编码运行：`3f6b828b-39d3-4aa2-97dc-5bc5f4a020b3`。

通过普通消息 API 加入产品约定和 10 条较新记录，通过实际 Edge UI 置顶旧消息。
新用户请求仅要求使用置顶约定，没有写具体文案。真实 Claude CLI Planner 在
32.375 秒后返回通过校验的计划，并在 rationale 中明确取到 `Pinned Reference 20261008`。
真实 Claude 编码完成对应的一行文本修改，Diff、源码和实际 Vite DOM 均匹配。
未使用 ScriptedMock 代替本次原生规划或编码；CLI 平台不代表对路由后模型厂商的确认。

该最终版本会话的首次原生规划因输出任务数量不符合所选角色数量而被正确拒绝
（HTTP 400），零任务、零执行；明确只要一个 frontend_change 任务后再次请求成功。
拒绝记录单独保留，不能把本次演练表述为首次请求无失败。较早兼容修复前的另一
会话也完成过原生闭环，但以上以最终代码的新运行作为验收对象。

执行持久化上下文明确包含旧引用并保留 agent 归属。通过实际 UI 取消置顶后，重新
准备的规划和执行引用均为空；再次置顶和正常 API 重启后，新请求恢复引用。
原运行 metrics SHA-256 始终为
`f59983062d31730049e32274f747b8cb0322043e2e548e8936325961db509ab5`，计划哈希也不变。
重启后显式启动健康 Preview，按钮仍为目标文案，页面无 JavaScript 错误。

重启审计中，Session、Message、TaskRun 全表字节序列化哈希不变；Task 表中仅
既有任务 `d9e6e037-46d1-42ef-984e-a473b6bb9e2b` 的 `updated_at` 被启动协调刷新。
逐行比较确认其余字段不变，不能声称四张表全部哈希相同。重启前保存了 SQLite
备份，备份不纳入公共证据文件。

## 验证状态与边界

- 相关测试：56 passed，包括本项新增 10 个测试节点，取消置顶/快照、跨会话、
  相同时间排序、数量与 Unicode/转义字符预算、保护内容及三个适配器指令路径。
- 初次全量为 1 failed / 1,779 passed / 1 skipped，失败为部署日志期望的整段脱敏
  占位形式发生变化；修复后最终全量为 **1,780 passed / 1 POSIX-only skipped**，
  耗时 611.63 秒。34,665 条 `datetime.utcnow` 弃用告警来自既有模型时间函数。
- 最终 `pnpm check`、strict OpenSpec 校验已通过。
- 实际 UI、原生规划/编码、Diff、Vite 和正常重启验证已通过；没有证明任意任务
  都能正确使用任意长历史，超预算信息仍会明确省略。
- 最终代码、文档、规范和运行证据索引见
  [validation-index.json](evidence/pinned-message-context/validation-index.json)。
  全项目仍有富消息、重新生成、对话创建 Agent
  等独立缺口，见 [交付核对](local-project-delivery.md)。
