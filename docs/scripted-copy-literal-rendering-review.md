# 脚本文案字面量渲染验收

日期：2026-10-08；`agenthub-scripted-copy-literal-rendering` 1.1 完成（本地未提交）。

实际隔离 SQLite、ScriptedMock TaskRun、Edge 和健康 Vite 复现了两个问题：按钮文案
`{agenthubCopyProbe}` 导致 ReferenceError 和空白；标题文案中的 `<strong>` 成为
子元素，`&amp;` 变为 `&`。当时的 scope/Diff 完成检查通过，但记录明确保留
`functionalAcceptance=not_evaluated`，并没有声称网页功能验收通过。

本项只修复固定按钮/标题模板。敏感字符使用 JSON 字符串字面量作为 JSX 文本，
角括号转义后不会截断下一次锚点匹配；callable 正则替换保留反斜杠，普通单行文案
继续使用原有源码格式。现有 targetText 规范化、支持范围、注册目标、CSS、只读、
Queue/Target Lock、执行所有权、非空 Diff、no-op 和失败边界不变。

定向回归 **220 passed**（139.47 秒），包括 16 项新增的字面量、源范围、控制字符、
反斜杠、重复 no-op 和敏感文案后继续普通修改测试。另有 **16 份实际适配器输出**
通过严格 TypeScript、esbuild 和实际 Edge React DOM：中文、Emoji、引号、标签、
实体拼写、花括号、反斜杠、内部 LF/CR/Tab 和 Unicode 分隔符均保持原值，无额外
子元素或页面错误。这些结构化 fixture 使用测试 ownership guard，不替代生产路由/
执行租约证据；三种实际入口另行验收。

直接、确定性组和 Orchestrator 三路实际界面发送任务、显式脚本兜底、Diff 和健康
Vite 检查通过：共 13 个实际 DOM/续接/重启检查，标签/实体/花括号保持文字，随后
改回普通文案仍正常；样式哈希和表单一致。组内另有 5 次独立只读脚本 QA。
API/Web 重启后 Session/Message/TaskRun 全响应哈希一致，显式恢复的预览保持最终
内容。既有 API8006、原生源码与历史不变，隔离服务已停止，主 Web3000 已恢复并返回 200。

全量 API **1,752 passed / 1 POSIX-only skipped**（741.64 秒）。静态、strict OpenSpec、
空白、冻结哈希与私有值排除通过。证据见
[修复前复现](evidence/scripted-copy-literal-rendering/before-acceptance.json)、
[实际三路验收](evidence/scripted-copy-literal-rendering/acceptance.json)、
[编译及 DOM fixture](evidence/scripted-copy-literal-rendering/fixture-results.json)、
[运行/事件/制品来源](evidence/scripted-copy-literal-rendering/execution-lineage.json) 和
[验证索引](evidence/scripted-copy-literal-rendering/validation-index.json)。早期预演的
60 秒观察限额和用户文本截图文件名问题不计为最终验收；最终脚本等待实际终态，
截图仅使用服务生成的 ID，不将用户文案当作路径。

旧错误运行、App Diff 与浏览器结果按产生时点保留，旧适配器源码通过执行前冻结
SHA-256 校验复原，历史记录不迁移。当前完成契约仍只检查范围和输出，功能验收
来自独立编译/浏览器证据；累计 Session Diff 也不能被解释为单次修改范围。

本项不修改其他适配器、规划、产品 UI、demo 基线或数据库，不安装依赖、不重复
真实模型调用，也不提交、推送或部署。模拟 Codex 失败/故意不可用 CLI 和脚本
成果均需保留来源。现有主 API 仍加载旧模块，正常重启后端后新任务才使用修复。
最终核心工作流和实际执行耗时仍需独立核查。
