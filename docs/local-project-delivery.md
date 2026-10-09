# AgentHub 本地个人项目交付核对

本轮继续以本地单用户 Coding Workspace 为范围。原始设计 PDF 是需求参考，
其中的竞赛提交、上线部署和多端客户端不作为当前本地运行验收条件。
已勾选的 OpenSpec 不能替代实际功能检查。

需求来源：用户提供的《AgentHub- 多Agent协作平台设计.pdf》，3 页，SHA-256
`95d472e103ed53e50b6264f4a07c895dbbc01f5a669027c81194ae83c53b289c`。
下面的实现状态基于截至 2026-10-09 的本地源码核查及运行证据。

本轮终验已修复 320px 输入区、选中代码引用、Planner 丢失引用、重复点击当前
会话清空成果及公共时钟弃用问题；最新原生续接、实际 iframe、重启和历史保留
已通过，最终 API 1949 passed / 1 skipped、Web 267、本地工具 17、demo-api 5；
静态检查与生产构建通过。本地核心版本验收完成，完整批次与失败样本见
[本地核心工作流终验](local-final-workflow-review.md)。

| 需求 | 当前确认状态 | 边界与说明 |
| --- | --- | --- |
| 新建、切换、搜索会话，保留历史 | 已有会话置顶/归档/恢复及关键消息置顶/原文跳转；真实 CLI 运行期间整理、亮暗/窄屏/刷新/重启、旧库与边界测试通过；API 1,668 passed / 1 skipped、Web 184 passed | 保留归档不取消/删除、不改变运行快照的边界；见 [记录](session-organization-review.md) |
| IM 对话、角色联系人和 @ 路由 | 多 @、原生 Planner 整组内容、默认自动组/独立评审和原生结果汇总已通过；真实 Planner → Claude 编码 → 原生评审 → 原生汇总、亮暗/刷新/重启/SSE 通过；汇总阶段全量 API 1,651 passed / 1 skipped、Web 174 passed | 历史手动计划继续保留；会话整理新增证据见上行。见 [汇总记录](group-result-summary-review.md) |
| Manager 分解、路由、持续修改 | 登录与普通按钮后续修改真实 Codex 闭环通过；自定义 Planner 整组规划、自动协调/指定评审续接、最终汇总和提示词标记已有实际证据，保留未配置时的确定性执行记录 | 无效输出诚实拒绝；继续保留复杂需求、取消与多 Session 的边界验证 |
| 核心执行、安全文件输出及完成判定 | Worktree、Queue、Target Lock、scope、非空 Diff、执行租约和完成围栏具备；同步检查已移出事件循环，最新项减少内部重复采集；同基线两次脚本任务核验阶段平均 13.09→6.71 秒，保护采集器哈希不变；API 1,770 passed / 1 POSIX-only skipped，见 [性能验收](scope-finalization-performance-review.md) | 性能数据仅限该固定样本；本轮核心工作流、配置保留与重启终验已通过，见终验记录 |
| 至少两个真实平台统一适配 | 保留 Codex、ClaudeCode 和 ScriptedMock；真实 Codex、Claude 编码与原生只读回复都有独立运行及匹配证据，Claude 启动/SDK 配置和退出围栏全量 API 1,564 passed / 1 skipped | 继续保留真实异常/恢复和来源验证；CLI 平台不证明用户路由的模型厂商 |
| 自定义 Agent 的 System Prompt 和工具集 | 既有角色及受限档案进入 TaskRun；名称/别名、提示词、原生工具策略、档案选择与联系人已通过浏览器/Codex/Planner；本轮真实 Claude 编码与 Read-only 回复、标记各一次和源文件哈希一致通过 | 继续保留工具策略/目标/身份围栏，模型回复与后端脚本 Review artifact 分开标注。旧安全草稿继续不可执行 |
| 原生评审成果 | 新 Claude Read-only 评审绑定实际文件版本和完整 Read，持久化实际判断/发现/建议；真实 CLI、浏览器/暗色/刷新/重启及 SSE 通过；API 1,603 passed / 1 skipped、Web 168 passed | 静态评审未运行测试；不把评审执行完成或 passed 判断作为功能验收。见 [记录](native-review-artifacts-review.md) |
| 过程可视化及结果来源 | DAG、SSE 事件、运行记录、Diff/Review/Preview 来源已经展示；本轮修复规划详情丢失角色 | 保留真实角色、服务步骤和脚本报告的区别 |
| 代码差异、版本、网页/文档查看 | 已有真实 Diff、版本/文档工作台和安全 iframe；预览归属/退出、一键重启、高端口、异步选中和当前进程退出清理实际通过；API 1,676 passed / 1 skipped、Web 212 passed；[记录](preview-restart-recovery-review.md)。新项已修复主题切换瞬态，Web 215 passed，实际逐帧颜色/跨标签/悬停通过 | 实际手工修改、原生续接与版本来源已分别核对，不把累计 Session Diff 误称为单次 patch；主题证据见 [记录](theme-transition-consistency-review.md) |
| 失败、兜底和连续上下文 | 原真实后续修改证据保留；三路登录目标、样式与文案续接已修复，最新项使花括号/标签/实体按文本显示。16 份严格编译/实际 DOM、三路 13 个渲染/续接/重启检查、独立 QA 和样式/历史一致通过；API 1,752 passed / 1 skipped，见 [字面量记录](scripted-copy-literal-rendering-review.md) / [样式记录](scripted-login-form-styling-review.md) / [目标记录](login-fallback-target-binding-review.md) | 旧 plan/错误输出不自动迁移；继续核对实际核验耗时、真实异常与中断，不将模拟失败或故意不可用 CLI 等同真实供应商故障 |
| 记忆与配置一致性 | 有作用域检索、v2 内容冻结快照、规则预算、receipt 和 UI 显式刷新 | 本轮核对原生请求中的档案/快照绑定、引用片段和重启保留；置顶与自定义提示词的实际使用另有独立记录，不仅依赖配置行 |
| 手动置顶关键消息作为长期上下文 | 已补齐同会话有界规划/执行引用；实际 Planner 和 Claude 编码从旧置顶消息取得新请求未写出的文案，Diff/Vite/取消置顶/历史快照与重启通过；API 1,780 passed / 1 POSIX-only skipped | 保留 16 条/每条 2,000 字符/序列化 12,000 字符预算与会话参考信任边界；[记录](pinned-message-context-review.md) |
| 富消息：代码块、图片和文件附件 | Markdown/代码复制已验收；新增不可变附件、文件提取/下载、图像输入及有界引用。真实 Codex 使用文件+图片、Claude 规划/编码使用文本，Diff/Vite/UI/持久化一致；API 1,814 passed / 1 skipped、Web 242、本地 17；[附件验收](message-attachments-review.md) | 保留文件/预算/无 OCR 边界；当前 Claude 配置的模型拒绝图片，已实测明确失败。HTTP 图像载荷单测不等同远端推理 |
| 消息回复、引用、重新生成和复制代码 | 引用、整条/代码块复制及回复/计划/汇总重新生成已验收；同一请求/附件真实生成标题序号 1→2，汇总不重跑代码，响应丢失/切换/重复/重启及历史保留通过；API 1,845 passed / 1 skipped、Web 249；[记录](message-regeneration-review.md) | 保留当前状态重新执行、用户确认、持久操作 ID 和单 API 边界；不代替失败任务重试或文件撤销 |
| 通过对话创建 Agent | 已有专用创建对话、真实无工具生成/澄清、多轮调整、手工编辑/标签页恢复及显式保存；新 Agent 从自己的提示词取得实际标题，Diff/Vite/UI/重启一致；API 1,872 passed / 2 skipped、Web 256；[记录](conversational-agent-creation-review.md) | 保留生成不执行、确认保存/启用及受限工具策略；需要配置可用 Planner，未保存草稿仅在同一浏览器标签页恢复 |
| 直接代码编辑和一键应用 Diff | 已有完整当前源码编辑、受限补丁准备/应用、版本冲突、用户来源和重启围栏；实际 UI/Vite/原生续接/历史一致性通过；[记录](bounded-code-editing-review.md) | 限规范 Session 工作树及目标，支持有界 UTF-8 增删改；不支持任意主机文件/二进制/重命名/权限修改；应用成功仍需独立测试和评审 |
| 选中代码 → 对话式局部修改 | 完整源码的 Monaco/纯文本选区可明确引用；普通/群聊 Planner 和执行收到同一有界片段。真实 Claude 从引用取得正文未提供的新标题，文件/Diff/Vite 一致；[终验记录](local-final-workflow-review.md) | 每片段最多 2400 字符、每消息最多 8 项；引用标为编辑器草稿，不自动应用或发送。首次 Planner 丢引用导致错误标题的运行仍保留 |
| 时间显示与本地使用文档 | 会话/Preview/事件已有统一本地时区、原始值/UTC、严格解析与 SSR 一致性；实际三时区/刷新/窄屏通过，Web 209 passed；[记录](local-time-display-review.md)。健康预览恢复/主题、无 Bash 启动/只读诊断及使用说明已独立实测；启动器 12、Web 215 passed，见 [启动记录](local-startup-entrypoint-review.md) / [说明](local-usage.md) | 保留本地单用户、脚本/真实模型、正常/异常退出和未上线的实际边界 |
| 当前依赖安全状态 | 2026-10-09 生产审计 12→0，全树 19→1 high；braces 未发布修复版，已应用并验证本地深度补丁，原始告警保留。实际 Diff 改为本地 Monaco/worker 与 DOMPurify 3.4.16；本地 17、Web 237 passed、静态/构建/浏览器通过；[记录](local-dependency-security-review.md) | 后续跟随上游替换临时补丁；不将包审计归零等同所有漏洞已消失。额外生产模式浏览器启动被审批拦截，现有开发模式已验证 |
| Windows 连接关闭与正常退出 | 已定位历史 10054 跳过 socket/Server 清理并精确恢复；正式 API 入口故障注入对照、预览端口释放、SSE、当前工作台重启及历史行集一致通过；API 1,827 passed / 1 skipped、本地 17；[记录](windows-connection-cleanup-review.md) | 实机验证为 Windows Python 3.12.7；其他异常仍上报，保留现有退出超时和进程归属边界 |

## 继续交付顺序

1. 已完成真实浏览器闭环、阻塞修复与独立验收证据。
2. 已完成提示词生效、配置持久化、可执行受限 Profile、原生规划/编码/评审、自动协调与结果汇总。
3. 已完成会话置顶/归档/恢复、关键消息置顶/跳转及实际执行中整理验证。
4. 已完成时间展示、预览进程诊断/重启恢复、主题切换及个人项目启动入口/使用文档；独立 SQLite、Edge、真实 Vite、冲突回滚和退出/历史保留已验收。
5. 已完成三路登录页兜底目标绑定、原始/中文需求回归和脚本表单样式；实际桌面/窄屏、键盘焦点、文案续接与重启一致通过。
6. 已修复按钮/标题特殊字符的字面量渲染和后续定位，减少核验阶段的重复完整采集，补齐置顶消息上下文、Markdown/代码复制、依赖安全更新，以及文件/图片附件的实际模型链路。
7. 已定位附件验收中的 Windows 连接清理失败；正式 API 包装入口在同故障条件下也会等到超时，修复后正常释放连接和预览并退出。当前工作台已重启加载，历史消息/运行/Diff/附件哈希一致，完整回归和独立证据通过；普通 200 次 TCP RST 未自然复现，与故障注入证据分开记录。
8. 已完成消息重新生成及独立原生、浏览器、响应丢失与重启验收；保留首个 Planner 无效命令失败样本和拒绝门禁，未以重试成功掩盖失败。
9. 已完成对话创建 Agent：自然语言生成、手工调整、显式保存及新档案真实执行通过；恢复验收临时修改的 Planner 默认配置，保留首次设置校验拒绝记录。
10. 已完成受限编辑/应用 Diff、实际用户改动/Claude 续接和重启一致性；后续 Agent Diff 排除既有手工改动，修复续接上下文超过 Windows argv 上限。
11. 已完成本地核心终验：修复 320px 输入区、引用代码到规划/执行的缺口、当前会话重复选择以及公共时钟弃用；当前原生 Codex/Claude、只读评审/汇总、兜底/队列中断、引用续接和重启通过，最终回归与验收索引已记录。

各项通过独立 OpenSpec 任务推进。本次核心终验不将以下可选项视为已完成。
P2 上线部署矩阵、静态/容器发布和原生移动客户端按用户
当前指示留待后续上线决策；不扩展为多人平台或 MCP/Provider 市场。
PDF 标记为 P2 的 PPT 浏览和源码包导出也尚未实现，不计为已完成能力。
