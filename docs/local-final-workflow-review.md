# 本地核心工作流终验

日期：2026-10-09。OpenSpec：`agenthub-local-final-workflow-acceptance` 1.1。
当前状态：本地核心工作流终验通过，改动保存在 `dev` 工作区，未提交/推送。
冻结清单见 [验收索引](evidence/local-final-workflow/validation-index.json)。

## 本次修复

- 输入区的隐式网格最小宽度使 320px 视口中的发送按钮右端到达 x=354。
  增加 `min-w-0` 和单列约束后右端为 x=291；390/768/1024/1440px 原布局保持。
- 完整源码编辑器增加“引用选中代码”，兼容本地 Monaco 和纯文本模式。引用保留
  原片段、相对文件名、来源制品和 `editor_draft` 标记，不自动应用或提交。单片段
  最多 2400 个 Unicode 字符，超过时要求缩小选区；最多 8 项上下文。内容变化、
  编辑器模式/文件变化和跨 Session 切换不会复用过期选择。
- 重复点击当前 Session 不再清空成果和上下文；原来没有路由 ID 变化，清空后也
  不会触发重新加载。真实重复选择及前端回归覆盖该问题。
- 新原生验收发现 Planner 未携带消息引用，误把附件里的标记当成目标标题。
  `TaskRun=completed` 和非空 Diff 当时均成立，但用户预期不成立。现将有界引用
  同时传入普通/群聊 Planner 的 canonical context，校验制品 Session 归属、过滤
  敏感值并保留预算。引用字段使用 `conversation_reference`，不标为系统指令。
- 公共时钟改用 `datetime.now(timezone.utc).replace(tzinfo=None)`。固定时钟、
  模型默认值、SQLite 回读和 JSON 验证保留原有 UTC、微秒和无时区序列化约定；
  没有时间迁移，也没有修改历史时间含义。

## 真实运行

继续使用独立验收 SQLite、API 8006 和 Web 3000。维护重启只停止本轮所属的 API，
没有接管其他监听进程。使用已有 Edge / Playwright、Codex CLI 和 Claude CLI，
没有安装依赖或变更默认运行配置。

| 路径 | 结果与证据边界 |
| --- | --- |
| 两个独立 Session | Codex 与 Claude 分别修改自己的工作树，文件与真实 Diff 匹配；目标级写锁仍限制同一目标的同时写入。本次不声明原生写任务获得并行加速 |
| Claude 群聊 | 原生 Planner → 编码 → Claude 只读评审 → 原生协调汇总通过。脚本附带报告和原生评审分别保留，评审不等于执行了测试 |
| 引用首次原生失败 | UI 请求确含 `Selected Context 734`，编码快照也包含它，但 Planner 未收到；实际标题变成附件标记 `Final reference 734.`。保留失败运行和样本，不用后续成功覆盖 |
| 修复后引用续接 | 消息正文不含目标标题，编辑器草稿片段提供 `Selected Context 735`；真实 Claude 文件、Diff 和 Vite 标题一致，附件标记仍不同。引用本身未写文件 |
| 修复后 Codex 续接 | 真实 Codex 将原标题改为 `Final Codex 735`，实际文件与 Diff 一致；重启后 iframe 确认 |
| 强制失败与中断 | 明确注入 `CODEX_DEMO_FORCED_FAILURE`，兜底运行创建后中断，再重试通过 ScriptedMock 修改文件并生成真实表单/Diff/Preview。此处验证的是受控失败和队列中断，不是假称自然供应商故障 |
| 预览与交付 | 重启后重新启动三场预览，工作台 iframe 分别显示两个原生标题和兜底登录表单；重复点击当前会话保留预览。后端创建 `mock/ready` 部署卡，没有上线或访问假发布地址 |
| 小屏与输入 | 亮暗主题下 320/390/1440px，同时带附件与引用的发送控件可见且可命中；Enter 真实发送、Shift+Enter 换行通过。`isComposing` 事件模拟验证不误发送，不宣称实测了所有系统输入法 |

重启前后对三个新增 Session 的 17 条消息、9 个 Task、9 个 TaskRun、7 个 Diff、
16 个非预览/部署 Artifact、4 个附件及 3 份源码做逐行/文件哈希比较，全部一致。
预览状态在停止 API 后按设计失效，随后明确重启并实际检查 iframe。

本轮开始前的 37 个 Session、119 条消息、68 个 Task、51 个 TaskRun、42 个 Diff、
42 个 Review、11 个附件、6 个自定义档案和 1 份运行配置保留。仅旧 Task
`d9e6e037-46d1-42ef-984e-a473b6bb9e2b` 的 `updated_at` 被既有调度器正常刷新，
其他受核对字段一致。SQLite 备份留在临时目录，不加入仓库。

## 验证批次

- 第一批完整 API：1946 passed / 1 POSIX-only skipped，使用
  `-W error::DeprecationWarning`；该批早于 Planner 引用修复。
- Planner 引用、群聊、上下文与 Provider 契约相关：105 passed。
- 最终 Web：267 passed / 34 files，包含源码选择和重复会话选择回归。
- 本地启动器/依赖补丁测试：17 passed；demo-api：5 passed。
- 根 `pnpm check`、Next 生产构建与 strict OpenSpec 通过。生产构建不等于生产
  服务已上线；实际浏览器使用本机开发服务。
- 默认端口的 doctor 发现正在使用的 3000 并拒绝启动，这是正确的占用保护；
  改用空闲检查端口 3206/8206 后通过，没有停止现有监听者。
- Planner 修复后的最终完整 API：**1949 passed / 1 POSIX-only skipped**，
  `-W error::DeprecationWarning`，耗时 926.50 秒。之前的第一批全量不冒充最终批次。

首轮时钟测试误用了 Workspace 不存在的 `updated_at`，更正为实际 `created_at`
契约后通过。选择脚本最初操作了 Monaco 的辅助 textarea/未注册的查找快捷键，
改为点击可见编辑区并使用真实选择键后通过；不能把这些驱动错误称为产品修复。
切换脚本补充等待路由生效；产品的“重复选择当前会话清空成果”另有独立修复。

## 范围与后续边界

本次核对对象是本地单用户 Coding Workspace。原设计 PDF 的核心 IM、两种原生
适配器、受限自定义 Agent、协调/汇总、连续上下文、过程/结果可视化、代码编辑和
预览已有对应实现与证据，逐项入口见 [交付核对](local-project-delivery.md)。

PDF 的 P2 PPT 浏览、源码包导出、静态/容器生产部署和原生桌面/移动客户端未由
本项实现；PPT 与源码包不能宣称已支持。既有局部 Diff/版本和对话式修改已纳入。
比赛提交材料不再是本地运行验收条件。当前 Claude 模型拒绝图像的既有实测限制、
有界记忆/附件、单 API 进程和人工应用后的独立验证要求继续保留。

完成状态表示指定本地流程和检查通过，不保证任意模型输出在语义上永远正确。
请以实际文件、测试和预览验收产物；不把 CLI 退出、任务状态、静态评审或脚本兜底
单独写成“所有用户需求自动验证通过”。
