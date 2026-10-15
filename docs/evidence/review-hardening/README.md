# 四项审查缺陷的修复证据

对应 `agenthub-review-defect-hardening` 1.1；修复基于 `dev` 的 `d20aea7`，随本次修复提交保存；2026-10-15 提交前核对。本页记录本地验收，远程 CI 以对应提交的 GitHub Actions 为准。

| 验收要求 | 直接证据 |
|---|---|
| 不受信任页面不能控制任务 | `test_local_request_guard.py` 覆盖不同方法/Origin/Host/缺头；实际 queued TaskRun 中断被拒绝、状态和原生中断调用均未改变。开发 API 重启后的三类拒绝状态见 `runtime-acceptance.json` |
| 预览不能返回不相关/保护文件 | `test_preview_serving_scope.py` 启动真实安装的 Vite，逐项检查后端源码、`.env`、公共目录保护文件、额外拒绝路径、软/硬链接、JS raw import 和 CSS import；正常依赖/样式通过。实际已有 Session 的新健康预览读取后端返回 403 |
| 并发保存不会突破 Skill 默认预算 | `test_skills.py::test_concurrent_default_saves_cannot_overfill_aggregate` 使用独立文件 SQLite 和两个连接/线程，覆盖新增/更新与数量/字节四组合；一成功一拒绝，冻结绑定有效，拒绝后再次保存可用 |
| 成功事件不会生成故障与恢复建议 | `test_run_diagnostics.py` 八类成功/普通文本负例及六类真实失败正例；保留原 Scope 错误码、Provider 错误和预览/部署后处理问题 |

全量 API **2,128 passed / 1 skipped**（1132.10 秒），定向 API 146 项、Web 296 项/38 文件、启动器 17 项、demo-api 5 项通过。
真实沙箱浏览器断言 React 标题及 CSS 计算样式；没有关闭 chromiumSandbox、安装浏览器或其他依赖。
根 `pnpm check`、OpenSpec 严格校验及 `git diff --check` 通过，任务已完成勾选。Windows 根命令使用本机已有 Git Bash，未安装依赖。

开发服务按正常管理入口重新启动，没有执行中的 TaskRun 被中断。旧预览因原进程结束保留失效历史；
从已有真实 Codex 完成运行创建的新预览为 healthy。其诊断仍包含历史 `preview_failed`，这是准确的后处理
记录，不应为了清空告警而删除历史。MCP `ready` 证明实际握手，不代表这轮又进行了模型工具调用或编码。

控制请求头是公开的浏览器预检标记；本项目仍是本机单用户工作台，没有新增多用户认证。
固定 Vite React 预览不加载项目自定义 Vite 配置，CSS 远程/data/转义导入保守拒绝；不承诺任意插件或预处理器兼容。
测试中的链接在独立临时目录内创建，已安装依赖链接先解除再由 pytest 清理，不改写已有 Session 源码。

## 2026-10-15 远程 CI 跟进

`b3afe0e` 已推送至 dev；[CI 38674503667](https://github.com/YoungBossX/AgentHub/actions/runs/38674503667)
首次 Chrome 启动超时，第二次进入完整测试后为 2,080 passed / 48 skipped / 1 failed。
失败是规范 POSIX `/@fs/home/...` 丢失绝对根后误拒绝依赖，导致浏览器没有渲染标题。
原先本地 HTTP 用例的双斜杠 URL 未覆盖 Vite 实际生成的形式，Windows 本地通过不能替代 Linux 验收。

共用解析器的 POSIX/Windows/虚拟 ID 回归已先红后绿，加入早期 Node 门禁；本地 19 项通过。
规范 URL 的真实 HTTP 越界检查与 React/CSS 浏览器渲染、预览模块 25 项通过。
CI 预检启动预算调整为 30 秒，保留沙箱及全部测试断言，页面失败新增有界诊断。
补丁尚待新 GitHub 运行验证，不把旧提交的本地结果当作新提交的 Linux 通过证明。
