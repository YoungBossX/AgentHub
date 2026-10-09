# 三栏边界拖动验收

日期：2026-10-07。OpenSpec：`agenthub-resizable-workbench-columns` 任务 1.1。

桌面三栏的左右分界线现均可拖动。命中区域为 9px，悬停/键盘聚焦时高亮，
支持方向键每次微调 16px、Home/End 到边界、双击恢复对应栏默认宽度。
左栏 180–360px、成果栏 280–720px，中间至少 400px；默认 220/360px，
容器 ≥1600px 时默认 240/420px。实际可调上限同时受当前容器和另一栏宽度约束。

宽度保存在 `localStorage` 的 `agenthub.workbench-columns`；刷新恢复，
存储无效/不可用时保持可用。容器收窄时显示宽度受约束，放大时仍保留偏好。
指针捕获与临时透明遮罩保护拖动输入；pointer cancel、Escape、窗口失焦或离开桌面宽度
会恢复拖动前设置并清理遮罩。没有改动 iframe 内容、权限或执行流程。

1200px 以下保留现有双栏/覆盖面板和移动抽屉，不显示拖动手柄。
成果面板收起时仅左手柄可用，展开时隐藏两手柄，恢复后保留宽度；三个内容区域不因
调整尺寸重新挂载任务列表。无依赖安装、后端代码修改、提交或推送。

验证：

- Web **18 files / 159 passed**（新增 8 项）：分别拖动、非当前指针忽略、完成后持久化、
  三类取消、键盘/极限尺寸、中间最小空间、窄屏取消、异常存储、单栏重置与面板模式。
- `pnpm check`、strict OpenSpec、Git 空白检查通过；本轮未修改后端，没有重跑 API 全量。
- 1440×900 实际浏览器拖动左栏 **220→300px**、右栏 **360→500px**，
  DOM 实测列宽 **300 / 640 / 500px**，拖动结束遮罩移除。刷新后两边仍为 300/500。
- 实际双击恢复 220/360；方向键将左栏变为 236，再恢复默认。
  成果展开/恢复/收起时，分界线数量分别为 0/2/1；暗色配色兼容。
- 390×844 实测文档宽度 390，两手柄 display:none，输入和原抽屉布局保持可用。
- 使用既有临时历史基准副本展示实际制品，未启动新 Agent/Provider 或声称新预览成功。

[拖动后的三栏](evidence/conversation-workbench/agenthub-columns-resized.jpg)、
[暗色分界线](evidence/conversation-workbench/agenthub-columns-dark.jpg)。
源码/截图哈希和浏览器尺寸记录见
[机器证据](evidence/conversation-workbench/columns-validation.json)。
