# 脚本登录表单样式验收

日期：2026-10-08；`agenthub-scripted-login-form-styling` 1.1 完成（本地未提交）。

上一项实际预览显示，ScriptedMock 生成了登录表单，但没有对应输入框 CSS。
本项为固定 demo 样式文件增加受控样式块，提供表单/标签间距、16px 输入字体、
灵活宽度、48px 最小高度、悬停边框和可见键盘焦点。输入补充 name/autocomplete，
保留隐式标签和原有按钮。这仍是前端演示，不包含认证服务。

其他 CSS 原始字节保留；存在单个完整管理块时只替换该块。歧义标记、样式别名
（symlink/hardlink）及危险路径在写入前拒绝。准备 App 与 CSS 后先写 CSS，普通
写入失败恢复已尝试文件；恢复失败明确报错，不声明成功。事件报告实际变更文件，
支持单独补齐样式，并保留无变化和不支持目标的拒绝。

新样式使已有登录任务在 Session 中留下两份已验证的未提交文件。旧 Orchestrator
文案规划只声明 App，导致后续工作被脏工作树门禁阻止。本项补入固定 CSS 上下文，
实际文案修改仍只写 App；注册目标、scope、只读、Queue/Target Lock 和完成门禁保留。

最终定向回归 **204 passed**（118.66 秒），包括 13 项新增的旧样式/CRLF 保留、
实际文件报告、仅补样式、无变化、歧义标记、部分写入回滚、恢复失败与路径别名测试。
Windows 的三项别名测试均实际执行。相关真实 Git、执行引擎、规划、自动组和续接回归通过。

独立 SQLite、实际 Edge 和健康 Vite 已完成直接、确定性组、Orchestrator 三路验收。
界面发送任务、保留 Codex 失败、显式使用 ScriptedMock 重试，并打开匹配任务的 Diff
和预览。实际 iframe 以及同一 Vite URL 的桌面 1440、窄屏 390/320px 共 20 份表单
测量验证了字体、间距、边框、字段宽度与无横向溢出；另检查自动填充属性、真实
键盘 Tab 焦点与悬停过渡。
同 Session 后续按钮文案只改变对应 App 文本，样式哈希与其他源码保持一致；组内有
两次独立只读脚本 QA。三个附加 OAuth 请求均诚实失败、无文件写入或 Diff。

刷新、亮暗历史视图和 API/Web 重启后，全部 Session/Message/TaskRun 响应哈希一致。
显式恢复的实际预览保留表单、样式和最终文案，没有页面异常。既有 API8006、原生
演示源码及历史未改动；隔离服务已正常停止，主 Web3000 已恢复并返回 200。

全量 API **1,736 passed / 1 POSIX-only skipped**（668.72 秒）。`pnpm check`、
strict OpenSpec、空白与证据哈希检查通过。证据见
[实际浏览器与样式测量](evidence/scripted-login-form-styling/acceptance.json)、
[运行、事件和制品来源](evidence/scripted-login-form-styling/execution-lineage.json) 和
[验证索引](evidence/scripted-login-form-styling/validation-index.json)。
累计 Session Diff 可能同时包含 App/CSS；文案运行的 adapter 事件只报告 App，不能
把累计 Diff 当成单次修改。初次定向回归的 fixture/样式上下文问题已修复；早期浏览器
脚本在 120ms 悬停过渡结束前断言的失败不计为最终验收，最终脚本等待实际颜色稳定。

本项没有修改产品 Web UI、demo 基线、其他适配器或数据库，也没有安装依赖、
提交、推送、部署或重复真实模型调用。脚本成果/评审、演示模拟失败和故意不可用 CLI
均明确保留来源。运行中的主 API 为保留原生演示继续加载旧模块，正常重启后端后，
新登录任务才会使用本项代码；历史成果不被自动改写。特殊字符文案处理与最终整体
工作流核查仍是后续独立任务，不能据本项通过声明整个项目全部验收完成。
