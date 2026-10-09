# 工作台亮色 / 暗色切换

日期：2026-10-07。OpenSpec：`agenthub-workbench-theme-toggle` 任务 1.1。

原界面固定为亮色，没有切换按钮。现于工作台顶部工具栏添加月亮/太阳按钮，
提供「切换到暗色模式 / 切换到亮色模式」可访问名称、当前状态和键盘焦点提示。
默认仍为已认可的亮色样式；显式选择保存在本机 `localStorage` 的 `agenthub.theme`，
刷新恢复、同源标签页同步。存储不可用时当前页面仍能切换；非法偏好回退亮色。

根布局使用固定 `beforeInteractive` 初始化脚本；共享配色适配会话侧栏、聊天气泡、
任务/事件/成果卡片、设置页面、SVG 依赖节点和只读 Monaco Diff。
Preview iframe 中的应用有独立主题，未注入脚本或修改安全策略。
未增加依赖、后端改动或 Provider 执行，也未提交/推送。

验证结果：

- Web **17 files / 151 passed**，包括双向切换、刷新初始化、非法值、存储读写失败、
  跨标签事件和已打开 Diff 编辑器随主题变化；原有 143 项回归保留。
- `pnpm check` 通过（Web ESLint/TypeScript、API/Demo API compileall、Demo TypeScript）。
- 浏览器实际切换两种主题并分别刷新恢复；暗色下检查任务依赖图、成果面板与补丁。
  默认视口截图为 1145×1244；窄屏 390×844 的按钮可达，页面宽度实测 390，无整体横向溢出。
- 使用前轮临时历史基准数据库展示实际制品，没有重跑 Provider 或声称新健康 Preview。
  浏览器初始加载发现测试 API 已停止，恢复了 `8006` 上的同一临时副本服务；未触碰原有 `8000` 服务。
- strict OpenSpec、空白及证据哈希检查通过；前轮 UI 哈希是当时的冻结记录，本轮新增独立主题记录。

截图：[暗色过程](evidence/conversation-workbench/agenthub-theme-dark.jpg)、
[亮色工作台](evidence/conversation-workbench/agenthub-theme-light.jpg)、
[暗色窄屏](evidence/conversation-workbench/agenthub-theme-mobile.jpg)、
[暗色 Diff](evidence/conversation-workbench/agenthub-theme-diff.jpg)。
来源哈希见 [主题证据](evidence/conversation-workbench/theme-validation.json)。
