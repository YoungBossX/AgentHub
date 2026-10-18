# 逗号引导语修复验收

日期：2026-10-18；本地 main `2072231` 之上的未提交修复。

## 根因与修改

旧 SECOND_ACTION 将“逗号 + 修改动词”直接视为第二个动作，因此
`In the demo app, change ...` 在实际只有一个动作时被误判。进一步的红灯测试还
发现，引导语后的否定和解释不能命中句首规则，可能误入修改规划。

新增明确的范围/礼貌引导语识别：只从边界分析文本移除已识别的中英文前缀及逗号，
支持连续中性引导语，然后完整执行原有否定、解释、查询、审查、多动作、引用和参数
检查。原消息与参数提取不改写；未知前缀不随意剥离，不引入模型调用或权限扩大。

覆盖 In/For/Please、演示应用范围、英文/中文逗号及双引导语；真正的第二动作、
省略动词的双文案、引导语后的否定/解释/混合查询/审查、引用和缺失参数保持边界。

## 回归证据

- 修复前：新回归选择集 26 failed / 93 passed，保留红灯日志。
- 修复后：意图识别与实际消息规划路由 227 passed。
- 语料从 73 增至 85：85/85，56 条非执行样例的 unsafeRuleExecutionErrors=0。
  人工语料不能代表真实模型准确率或开放场景泛化性能。
- 相邻群组/工作流回归首轮 123 passed / 1 failed；失败用例 coordinated-contacts
  在基线环境准备中出现 PermissionError，完整报告保留。仅该失败用例在新隔离临时
  环境复跑：1 passed / 98.40s，不修改测试断言，不将两轮计成 125 个不同用例。
- 前端曾因 Node 原生内存分配失败而退出；串行复跑发送框/工作台/名称组件：29 passed。
  静态检查指出新测试的非法 exact 选项，移除后根 `pnpm check` 通过。
- 所有 pytest 经 test-api.sh 创建新外部数据库，未用产品数据库跑测试。

## 原失败措辞的真实闭环

原样发送：

```text
@frontend In the demo app, change the title to "AgentHub migration verified".
```

- Session：`31c5e158-84e6-41c5-8f82-34b814821cc1`。
- Task：`8266588e-a031-44e3-9822-eb19ba661ec5`，只创建一个有界前端任务。
- IntentDecision：change/continue，copy_change/demo_heading_text，参数保留为
  `AgentHub migration verified`。
- 真实 Codex TaskRun：`12f2b4d5-a42d-4307-b28e-9b7ef7cfe605`，completed，未使用回退。
- 真实 Diff：只修改 `apps/demo/src/App.tsx`，+1/−1。
- 版本绑定 TypeScript check、Vite build、3 项产物测试通过；标题需求契约的桌面/
  窄屏文本与运行时四项检查通过。
- 预览 `http://127.0.0.1:28073` healthy、HTTP 200；真实浏览器和工作台 iframe
  均显示 h1 `AgentHub migration verified`。地址仅对应本次进程生命周期。
- 模型评审未运行，QA incomplete，不把固定标题契约当成完整业务验收。

服务正常停止后加载修复，三个先前受管预览输出重新启动并核验 HTTP 200；未改写旧
失败记录。原数据库版本仍为 current；没有新 schema 迁移或重置历史数据。

## 名称与沙箱分析

界面标题和页脚将旧默认名称 AgentHub Demo 显示为 AgentHub；数据库查找键与
自定义工作区名称保留。真实页面确认不再显示旧品牌，名称兼容测试覆盖旧名和自定义名。
沙箱只交付[候选方案](../../../docs/sandbox-options.md)，没有安装 Docker/WSL 或启动容器。

本机证据目录：`E:\AgentHubBackups\intent-comma-20261018-1792320087638`。
包含 red-tests.log、green-tests.log、adjacent-tests.log、workflow-retry.log、
brand-red.log、brand-green.log、brand-green-sequential.log、final-check.log、
evaluation.json、runtime-flow.json 和 workbench-final.png。
原始失败报告位于 retained pytest basetemp；本次没有提交、推送或新远程 CI。

## 后续交付前验证

用户随后授权提交并推送。本轮根检查通过，完整测试组成逐项通过：API 2551 passed /
1 skipped（Windows 不适用的 POSIX 大小写用例）、Web 329（串行）、本地工具 24、
demo-api 5。相邻完整工作流在该 API 批次通过，不再以局部复跑代替本轮全量结果。
日志与 JUnit 保存在 `E:\AgentHubBackups\delivery-workbench-20261018-1792322555974`。
上文为原实现阶段的历史记录；远程 CI 在本次提交推送后按精确 SHA 单独核验。
