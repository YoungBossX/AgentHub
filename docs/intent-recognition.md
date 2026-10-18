# 意图识别边界与离线评测

2026-10-17 本地识别边界，2026-10-18 增补群组 Planner CI 回归修复。

## 当前处理方式

消息先解析正文中未被引用的角色，生成服务器 `IntentDecision`。`@frontend` 等仅
选择角色，不把解释、查询、否定或引用示例自动变成写任务。

启用 Planner 时仍复用原有一次模型调用及结构化 ConversationOutcome，不增加额外
分类调用。有效任务计划继续接受原有图、目标、权限、审批和执行检查；解释/查询/纯
对话或审查请求与模型写计划冲突时，不创建该写任务。审查的确定性兜底创建现有
只读 review 任务，而非前端修改任务。

已识别的多项动作、省略第二个动词的标题/按钮组合、未解析指代等交给协调者
Planner；Planner 不可用、失败或返回非任务结果时不执行部分规则匹配。显式直接
指派遇到这些歧义会请求澄清，用户可改用 `@orchestrator` 进行完整规划。显式群组
使用既有群组 Planner 理解完整请求，且必须获得有效原生计划；没有有效计划时
回滚未保存任务并请求澄清，不允许退回确定性群组协调。

已识别的否定、纯引用/代码、未闭合代码块、空参数或超长参数保守停止。有效单项
登录页、文案、颜色、字段和固定应用创建继续使用既有路径。标题/按钮文案支持
中文“改成”后不带空格。文案最长 60 个 Unicode
字符，不再截断后执行；引号内标点和 @文本保留为参数，不能选择 Agent。应用类型
规则要求创建动作直接指向该类型，单独出现 todo/联系人/笔记不生成固定应用模板。

这些是有界词法规则，不是完整中文语义理解，也不是权限或安全沙箱。未覆盖的新
表达仍可能需要增加反例或由 Planner 处理；执行范围仍由原有服务端控制决定。

## 统一结果

用户消息 API 的 `intentDecision`，数据库既有 message context 的 `_intentDecision`，
以及该消息新建任务的 `planJson.intentDecision` 使用同一服务器结果：

| 字段 | 含义 |
|---|---|
| schemaVersion | 当前为 1 |
| requestType | change/review/explain/status/chat/no_action/clarification/unknown |
| route | continue/planner/reply/clarify |
| source | rule 或 llm；表示决策路径，真实 Provider 身份仍看 plannerEvidence |
| action / target / parameters | 规则识别的动作、对象、有界参数；模型计划不沿用可能冲突的规则参数 |
| reasonCodes / missingFields | 路由依据和缺失字段，不伪造置信概率 |
| roles | 已验证的显式角色 |

`continue` 只表示继续既有规划/指派流程，不等于执行授权或验收成功。`planner`
表示不能使用规则兜底，`reply` 表示非写请求，`clarify` 表示需要补充信息。
调用者提交的 `_intentDecision` 在消息创建时丢弃；服务器重新计算，不从它读取授权。
旧消息不回填、不改写历史运行。模型测试替身同样走 llm 决策路径，但测试结果不能
声明真实模型能力。

## 复现离线评测

从 `apps/api` 使用仓库已安装的 Python 环境：

```powershell
..\..\.venv\Scripts\python.exe -m app.intent_evaluation --output C:/Users/XCC/AppData/Local/Temp/intent-report-new.json
```

输出文件必须不存在。工具不调用 Provider、不创建 Session/任务、不执行代码；读取
版本化 `apps/api/evals/intent_cases.json`，返回语料 SHA-256、类别分母、类型/路由/
对象/参数检查数、规则误执行错误及逐条不匹配。存在不匹配或误执行错误时非零退出。

该语料是人工编写的回归集，包含正常请求、否定、询问、状态、引用/代码、多个动作、
参数、指代、审查和未知输入。分数只代表固定样例，不是独立留出集的泛化准确率、
实际任务成功率、模型质量或性能提升。原版本对照只比较同一批负例的解析器匹配，
不能外推为历史实际误写次数。

本次没有添加 Embedding、小模型、分类训练、依赖或新 UI；原本地验收阶段没有
提交/推送。2026-10-18 用户另行授权当前分支交付及 CI 核对，以实际 Git/Actions
记录为准。
具体最终数字和代码/测试证据见 [验收记录](intent-boundaries-review.md)。
