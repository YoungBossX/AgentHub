# Fresh local runtime acceptance

日期：2026-10-07。OpenSpec：`agenthub-local-runtime-acceptance` 1.1。

## 本次修复

显式 Codex 失败后点击“使用兜底重试”，文件结果生成后的同步 scope 检查会占用
API 的 asyncio 事件循环。两次浏览器请求达到 30 秒超时，随后数据库中运行最终
完成；不能将此现象误判为模型执行失败或伪造即时完成。

现在 scope baseline、完成围栏中的同步收集/检查，以及既有同步完成副作用在后台
线程执行。调用方逐步 await，独占该 Run 的 SQLModel Session；重复取消也会先
等待线程结束再传递取消，避免线程仍在使用会话时调用方 rollback/close。
保留完整 snapshot、锁、租约、执行代次、CAS 和提交围栏，没有缓存或跳过作用域检查。

另外，规划详情现在从实际分配的 Agent 补齐缺失角色，任务分解兼容生成图中的
`assignedAgentRole`。健康探针测试显式控制 `CODEX_CLI_PATH`，覆盖命令名和绝对
启动路径的脱敏，消除本机 launcher 配置对测试预期的影响。

## 真实浏览器与制品

使用现有 bundled Playwright 驱动 Edge，无依赖安装。控制面基于开发 checkout，
独立 SQLite 位于系统临时目录，API 8006 / Web 3000，Session 使用实际 Git 工作树。
未向既有用户数据库发起写请求，也未对原 8000 进程执行停止/重启；不保证原服务
当前仍在监听。开发 API 维护重启只针对本轮确认所属的 8006 进程。

| 路径 | 实测结果 | 证据 |
| --- | --- | --- |
| 新会话登录页 → 普通第二条按钮修改 | 两次实际 Codex completed；非空 Diff、脚本 Review，第二次独立健康 Preview 渲染邮箱/密码和 Enter workspace | [真实工作流](evidence/local-runtime/real-codex-workflow.json) |
| Preview 刷新、页面刷新和界面偏好 | 聊天历史、暗色选择和栏宽恢复；390px 无页面整体横向溢出 | 同上及目录内截图 |
| 明确模拟 Codex 失败 → 用户选择兜底重试 | 保留 `CODEX_DEMO_FORCED_FAILURE` 原始运行，新的 scripted_mock Run 修改文件并完成；健康 Preview 实际显示表单 | [兜底工作流](evidence/local-runtime/fallback-workflow.json) |
| 结果收集期间的读取 | 修复后的完整兜底验收记录 41 次任务 GET，最慢 483ms，均未超过 5 秒请求预算 | 同上 `readLatenciesMs`；仅本机该次记录，不是 SLA/通用性能指标 |
| Diff 和展开 Preview 面板 | 实际补丁含邮箱输入，iframe 显示表单；角色详情与实际分配一致，分解角色完整 | [结果检查](evidence/local-runtime/result-inspection.json)、[Diff](evidence/local-runtime/diff-inspector.png)、[Preview](evidence/local-runtime/preview-inspector.png) |
| 多 Session 与交付卡 | 浏览器新建多个 Session，切回原会话保留历史；按钮创建后端 ready/mock 部署记录 | 兜底和结果检查 JSON；未访问模拟发布地址、未上线部署 |
| 阻塞修复后的真实 Codex | 普通第三条聊天将按钮改为 Enter project，实际 Codex completed；对应健康 Preview 保留表单 | [修复后真实运行](evidence/local-runtime/real-after-repair.json)、[截图](evidence/local-runtime/real-after-repair.png)；70 次 GET 最慢 320ms |

初次两次 Codex 浏览器验收在本轮阻塞修复前完成；不能仅凭它们声明新异步边界
已经使用真实 Provider 验证。随后第三次真实 Codex 已单独验证修改后的边界。
开发 API 重启后旧 Preview 状态可能变化，JSON 中的
healthy 记录表示相应验收时的事实，不是永久健康承诺。

## 回归结果与边界

- 修改前完整 API：1,438 passed、1 skipped、1 failed；唯一失败是健康探针测试
  对本机 Codex 路径的隐含假设。当前未宣称修改后重新跑完整 API 全量。
- 修改后运行/故障回归：345 passed，含 TaskRun 全文件、dispatcher、failure recovery
  和新 responsiveness/cancellation 测试；此前独立 59 项围栏复验不重复计入。
- 修改后下游回归：182 passed，覆盖 Planning、Provider Gateway、PMO、DAG integration、
  cross-provider、Preview、parallel rehearsal 和 v2 记忆快照。与前组共 527 项。
- 本轮 Web 全量基线：159 passed / 18 files；没有修改 Web 源码。
- `pnpm check`、strict OpenSpec 和 `git diff --check` 通过。

Manager 仍使用禁用真实 Planner 后的确定性/动态 fallback，Review 为明确标注的
脚本报告；没有真实 Claude、真实 QA 或在线部署证据。模拟 Codex 失败只能证明
该恢复入口，不能代替真实供应商异常验证。对比各 Session 的累计 Git Diff，不将
第二次 Diff 中保留的登录表单误称为第二次 Agent 重新修改了表单。

后续本地需求和实际缺口见 [交付核对](local-project-delivery.md)。当前检查没有证明
自定义 Agent 已可执行或 System Prompt 已生效，不将本项完成当作整体项目完成。
