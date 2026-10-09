# 登录页兜底目标绑定

日期：2026-10-08；`agenthub-login-fallback-target-binding` 1.1 完成（本地未提交）。

启动入口验收发现，直接 `@frontend` 和确定性多 @ 群组为登录页需求保存了
`demo_frontend_request`。ScriptedMock 按显式目标拒绝执行，导致原本支持的登录模板
也无法兜底。旧失败记录见 [启动时的失败证据](evidence/local-startup-entrypoint/fallback-gap.json)。

新任务工厂在注册的内置 frontend 目标上保存具体 `login_page` 或按钮/标题目标与
目标文案。共享解析器只在明确创建 demo 登录页/表单时匹配，并保留文案、输入、颜色、
状态和布局意图的优先级。Orchestrator 的最终创建判定也使用同一有界语法，替代两个
关键词；英文既有三步计划保留，中文创建请求也能进入该计划。允许旧记忆验收使用的
语言/检查/变更日志流程附注，原文继续传递，不增加文件权限或声称这些步骤已执行。

外部目标选择、原生 Planner 的校验/语义替换、群组独立评审/依赖、Agent 身份、
scope、Queue/Target Lock 和适配器检查保持原有边界。没有在重试时修补历史 plan
或运行快照。OAuth/JWT/服务端认证等额外要求不会被脚本当成简单登录页模板。

最终定向回归 **192 passed**（115.72 秒），覆盖三路持久目标、中文、意图优先级、
外部目标、真实 Git/执行引擎的模拟失败→显式兜底、登录表单与按钮后续变更、
自动组独立脚本评审、不支持目标无写入及旧 P18b 记忆工作流兼容。

独立 SQLite、实际 Edge 与健康 Vite 已完成三路验证：从界面发送新任务，保留
Codex 失败，再点击“使用兜底重试”和绑定该任务的“启动预览”；登录表单、Diff、
预览来源与源码一致。同 Session 按钮修改只改变对应文案，CSS 与其他 App 内容
保持一致。自动组另有两次独立只读脚本 QA，完成后正常继续。

三路 OAuth 附加需求都保留泛化目标，兜底失败且无文件变更/Diff。刷新、亮暗/窄屏、
API/Web 重启后全部 Session/Message/TaskRun 响应哈希一致，显式恢复的实际网页
仍展示正确表单和按钮。失败运行冻结字段保留；响应中的当前 Target Lock 诊断会
随下一次运行改变，不能把动态诊断当成历史快照。既有 API8006、原生源码和已验收
历史未被本轮隔离场景修改；主 Web3000 已恢复。

最终 API **1,723 passed / 1 POSIX-only skipped**（658.24 秒）；`pnpm check`、
strict OpenSpec、空白检查与冻结哈希通过。证据见
[实际浏览器验收](evidence/login-fallback-target-binding/acceptance.json)、
[运行与制品来源](evidence/login-fallback-target-binding/execution-lineage.json)、
[历史边界](evidence/login-fallback-target-binding/historical-boundary.json) 和
[验证索引](evidence/login-fallback-target-binding/validation-index.json)。
初次全量回归的 P18b 兼容失败已修复；
早期验收脚本的 CRLF 比对、动态诊断及旧任务按钮选择问题不计为最终通过证据。

本项没有新适配器、UI、数据库迁移或依赖安装。脚本成果和脚本评审不是模型成果；
故意不可用 CLI / 演示模拟失败均需在实际验收中保留来源。
未安装依赖、提交、推送或部署，也未重复真实模型调用。既有主 API8006 为保留
原生演示状态继续运行；使用更新后的规划需正常重启后端。Web3000 已恢复连接该 API。

实际预览表单目前使用浏览器默认输入框样式，视觉完善留作下一项；本项验证的是
规划、失败恢复、真实文件与制品来源，没有把功能链路验收等同于模板视觉质量完成。
