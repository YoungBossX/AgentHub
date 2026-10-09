# 原生评审成果验收

日期：2026-10-08。对应 `agenthub-native-review-artifacts` 1.1。
本项完成（本地未提交）；任务在真实运行和最终门禁通过后勾选。

## 问题与修复

原生 Claude Read-only 任务此前把模型回复保存在事件流中，完成后却统一创建
`scripted_mock` 评审成果。调用成功、模型判断和脚本检查缺少直接关联。

- 新原生只读运行在启动边界冻结注册目标的文件指纹，追加服务端 JSON 契约。
  文件读取放在可取消后等待收尾的工作线程中，保留请求 CAS、Profile/工具策略、
  执行租约和精确代次完成围栏。单独 @ 自定义原生评审角色也保存所选目标。
- CLI 的最终 `result.result` 是评审输出来源；实际完整 Read 的调用/结果对应关系、
  内容摘要、文件列表、发现行号和状态/风险需匹配。未读取、部分读取、错误读取、
  无效或错绑 JSON、非零退出、越界文件和写工具请求不会产生原生评审成功。
- 完成前复查目标及文件版本，收集同一运行的 Diff。原生 Review、ArtifactVersion、
  ready 事件与 terminal 状态一起提交；失败回滚，不能以脚本报告替换原生成功。
  显式再次读取评审与完成后的重复收集保留原报告，不重新解释当前源文件。
- 模型的 `passed/warning/failed` 是评审判断，TaskRun 的 completed 是执行完成。
  固定记录 `validation=not_run`；前端显示实际摘要、发现、建议、行号、文件/输出
  摘要及“只读静态评审、未运行测试”。保留旧历史成果与编码任务的脚本评审标识。
  评审面板标题栏及发现项使用现有暗色主题颜色。

## 真实运行证据

使用本轮专用 SQLite、API 8006、Web 3000 及已有原生 Claude CLI/用户 SDK 路由。
没有安装依赖或放宽 CLI 的 Read、restricted、safe-mode、strict MCP 和无 shell 策略。
最终运行标识与原始成果见 [运行证据](evidence/native-review-artifacts/runtime.json)。

新会话真实原生评审运行 `de74f9e9-610d-473b-b6f2-dae28212ad2a` 完成，CLI exit 0。
模型实际完整读取 `apps/demo/src/App.tsx`，发现按钮文案为 `Continue`，与该验收
Profile 的预期 `Claude native workspace` 不同，返回 warning/low、两条发现和建议。
成果摘要与最终原生评审内容一致，Read 内容摘要及原始文件 SHA-256 匹配；三个
demo 源文件评审前后哈希完全相等。该结果不表示已完成按钮修改或功能测试。

真实浏览器核对执行卡片、展开评审、摘要/发现/版本标识和暗色模式，刷新后仍只有
一次运行与一个相同原生成果。持久 SSE 重放保留原生 receipt 与 assessment，
`Last-Event-ID` 到达 high-water 后不重放旧帧。截图见证据目录。
专用 API 重启后，相同原生报告、文件 receipt 与一次 completed 运行仍可读取，
没有新 CLI 执行。

## 回归与诚实边界

最终全量 API **1,603 passed / 1 POSIX-only skipped**（906.09 秒），Web **168 passed /
20 files**；`pnpm check`、strict OpenSpec、空白及源码/证据哈希校验通过。
最终定向 API **103 passed**；涵盖字段/绑定/覆盖校验、读取证据、编辑/新增/删除/
目标变化、硬链接/重解析/预算拒绝、保护路径排除、结构化结果、越界工具、终止
失败回滚、刷新/重复收集及后台工厂。最终结果、日志和文件摘要见
[验证索引](evidence/native-review-artifacts/validation-index.json)。

初轮真实单 @ 任务缺失 targetId，被新校验拒绝；这推动了目标绑定修复。随后的
旧会话追加任务被已有失败依赖拦截，最终验收改为新会话，未篡改历史依赖状态。
初轮浏览器用了旧开发资源，重启本轮 Web 后核对；展开成果隐藏顶部主题按钮，
验收脚本恢复布局后切换主题，再次展开。完整回归曾发现旧后台工厂测试使用
不存在的工作树和空成功事件，已改为真实临时文件及结构化 Read 事件，保持正向
工厂/网关验证。此前完整测试为 1 failed / 1,602 passed / 1 skipped，修正该旧测试
后重新执行上面的最终全量。上述失败和中途停止的测试均不作为通过证据。

文件预算：至多 128 个作用域文件、单文件 512 KiB、总计 4 MiB、4096 个遍历条目；
超预算或不安全路径明确失败。仅声称实际读取并列出的 UTF-8 文件覆盖；冻结范围
可大于实际评审覆盖。Diff 是 Session 当前累计差异，不声称是评审任务产生的新
写入。版本比对是本地观察与证据校验，不是 OS 沙箱或跨进程文件事务。

本项只接入现有原生 Claude Read-only 策略。保留 Codex、Claude 编码、Mock 兜底
及旧脚本成果；不把 CLI 平台当成底层模型厂商证明。无新 Preview/部署验收、依赖
安装、开发仓库提交或推送。多 Agent 完成汇总与执行协调留待下一项，本轮未实施。
