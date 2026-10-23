# 项目展示图片来源

这些图片来自 AgentHub 实际运行的工作台或生成页面，不是设计稿。README 与根目录
`index.html` 使用相对路径引用，点击图片可查看完整原图。

`brand-icon.png` 直接采用现有应用元数据渲染的 180px 品牌图标，来源为用户提供的
设计，用于页首标识，避免为了小尺寸标识传输整张高分辨率原图。

## 当前工作台回看真实历史记录

以下四图在 2026-10-23 通过当前 UI 截取，展示 2026-10-20 正式中文批次中
`coordinated-contacts` 第 10 次的已完成记录，Session 为
`fc974ec8-ab7c-49c2-8765-39957c6fa801`。

| 图片 | 内容 |
| --- | --- |
| [workbench-process.png](workbench-process.png) | 中文任务依赖图、运行状态及成果面板 |
| [workbench-dark.png](workbench-dark.png) | 同一真实任务的暗色工作台 |
| [workbench-diff.png](workbench-diff.png) | 前端真实 Git Diff 与按任务组织的成果 |
| [workbench-review.png](workbench-review.png) | Claude Code 原生只读评审，保留实际判断与来源 |

仅在隔离数据库副本中读取历史记录，禁用 API 生命周期及后台工作，浏览器只允许
本机 GET/OPTIONS。未重新调用模型、运行任务、启动预览或修改产物，Task/TaskRun/
Artifact/Diff/Review 行集与源数据库逐项核对一致。原始评测库与正式结果没有回写。
截图中的脚本 Review 和原生模型评审有各自来源，不能合并为同一种验收。

## 当时留存的生成结果

| 图片 | 内容 |
| --- | --- |
| [result-preview-desktop.png](result-preview-desktop.png) | 2026-10-20 同一样本生成的联系人页面，桌面实图 |
| [result-preview-mobile.png](result-preview-mobile.png) | 同一生成源码的 390px 实图 |

这两图直接复制原始留存文件，像素未修改。前端通过平台 Vite 预览，后端由操作者辅助
运行真实 ASGI；不代表自动多服务部署、生产上线或本次重新验证页面。

## 统计与版本边界

该展示样本零重试，原流程 388.516 秒；选择通过样本是为了展示协作覆盖，不能代替
正式统计。历史普通批次为五类固定中文场景各 10 次，严格完整验收 40/50；受控故障
恢复 10/10 单独统计。后续代码和评审协议修复不改写原批次，也不继承旧版通过率。

- [历史评测与完整分母](../../chinese-usage-latency-validation-20261020.md)
- [后续原生 QA 修复与复验](../../real-api-stability-validation-20261022.md)
- [当前项目状态](../../project-state.md)
- [逐图尺寸、哈希及运行来源](provenance.json)

新截图、只读数据库副本、浏览器请求审计和行集核验留存于本机
`E:/Docker/AgentHub/public-docs-20261023-01`；仓库不包含原始数据库或凭据。
