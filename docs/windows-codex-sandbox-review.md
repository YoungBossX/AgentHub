# Windows Codex 原生沙箱修复

日期：2026-10-07。对应 OpenSpec `agenthub-windows-codex-sandbox-selection` 1.1。

## 结果

当前真实 Codex CLI `0.162.0-alpha.2` 已在三个新建外部目标中完成实际文件修改。
本轮固定三项合成编码基准为 **3/3**，独立功能测试为 **10/10**；每项都有 Provider
thread/turn、有效规则 receipt、通过的 scope、新增输出完成证据与匹配的非空 Diff。
验收脚本和非目标脚手架保持不变。没有使用 Mock 或人工应用模型回答中的代码。

先运行的独立单项为 **1/1**、功能测试 **3/3**，随后在另一个新目录运行完整三项。
单项不计入三项报告分母。历史 0/3 报告保持原字节。

| 任务 | 本轮 TaskRun | 功能测试 | 结果 |
|---|---|---:|---|
| 标题规范化 | `582527fa-1112-48f1-9c51-ce76dca304e6` | 3/3 | passed |
| 整分折扣 | `339432d5-770e-4b85-b478-773ab403b9be` | 4/4 | passed |
| 图书搜索 | `1ae9af3f-aaa3-4a97-bd37-31f1a4b243ad` | 3/3 | passed |

原始机器报告：

- [单项](evidence/external-task-benchmark/windows-sandbox-fixed-single.json)，SHA-256
  `886ecc21c5f77c92ea1b0696f6582a5ebf7b3ea22b511f3e4c28d1b2ec05c7bd`。
- [三项](evidence/external-task-benchmark/windows-sandbox-fixed-suite.json)，SHA-256
  `2b1a5f08667e29ffb571c3a6fd8c6a29ec4163b3be2feeea1bf0985c31b8ae2c`。

## 原因与修改

适配器有意使用 `--ignore-user-config`，全局 `[windows] sandbox="unelevated"` 不会进入
该执行命令。在正常继承权限的新目录中，同一 CLI、相同环境白名单、相同任务仅增加
显式 `-c windows.sandbox="unelevated"` 就能从工具创建被策略拒绝变为真实读取、追加和
回读成功。这为本机当前 CLI 的原生沙箱选择提供了直接对照证据。

此前 `tempfile.mkdtemp()` 探针目录具有关闭继承的 OWNER RIGHTS ACL，直接读取仍被
拒绝；普通新建目录可以读写。该夹具限制不能推导为所有 Windows 工作区不可访问。
旧三项基准目录本身具有正常继承权限；本轮不修改旧目录或宿主 ACL，也不覆盖旧诊断。
Python 自 3.12.4 起在 Windows 处理 `mkdir(mode=0o700)` 的访问控制，见
[Python 官方说明](https://docs.python.org/3.12/library/os.html#os.mkdir)。

CodexAdapter 现在仅在 Windows 的可执行文件后增加固定全局参数。其余 `never`、
`exec --json`、绑定工作树的 `--cd`、`workspace-write`、`ephemeral`、
`ignore-user-config`、`ignore-rules`、指令分隔符与环境白名单全部保留。
Linux/macOS 的命令形态不变。

命令守卫只在 Windows 识别这个精确的 17-token 形态，随后继续校验原来的完整
15-token 形态与 cwd。不同模式/配置、任意 TOML 注入、重复覆盖、额外目录、网络
放行、全访问和缺失参数均拒绝。旧的有界命令保持兼容，不新增任意配置入口。
写任务完成判定保持原状：只有新增文件输出及有效 Diff 才能产生成功 Review；无输出
仍失败。`completionValidation.functionalAcceptance=not_evaluated` 表示应用门禁未做
功能验收；本轮功能通过来自独立 Node 验收器，二者没有混淆。

## 验证与边界

先验证新增用例在修改前失败：Windows builder 和白名单正例 **2 failed / 24 passed**。
修改后，适配器、守卫、ClaudeCode 与基准 runner 回归 **121 passed**；执行引擎与
作用域回归 **456 passed / 1 POSIX-only skipped**，合计 **577 passed / 1 skipped**。
覆盖非 Windows 命令形态、非法参数、scope、无输出/空 Diff、只读、代次围栏与既有
执行路径。本轮没有重复 API 全量或 Web 全量测试；这些数字是相关模块回归。

`pnpm check`、strict OpenSpec 和证据哈希检查通过。第一次项目检查因 PATH 缺少 Bash
而停止，随后仅在该检查子进程 PATH 中加入已安装的 `E:\Git\Git\bin` 后全部通过。
未安装依赖，未永久修改系统 PATH。机器验证见
[验证清单](evidence/external-task-benchmark/windows-sandbox-validation.json)。
该清单同时绑定原始参数对照、显式沙箱对照、继承目录与 OWNER RIGHTS 目录的四份
原始探针报告和哈希，保留修复前后的诊断证据。

本轮是小型固定合成任务的单次真实验收，不是通用编码能力、稳定成功率或并行性能
证明。没有验证 Planner、聊天、Preview、build 或部署；模型与上游服务身份未由本
基准断言。每项只允许编辑 `src/domain.mjs`，没有扩展任务权限。

选择的 `unelevated` 使用受限 Windows token 与 ACL，网络隔离弱于官方优先推荐的
`elevated` 模式；本轮没有创建沙箱用户、配置防火墙或声称已具备 elevated 隔离，见
[官方 Windows 沙箱说明](https://learn.chatgpt.com/docs/windows/windows-sandbox)。
这些成功结果也不证明 OWNER RIGHTS 临时目录已得到修复。

开发工作区未提交或推送。UI 设计已确认，本任务没有开始 UI 实现。
