# 原生 Planner 群聊规划验收

日期：2026-10-08。`agenthub-native-group-planner` 1.1 完成；本地未提交。

## 解决的问题

此前多 @ 使用确定性协调，自定义 Planner 与其他角色一起被指定时明确拒绝。
现在显式选择或运行配置选定的 Planner 会实际生成整组任务内容，服务端保留全部
执行角色、自定义档案及目标。原生输出的标题、文件计划、验收条件、验证要求和
理由进入任务和执行指令；没有用固定任务覆盖后再声称模型规划成功。

Task 工厂在整组校验前保持 detached，避免提供方调用期间提前 flush 部分任务。
整组任务与协调消息一次提交。每个角色/目标必须按顺序出现一次；权限、路径、
命令、风险、意图、制品及依赖校验失败，或提供方失败/返回非任务结果时，明确
报错且不创建部分任务。原始用户消息按既有 API 行为保留。调用后刷新并复核
Planner 身份/工具策略、参与者启用状态、能力和目标策略。

写任务继续串行，显式评审等待写任务并独立执行。保留 `explicit_group_v1` 执行
标识，所以编码自动产生的建议报告不能完成显式 QA；ScriptedMock QA 仍只读。
未配置/禁用原生 Planner 时，原有确定性群聊和 P0 兜底路径保留。未增加自动启动。

## 原生 CLI 与证据边界

Windows 优先识别 npm 安装的原生 `claude.exe`，不引入 cmd/shell JSON 解析，
按 UTF-8 读取输出。无工具规划使用 `--tools ""`、`--allowedTools ""`、
`--strict-mcp-config` 与 `--safe-mode`，保留 CLI 认证与模型配置，禁用环境中的
hooks/plugins 和额外指令发现。角色、目标、顺序已由服务端确定的有界群聊调用
使用 `--effort low`，仍采用和校验真实模型输出，不将降低推理预算称为固定规划。
CLI 必须支持这些参数；不支持时明确失败，不静默替换。

首次完整调用在 60 秒预算内超时；安全模式最小探针约 5.94 秒成功，完整群聊
在 low effort 的受控探针约 9.64 秒成功。随后实际浏览器消息的 Planner 调用
约 8.83 秒成功，提示词独有标记进入模型规划理由；这不证明超时完全由某个
hook/plugin 导致，也不代表所有需求都能在该耗时内完成。

已验证真实 Codex 文件修改及匹配 Diff，随后自己的只读脚本 QA 运行完成。
最终源码启动后的浏览器重新读取历史、展示提供方/验收条件及评审来源通过，
没有新建 TaskRun。旧浏览器脚本在最终 UI 精确文本定位处失败；此前文件字节
相等断言已经执行，通过更准确定位的独立只读浏览器检查补齐 UI 验收。
最终源码另开 Session 的新链路也已完成：Planner 13.703 秒；Codex Run
`874cb6e6-b1d2-4664-8649-5314cab8c28c` 和自己的只读脚本 QA Run
`5cfe11fe-b946-4cd7-842d-01223b1cd0ae` 均 completed。Session 为
`1bedf9bb-da50-4653-bad4-b3d96ae8d715`，两个任务、两次运行和依赖均已通过
只读 SQLite 验证；提示词 SHA-256 与实际保留的档案一致。

该 Session 的首次原生输出使用了不被允许的 planned-file 路径，返回 400 且
没有部分任务或协调回复。验收档案随后明确了 demo 路径的坐标系，再次真实调用
通过；不将此结果外推成默认提示词下所有需求都能一次成功。最终链路脚本的
文件相等断言和自己的 QA 均通过，之后因在执行视图查找隐藏的对话消息而超时；
独立只读浏览器检查在正确视图验证历史、Planner 来源和评审。只保留评审后的
文件 hash，未把没有保存的评审前 hash 伪造成独立留档。

运行/队列/规划来源和失败原子性见 [runtime.json](evidence/native-group-planner/runtime.json)，
浏览器截图见 [规划](evidence/native-group-planner/plan.png)、
[Planner 详情](evidence/native-group-planner/planner.png)、
[自己的评审](evidence/native-group-planner/review.png)。
[最终校验索引](evidence/native-group-planner/validation-index.json) 保留文件/源码哈希及全量日志摘要。

QA 是规则脚本报告，不是原生模型评审；QA Diff 是当前目标的累计 Git 快照，
不是 QA 新写的 patch。没有本项新 Preview/部署或真实 Claude 编码适配器验收。
原生规划通过用户已配置的 Claude CLI 传输；没有根据 CLI 名称推断其实际模型厂商。

## 验证

- 当前最终源码定向 API：165 passed，覆盖整组、Planner 提供方/契约、提示词、
  自定义档案及记忆指令；包含遗漏/额外/换角色、越界、非法命令/依赖、风险、
  返回非任务结果、晚禁用、Planner 身份改变、六任务双目标和 HTTP 持久化。
- 初轮全量 API：1,542 passed / 1 POSIX-only skipped，738.76 秒；该轮之后补充了
  提供方解析和身份变更围栏，不能当作当前最终源码全量结果。
- 最终源码全量：**1,544 passed / 1 POSIX-only skipped**，917.89 秒，进程退出 0；
  新增身份/解析围栏与已有隔离写、锁、租约、完成判定和兜底路径都在该轮覆盖。
  中间一轮因后续源码围栏改动主动终止，不计作通过。
- Web：167 passed / 20 files；demo-api：5 passed；未修改本项 Web 源码。
- 最终 `pnpm check`、strict OpenSpec、空白检查和归档哈希核对通过。

未安装依赖、提交、推送或发布。会话置顶/归档、关键消息置顶、完成后的聚合回复、
统一时间和完整本地交付说明仍是独立后续工作。
