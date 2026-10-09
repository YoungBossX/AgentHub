# 文件访问限制定位与写任务完成判定

日期：2026-10-07。对应 OpenSpec `agenthub-write-completion-validation` 1.1。

后续状态：同日独立任务已完成 Windows 原生沙箱选择修复，正式三项验收为 3/3；
见 [后续修复记录](windows-codex-sandbox-review.md)。本文及其 0/3 报告保留该任务当时的
实际结果，不用后续成功覆盖历史失败。

## 结论

已定位两个实际限制层：原始 Codex 命令的工具进程创建被策略拒绝；在诊断命令中显式选择 Windows `unelevated` 沙箱后，工具能够启动，但目标文件读取仍被 ACL 拒绝。当前没有证明真实 CLI 可以在这些目标中写文件。生产适配器没有采纳这个仍无法完成文件操作的配置，也没有改变宿主 ACL。

后端现在把 Provider 回合结束与写任务产出分开判断：没有本次新增修改、没有有效非空 Diff 或 Diff 收集失败，都会进入失败终态。既有只读任务路径保持可用。非空 Diff 仅证明存在输出，功能正确性仍由独立验收确认。

## 定位证据

使用当前真实 CLI `codex-cli 0.162.0-alpha.2`，在新建夹具中只要求读取 `probe.txt` 并追加一行，不要求访问网络或其他文件。子进程沿用适配器的环境白名单。

| 探针 | 实际观察 | 文件结果 |
|---|---|---|
| 原始适配器参数 | stderr 中 `codex_core::tools::router` 报 `CreateProcess ... rejected: blocked by policy`；没有 command_execution 事件 | 保持 `before` |
| 同一提示与参数，仅增加 `-c windows.sandbox="unelevated"` | 出现 command_execution；相对路径首先解析到 PowerShell runtime 目录；随后明确目标绝对路径的 ReadAllText 被拒绝 | 保持 `before` |
| X 盘新夹具，明确要求工具指定 workdir | 命令启动，绝对路径 ReadAllText 与 AppendAllText 都报 Access denied；PowerShell 非终止错误使 shell exit 仍为 0 | 保持 `before` |

前两个探针是同批对照，仅改变原生沙箱选择。第三个增加了显式 workdir 提示并关闭继承 stdin，用来排除仅由相对路径导致失败的解释，不能与第一个合并成单变量实验。夹具 ACL 观察显示 OWNER RIGHTS、SYSTEM、Administrators 和沙箱 capability SID 的允许项；当前用户能读取文件，而受限工具不能。没有进一步证明全部 ACL 拒绝规则的来源。

原始 JSONL/stderr、实际文件内容和 CLI 二进制哈希保存在 [诊断清单](evidence/external-task-benchmark/write-permission-manifest.json)，清单引用三份原始报告。没有把模型声称“只读”当作操作系统证据，也没有把 exit 0 或打印的“追加成功”当作文件成功。

[官方 Windows 沙箱文档](https://learn.chatgpt.com/docs/windows/windows-sandbox)说明原生模式与 ACL 边界，并说明 `elevated` 的设置涉及专用用户、权限与本机策略。本轮仅诊断已经可调用的 `unelevated` 模式；自动重建宿主沙箱、调整 Windows 用户/策略及目录 ACL 不属于本任务的运行时修复。服务应保留明确失败，后续宿主配置修复仍需再次验证真实读写。

## 完成判定

1. Codex 的 turn.completed 先暂存，等待进程结束。只有 exit 0 且没有终止错误才提交 Provider 完成事件；保留有界 stderr。exit 非零优先失败，避免回合事件掩盖进程错误。stdin 固定为 DEVNULL，防止继承终端输入。
2. 引擎先通过既有执行访问绑定、scope baseline、目标锁及代次校验。写任务无新增 changed_paths 返回 `TASK_RUN_NO_CHANGES`，不能借用执行前已有的脏 Diff。
3. 收集实际 Diff。收集异常返回 `TASK_RUN_OUTPUT_UNVERIFIABLE`；patch 为空或 Diff 文件与本次修改没有交集返回 `TASK_RUN_EMPTY_DIFF`。
4. 持久化 `completionValidation` 与 `task.completion_validation` 事件，记录新增路径数量、Diff ID、失败码和 `functionalAcceptance=not_evaluated`；不暴露内部 scope 指纹。
5. 只有输出通过后才生成成功路径的 Review 和 completed 终态，并推进后续集成、预览和部署。失败任务仍释放其自身队列/锁，保留失败证据。只读和历史 completed 的恢复路径不强制要求新补丁。

这些提交仍在既有 exact-generation finalizer fence 内。新增竞态回归验证：在完成证据提交前替换 adapter generation 后，旧执行不能写入 completionValidation 或失败终态。

## 真实基准与验证

最终 [真实三项报告](evidence/external-task-benchmark/write-completion-final.json) SHA-256 为 `08169cdcc2467d6fe1f8b6588bb2e23242ccca3e71a800cd031d4621abc18f6a`，源码和 suite 哈希已与当前文件核对。三项均有真实 Provider turn、有效规则 receipt 和通过的 scope，但新增修改为 0，最终全部 `failed / TASK_RUN_NO_CHANGES`，没有 Diff、Review、预览或部署，功能测试仍为 0/10，基准仍为 **0/3**。

| 任务 | TaskRun | 当前终态 | 完成判定 |
|---|---|---|---|
| 标题规范化 | `4ebf64f6-367c-475a-af5f-fccb42d14504` | failed | TASK_RUN_NO_CHANGES |
| 折扣计算 | `da97be7b-1f07-43d0-8e96-b0f7db2ca155` | failed | TASK_RUN_NO_CHANGES |
| 图书搜索 | `a0f0b0d2-eb33-445c-b739-dd8fbf80b73f` | failed | TASK_RUN_NO_CHANGES |

既往 [0/3 报告](evidence/external-task-benchmark/suite-final.json)保持原字节，旧 completed 状态不被追溯改写。本轮小任务和关闭 stdin 前的三项尝试分别保存为 `write-completion-probe.json` 与 `write-completion-before-stdin-binding.json`；它们不是最终当前源码的验收分母。准备请求 receipt、scope、Provider 回合、文件输出和独立功能测试分别报告，不以测试替身取代真实执行。

最终 API 全量 **1,352 passed / 1 POSIX-only skipped**（763.03 秒），覆盖 ScriptedMock、ClaudeCode、scope、DAG、记忆、锁、只读及新门禁回归。Codex 退出时序测试在全量收集后加强，最终版本又独立运行 **21 passed**；代次替换后的完成证据拒绝用例独立 **1 passed**，也包含在全量中。既有 `datetime.utcnow()` 弃用警告保留，不属于本任务。

Web 全量 **128 passed**，Demo API **5 passed**，`pnpm check`、严格 OpenSpec、空白、UTF-8、证据哈希与本地链接检查通过。工程测试中的受控写入是测试替身；真实模型结果仍为上面的 0/3。验证摘要见 [机器验证记录](evidence/external-task-benchmark/write-completion-validation.json)。任务在这些验证结束后标记完成。

本轮开发工作区未提交或推送。
