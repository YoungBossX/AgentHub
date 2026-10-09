# 本地启动入口验收

`agenthub-local-startup-entrypoint` 1.1，2026-10-08，本地未提交。

新增 `pnpm dev:local` 和只读 `pnpm doctor:local`。使用已安装的 Node/Python/Next，
不依赖 Bash；产品 API/Web 地址与 CORS 同步，可选 demo API 固定 5174。
退出/失败只清理本次启动的服务，保留数据库、会话工作树和已有监听进程。
README、本地使用说明和个人项目演示入口已同步。

## 修复与定向检查

真实 Windows 首轮新建 Session 未返回。线程栈确认在 Git worktree 命令的
stdout/stderr 读取中等待；关闭启动器输入后才完成。API 控制管道继承到子进程是
新包装方式引入的问题。现在复制私有控制描述符，并将进程 stdin/Windows
STD_INPUT_HANDLE 指向空设备，Git/CLI 子进程不继承控制输入。同一 HTTP 请求
修复后 **201 / 256ms**；最终真实浏览器新建 Session **201 / 383ms**。

Node 内置测试 **12 passed / 0 skipped**（4.88 秒），验证配置/端口、环境隔离、
错误解释器、监听保留、就绪身份/超时、子进程退出、取消、正常/重复/EOF 清理、
Windows 自有进程树清理，以及控制管道仍打开时子进程 stdin 已到 EOF。
Web **215 passed / 26 files**（6.47 秒）、`pnpm check`、Python AST、strict OpenSpec
和 Git 空白检查通过。未改 API 业务/前端代码，前项 12 个后端文件哈希保持一致；
未重新运行全量 API 测试，不将此前的 API 数量计作本次新结果。

## 真实运行

环境：Windows、Node 22.19.0、Python 3.12.7、Next 16.3.4、已安装的 Edge。
使用独立 SQLite 和 API 8007 / Web 3001 / demo API 5174，另一个既有 API 8006
始终保留。已通过：

- doctor 后没有数据库或监听服务；首次 API 自动初始化并返回空 Session 列表。
- 三个服务实际就绪后才打印最终地址；真实 Edge 访问选定后端并新建 Session/
  worktree。3001 Origin 返回 CORS 200，3002 Origin 被拒绝为 400。
- 手动组显式按钮文案任务，模拟 Codex 失败，再以 ScriptedMock 完成真实 +1/−1
  文件 Diff，实际 Vite 61825 显示 `Startup Verified`。本次没有模型调用；模拟失败
  与脚本写入不能算作真实 CLI 成功。
- 占用 8007 时启动失败，已有 API 继续健康。第二次启动使用另一产品端口但同一
  Next checkout，实际 Next 报已有开发实例；启动器返回非零、没有打印最终 Ready，
  回滚新 API，保留第一个 API/Web/demo API。
- 正常 `stop` 退出执行 API lifespan 清理，产品 API/Web/demo API/自有 Vite 端口
  全部可重新绑定。SQLite 和工作树保留。
- 重启后完整 Session/Message/TaskRun 记录哈希相同，Edge 恢复历史。旧 Preview
  已停止，界面显示预览异常属于正确诊断，需要显式重启，不把历史恢复描述成进程续跑。
- EOF 正常退出清理；受控强制结束当次自有 API，启动器返回非零并清理其 Web/
  demo API。此前 API 8006、已验收 Session/TaskRuns 和原生源文件哈希不变。
- 实际 PTY 发送 Ctrl+C，观察产品 API `Application shutdown complete`，随后
  8007/3001/5174 均释放，demo API PID 消失。PowerShell 中断返回 1；不宣称正常退出码 0。

## 边界与后续缺口

首轮管道继承失败、两次泛化登录页兜底失败，以及早期脚本只匹配旧 Next 错误
文本/选择隐藏历史文本的运行均不计作通过。最终通过记录来自 `final-pass`。

登录页失败已独立确认：直接/确定性组任务保留 `demo_frontend_request`，显式
ScriptedMock 重试返回 `SCRIPTED_MOCK_MUTATION_FAILED` / `Unsupported scripted
demo task target`。本项保留诚实拒绝，未更改 Agent 目标路由；后续应修正登录页
目标绑定，验证默认 Orchestrator/直接/组分配的失败与兜底路径。

统一入口不启用 Python reload；旧单服务开发命令仍保留。未验证 macOS/Linux
实际运行；强杀父进程或断电不能保证全树正常退出。没有安装依赖、真实模型重跑、
提交、推送或生产部署，整体项目仍需最终工作流验收。

证据：[索引](evidence/local-startup-entrypoint/validation-index.json)、
[真实验收](evidence/local-startup-entrypoint/acceptance.json)、
[Ctrl+C](evidence/local-startup-entrypoint/console-interrupt.json)、
[待修目标](evidence/local-startup-entrypoint/fallback-gap.json)、
[历史恢复](evidence/local-startup-entrypoint/restored-history.png)、
[实际 Vite](evidence/local-startup-entrypoint/scripted-preview.png)。
