# 主题切换颜色一致性验收

范围：`agenthub-theme-transition-consistency` 1.1，已有主题切换的瞬态颜色一致性。
实现、边界测试、实际浏览器和最终检查完成；本地未提交。

## 诊断修正与实现

上一项截图在点击暗色按钮后立即截取，出现了白底浅字。继续核查后确认：
稳定暗色样式是正确的，成果背景为 `rgb(23, 30, 42)`，标题为
`rgb(230, 237, 247)`；并非持久白色卡片。旧 CSS 的颜色过渡让标题立即换色，
背景仍从白色渐变，形成短暂混合。原先把该截图当作持续主题缺陷的判断过强，
这里用即时/稳定样式和逐帧采样修正，不删除原始截图证据。

主题应用前在当前 document 标记 `data-theme-changing`，短暂暂停元素和伪元素
transition。保留到新配色渲染一帧后，再恢复原过渡；generation 检查避免旧
回调解除较新的暂停。显式切换和实际跨标签页 storage 更新走同一路径，原始
localStorage 失败处理、初始化、hydration 和主题配色不变。iframe 为独立
document，当前文档的规则无法穿透；不改预览的安全策略或源码。

暂停覆盖当前文档的 CSS transitions，不停用 CSS animations；后台标签页的
animation frame 可被浏览器延后，页面恢复渲染后按相同两帧流程清除暂停。
不把两帧称为固定毫秒数，也不永久禁用组件的悬停动画。

## 实际验证

Edge 使用已有完成会话 `ac5dccd4-55ed-4c4a-b0be-bd33ff94636d`，复用当前服务
拥有的健康 Vite Preview（47037）；没有新建编码/评审/预览运行。

每次切换记录即时样式和后续六个 animation frame，覆盖成果标题/说明/来源、
主按钮、次按钮及成果面板标题。三次显式切换、一次快速三连切换及实际第二个
标签页发起的两次切换，共 **42 个样式采样 / 252 组前景背景对**，各序列的
即时颜色与稳定颜色一致，无混合配色降低对比度。CSS 的 lab/OKLCH 颜色先通过
浏览器 Canvas 转换为 sRGB，不能把 lab 数值误作 RGB。

成果标题暗色对比度约 **14.19**，亮色约 **14.62**；旧 CSS 白底浅字瞬间约
**1.18**。这些是特定采样文字/背景的相对亮度比，不声明整个项目通过无障碍
标准。组件原配色和光标悬停反馈保留：次按钮恢复原 0.15 秒 transition，实际
hover 背景改变并在动画结束后读取。

保存主题后刷新恢复暗色；390×844 窄屏亮暗与正常关闭/重开成果面板通过，没有
横向溢出、页面错误或 hydration 错误。浏览器实际 iframe 的完整正文与 body
前景背景在切换前后相同，仍展示 `Organization Native 20261008` 按钮。
完整 Session/Message/TaskRun API 记录前后相同，源码字节哈希与上一项一致；
页面没有非 GET 请求。既有 GET 的 Preview 健康核查仍可更新健康元数据，
不把整个数据库描述为只读。

本轮浏览器确认开发服务未更新全局 CSS，重启了本轮自有 3000 前端服务并确认
新规则加载；8006 API 和用户的其它服务未重启。早期脚本把隐藏任务按钮当作
采样对象、在窄屏覆盖面板打开时点击后方工具栏，以及把实际 lab hover 颜色
写成固定 RGB 等待，均已修正；这些运行不计为验收通过。

## 检查与边界

Web **215 passed / 26 files**，其中新增三项测试验证首次渲染期间保留暂停、
快速切换旧回调围栏和跨标签页更新；原持久化、storage 失败/清空/无效值、
主题切换及其它前端回归通过。`pnpm check`、strict OpenSpec、Git 空白、
源码/证据哈希及私有 SDK 配置值排除检查通过。

没有修改后端、安装依赖、重跑模型、重复全量 API、提交、推送或部署。
上一项冻结的后端文件哈希与当前版本相同；本轮 Web 数量和浏览器证据是新验证，
不把上一项 API 数量作为本轮新结果。个人项目启动入口/文档与最终全工作流
交付仍需独立完成。

证据：[索引](evidence/theme-transition-consistency/validation-index.json)、
[逐帧浏览器记录](evidence/theme-transition-consistency/browser.json)、
[诊断修正](evidence/theme-transition-consistency/baseline.json)、
[暗色成果](evidence/theme-transition-consistency/dark.png)、
[窄屏亮色](evidence/theme-transition-consistency/narrow-light.png)。
