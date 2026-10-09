# 受限源码编辑与应用 Diff 验收

日期：2026-10-09。范围：`agenthub-bounded-code-editing` 1.1，本地单用户。
实现、真实运行与对应回归已通过，1.1 已勾选。本地改动未提交。

## 实现

- 新增完整当前源码读取与本地 Monaco 编辑，文本框可作为加载失败回退；统一 CRLF
  在输入和拟应用 Diff 中保留。原始 Diff 片段不作为完整文件或自动重放的补丁。
- 先准备精确 UTF-8 差异，再明确应用；受限多文件增删改，不猜测偏移或模糊匹配。
  16 个文件、补丁 2 MiB、单文件 512 KiB、前后内容合计 4 MiB。
- 校验规范 Session 工作树的注册/仓库/目标/HEAD、文件内容/模式及保护路径，拒绝
  设备名、短名/大小写别名、链接/硬链接、Windows 命名流和不存在的父目录。
- 与 TaskRun/队列/Target Lock/join 互斥；SQLite 写锁先保留应用资格，再保存 applying
  记录，之后才写文件。用户修改有独立 Artifact/ArtifactVersion，不创建假 Agent。
- Windows 句柄防止其他程序同时写入/删除文件、替换父目录。部分失败只回滚仍符合
  本次完整输出的内容；不能判定的部分/外来修改保留为 unresolved 并阻止后续运行。
  启动恢复区分全部原始、全部输出与部分状态，不自动重放文件修改或模型执行。
- 历史 Agent Diff/评审保留；后续 Agent 在取得执行权限后捕获文件快照，Diff 不重复
  计入已存在的用户改动。旧 TaskRun 重采集 Diff/部署拒绝，新预览标记实际用户来源。
- 用户操作历史独立展示最近 50 项，文档工作台不批量载入恢复用全文；浏览器草稿
  保留请求 ID，可恢复丢失响应。跨会话晚响应不覆盖新内容。

## 实际发现及修复

1. Windows `nul.txt` 初始解析未拒绝。现于任何读取前拒绝设备名和别名，保留失败记录。
2. 第一轮浏览器在 390px 发现补丁撑大网格，控件超出视口。设置成果网格单列及
   Diff 卡片 `min-width: 0`；重新验收 390/320px 的所有编辑控件均在视口内。
3. textarea 归一化 CRLF，导致一行编辑显示整文件替换；保持源文件统一换行后重新
   验证，拟应用 Diff 仅替换主标题行。
4. 首次原生续接返回 CLI 不存在。本机二进制实际存在，独立 40,000 字符参数复现
   `FileNotFoundError / errno 2 / WinError 206`。长 Planner 参数改用既有 stream-JSON
   stdin，保留工具策略和输出校验；重试实际原生续接成功。未安装或替换 CLI。

## 真实闭环

- Session：`61107635-b6c9-49e8-99b8-42ad57e7f68e`。
- 第一次 Claude TaskRun：`f5ba5ba6-fd7f-4560-8b2b-6fdd532e774c`，先生成
  `Manual Edit Baseline 732`。不是用手工写文件伪造 Agent 产物。
- 浏览器读取完整源码，编辑为 `Manual Edit User 732`；准备阶段源文件不变。
  用户操作 `ba1e5adf-d809-43e2-8d6d-ca2441fb0885` 明确应用后实际 Vite 标题匹配。
- 第二次 Claude TaskRun：`f742f005-ca9c-4281-a3ad-f0e9a3f6f07f`，保留用户标题并新增
  `Native Continuation 732`。新 Diff 使用 `filesystem-snapshot:` 基线，未把用户标题
  行作为新 Agent 增加行；旧 Diff 响应哈希不变。
- API 正常停止/重启后，本 Session 的 1 Session / 7 Message / 2 Task / 2 TaskRun /
  6 Diff、Review、用户操作 Artifact / 6 ArtifactVersion / 2 Diff 行集和源码哈希一致。
  恢复的真实预览 `6c0c64a0-a140-4edf-a3d2-55fc2c8aefde` 显示标题和新增段落，
  工作台显示用户修改记录。源码 SHA-256：
  `5584e26beb00ca5351fded6d0ae1dc4f24f636581d7165f82507f0e28dd83d60`。
- 本轮前已有 36 Session / 112 Message / 49 TaskRun / 40 Diff / 40 Review / 11 Attachment /
  6 AgentProfile 和配置内容保留，仅原有调度器任务 `d9e6e037-46d1-42ef-984e-a473b6bb9e2b`
  的正常 `updated_at` 改变，未修改 Planner 默认配置。

## 验证与限制

| 验证批次 | 结果 |
| --- | --- |
| 精确补丁/用户操作新增测试 | 68 passed；随后新增实际执行基线 1 passed、Windows 命名流 1 passed |
| Diff/预览/部署/集成/执行工作树/P23 相关回归 | 166 passed |
| 全量 API 阶段 | 1,942 passed / 1 POSIX-only skipped，35,926 条既有 UTC 弃用警告，1,162.81 秒 |
| 全量启动后的 Planner 长 stdin、文档工作台过滤等改动 | 相关 132 passed，命名流测试另 1 passed；没有把较早的全量运行冒充最终所有文件的整套重跑 |
| 最终 Web | 33 个测试文件 / 263 passed |
| 最终工程检查与生产构建 | `pnpm check`、Next 16.3.8 build、strict OpenSpec 通过 |
| 实际浏览器/原生/重启 | 两次 Claude 文件修改、用户应用、Vite、亮暗/窄屏、记录和源码一致性通过 |

浏览器为本地 Next 开发服务，
生产构建成功不等同生产模式浏览器验收。真实链路使用 Claude Code；本项没有新增
Codex 原生运行，不以它替代既有 Codex 证据。

应用仅支持规范分配的 Session 工作树，旧式直接在主机目录执行的外部目标不开放
用户写入。POSIX 使用 no-follow/身份/内容核验和协作式文件锁，不能把它表述为对任意
不合作主机进程的强隔离。启动恢复假定单个 API 所有者。恢复时遇到绑定变化或不安全
文件仍保留围栏，需要恢复正确的目标/文件后再核对，不能强制覆盖。

整体项目目标仍未完成：本任务结束后还需整体工作流/UI 终验及既有时间警告处理。
本轮未提交或推送，没有新增依赖、数据库表或生产部署。

本项代码、规格、文档、原始验收记录与脚本的 SHA-256 见
`docs/evidence/bounded-code-editing/validation-index.json`。SQLite 备份仅在本机临时目录，
未归档到仓库。最初窄屏失败、CLI 失败与修复后成功分别保留。
