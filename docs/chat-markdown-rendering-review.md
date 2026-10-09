# 普通聊天 Markdown 与代码复制验收

日期：2026-10-08。对应 `agenthub-chat-markdown-rendering` 1.1，本地未提交。

## 实现范围

普通聊天正文从纯文本段落改为标准 Markdown/GFM：标题、强调、嵌套列表、只读
任务列表、引用、表格、行内代码、代码块、链接和脚注。沿用已有亮暗主题变量，
代码和表格在消息内部横向滚动。结构化群聊汇总继续使用原组件，存储内容、原文
引用、置顶和整条消息复制保持原语义。

代码块展示语言标签和独立复制按钮，只复制代码内容（含渲染代码的换行），不包含
围栏、语言标签和控件。共享复制控件处理缺失/拒绝剪贴板 API，显示成功或失败，
消息更新后不会把旧请求结果显示成新文本复制成功。Windows 原生剪贴板读取会将
LF 转成 CRLF，浏览器验收仅归一化该操作系统换行差异；单元测试核对原始写入参数。

新增并锁定 react-markdown 10.1.0 和 remark-gfm 4.0.1，安装前已说明，执行时
禁用安装脚本。解析使用语法树转 React；没有启用原始 HTML 或 MDX 执行。
原始 HTML 显示为文字，协议仅允许 HTTP(S)、mailto 和消息内脚注片段；拦截
控制字符、反斜杠、凭据 URL 及其他协议。脚注标题、引用与回跳 ID 按消息区分。
远程图片默认只显示描述、来源及加载按钮，点击后才创建图片元素，并禁止发送
referrer；跨源以匿名方式请求。超过 100,000 字符时，完整原文以带提示的纯文本
形式显示，不丢弃内容。

实现参考官方 [react-markdown](https://github.com/remarkjs/react-markdown) 与
[remark-gfm](https://github.com/remarkjs/remark-gfm) 文档，并读取已安装 Next.js
Client Components/CSS 指南。没有引入自制 Markdown 语法解析器。

## 验证

- 新增 18 个测试节点；定向 19 passed，Web 全量 **233 passed / 27 files**。
- Web ESLint/TypeScript 与实际 Next.js 16.3.4 生产构建通过。
- 实际 Edge 访问普通 API 写入的持久化消息，会话
  `fa77822b-e385-4f88-9012-c90d0f5496ca`，消息
  `bb630d3b-c11b-4b89-a492-1299e4a110ce`。
- 代码剪贴板与原文复制、引用/置顶、刷新、亮暗主题、危险 HTML/链接惰性、图片
  点击加载和刷新恢复、剪贴板拒绝提示均已实测，无页面 JavaScript 错误。
- 1440/390/320px 下 document 宽度分别仍为 1440/390/320px；长代码内部滚动
  宽度 6463px，表格内部滚动宽度 1497px，没有撑宽页面。
- 浏览器内容是明确标记的展示样例，经普通消息 API 保存；图片响应由测试路由
  控制，不冒充真实模型回复或真实外部图片服务。前项原生运行证据保留，本项没有
  修改后端执行、记忆或文件权限逻辑。

## 依赖审计与未完成项

锁文件新增 97 个传递/直接包版本，没有移除或升级既有包版本；少量既有快照差异
来自 pnpm peer 依赖去重。生产依赖审计为 **12 条告警**：1 critical、3 high、
5 moderate、3 low。使用原始锁文件和原始应用 manifest 在独立目录、不安装依赖
的情况下重新审计，告警 ID 和数量完全一致；新增 Markdown 依赖未增加告警。

这是旧依赖链的新鲜安全缺口，不是“审计通过”或可沿用历史零告警。受影响组件
包括 Next.js、DOMPurify、sharp、source-map-js 和 baseline-browser-mapping。
下一独立任务优先完成安全更新和兼容验证；当前普通消息展示任务不掺入框架升级。
附件上传、模型图像/文件输入、消息重新生成和对话创建 Agent 仍需继续实现。

代码、规范、文档、检查日志与浏览器证据见
[validation-index.json](evidence/chat-markdown-rendering/validation-index.json)。
