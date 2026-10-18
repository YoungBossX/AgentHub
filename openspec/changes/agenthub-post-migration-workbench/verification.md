# 迁移后工作台验收

日期：2026-10-18。代码基线 main `2072231`，本次仅本地修改发送框和交付记录。
没有安装依赖、修改后端/权限、重置数据、提交或推送。

后续用户要求的名称调整 1.2 已完成：旧默认名称在界面显示为 AgentHub，保留数据库
查找键和自定义名；29 项组件回归及根检查通过，真实页面标题/页脚核对通过。
本记录下面的逗号限制已由 intent-boundaries 1.3 修复，见
[后续修复验收](../agenthub-intent-boundaries/comma-verification.md)；原失败事实仍保留。

## 历史预览恢复

两条用户指定的旧预览属于同一完成运行
`085af646-f568-4506-9437-de2f3d49dc53`。按既有设计保留失效历史，显式启动新的
受管预览，不将旧 PID 重新声明为当前进程。

| 历史预览 | 新预览 | 本次地址 | 验证 |
|---|---|---|---|
| b4b7fc21-078b-43e7-bd5e-63cf51b4c063 | e4919663-61e0-4057-90e0-0eae906ecf78 | http://127.0.0.1:33416 | healthy、HTTP 200、浏览器标题 Skills MCP end to end |
| f79428f1-0a67-4833-9bdc-b990df97867b | fa17cf44-bf94-4bdf-bbd6-14ebb6b35b0a | http://127.0.0.1:30475 | healthy、HTTP 200、浏览器标题 Skills MCP end to end |

本次端口仅用于本次启动，不能当作永久地址。历史失败/停止记录保持其原有事实。

## 新运行、Diff 和预览

- Session：`e71db600-4d22-4d83-a2fa-8fd5054e462c`。
- 用户指令：`@frontend In the demo app change the title to "AgentHub Workspace"`。
- Task：`28e0e881-82af-4d41-a7fc-d54b95b4cd9a`。
- 真实 Codex TaskRun：`146421c1-06b2-446d-81b4-0db533040b60`，completed，未使用回退。
- Diff：`fddd1294-1430-4250-99a4-e8880f64be53`，只修改 `apps/demo/src/App.tsx`，+1/−1。
- 新预览：`3b023f01-dd04-4283-92d0-818c1518be99`，本次地址 http://127.0.0.1:57523，
  healthy、HTTP 200，真实浏览器 h1 为 `AgentHub Workspace`。
- 当前源码指纹 `aff49d7a0552dab15d32829fa12266cae0e15330be2250855a2df754cfa8a6ad`。
  绑定该版本的 TypeScript check、Vite build、3 项构建产物测试通过；固定标题契约的
  desktop.text/runtime 和 narrow.text/runtime 四项通过。
- 规则评审 passed，模型评审 not_run，整体 QA incomplete；标题契约不等于完整业务验收。

首次指令 `In the demo app, change ...` 的引导语逗号被保守边界误判为多动作；
第二次 `change the demo title ...` 不符合当前支持的有界语法。两次未创建任务，原消息和
澄清记录均保留。此项限制已记录，本次不扩展意图机制。

## 发送框

输入区独占上行；工具栏中附件靠左、发送靠右，统一高度与留白，去掉重复背景和
装饰气泡。保留原有附件、上下文、快捷键、输入 ref、提交和禁用规则。

- 桌面以及 390px 页面，在亮/暗主题下均检查。
- 390px 页面 scrollWidth=clientWidth=390，发送框宽 350，无横向溢出。
- 附件和发送按钮均 40px 高，共享中心线；两侧留白均 13px（含边框）。
- 非空草稿启用发送，Shift+Enter 增加换行；验证后清空测试草稿。
- 恢复原亮色和默认视口；未发送额外测试消息或创建额外 TaskRun。
- `pnpm check:web` 和 26 项 MessageComposer/WorkspaceShell 组件回归通过。
- strict OpenSpec 与 `git diff --check` 通过；本次没有重跑完整 API/Web 或新远程 CI。

详细运行回执、恢复映射、版本绑定 QA 和截图保存在用户本机
`E:\AgentHubBackups\alembic-20261018-140722-aa8a4531`：
`preview-recovery.json`、`post-migration-flow.json`、`flow-reviews.json`、
`composer-layout-verification.json` 和 `composer-*.png` / `workbench-composer-light.png`。
迁移前原始数据库备份与迁移备份保持保留。

后续提交前完整验证：根检查、API 2551 passed / 1 skipped、Web 329（串行）、本地工具
24、demo-api 5 均通过。用户已授权提交、推送并核验对应提交的 CI；上述局部测试及
未提交描述保留为原验收阶段事实。新日志见
`E:\AgentHubBackups\delivery-workbench-20261018-1792322555974`。
