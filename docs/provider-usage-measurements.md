# Provider 用量与执行阶段记录

该能力扩展已有Planner、Adapter回执和TaskRun JSON指标，不创建表或改写旧回执。
Claude/Codex CLI与ScriptedMock保持原有权限；没有安装依赖或增加Agent工具。
历史没有这些字段的记录继续兼容，缺失不能解释成零消耗。

## 每次调用的用量

`providerUsage.schemaVersion = agenthub.provider_usage.v1`。编码/只读QA记录在TaskRun指标和
唯一最终Adapter事件，Planner记录在`PlannerProviderResult.to_metadata()`及实际规划观察回执。

| 字段 | 含义 |
| --- | --- |
| `inputTokens` / `outputTokens` | CLI结果中报告的输入、输出计数，无有效回执时为null |
| `cacheReadInputTokens` / `cacheCreationInputTokens` | 分别保留缓存读取和创建；不存在的字段为null |
| `tokenTotal` / `tokenConvention` | Claude为非缓存输入+缓存读取+缓存创建+输出，四项齐全才给总数；Codex输入已经包含缓存，输入+输出即可，不能再加缓存 |
| `estimatedCostUsd` / `billingVerified` | 仅保留Claude CLI报告的估算，账单核验始终false；Codex缺失费用不推算为0 |
| `providerDurationMs` / `providerApiDurationMs` / `providerTurns` | CLI自己报告的跨度与轮次，不等于平台墙钟或纯推理耗时 |
| `reportedModels` | 最多16个有界CLI模型标签；不证明转发网关的实际上游型号 |
| `status` | reported为本协议计量必需项齐全，partial为部分计数可用，unavailable为未报告计数；均不是账单或质量认证 |

只提取白名单字段；布尔、负数、非有限值、字符串数字、不安全的大值和小数Token拒绝为null。
合法0与缺失区分。流式assistant快照及`modelUsage`的数值不会再叠加到最终usage。
现有工具白名单不允许模型派发子Agent；其他协议/未报告用量的Adapter仍可运行，但没有数据不能纳入完整Token总量。

每个独立TaskRun或实际Planner调用只计一次，失败与显式重试也参与。
收到早期错误后保留失败原因，完整读取最终回执并等待进程退出，再发一个失败终态。
这保留原有终态所有权fence，不允许已失败TaskRun补写后续Adapter事件。
Codex运行时MCP凭据的专用脱敏在原包装层继续执行，连同新增回执一并脱敏。

Planner普通输入使用JSON结果包装，长输入/附件仍走已有stream-json stdin；仅解包结果正文供原规划契约校验。
旧命令运行器返回纯规划JSON的测试/兼容路径继续保留，但缺少usage时明确未知。

费用语义依据[官方用量说明](https://code.claude.com/docs/en/agent-sdk/cost-tracking)：CLI/SDK费用是客户端估算。
当前订阅与转发服务未核实实际计价，不能把估算总和写成“真实花费”或宣称节省费用。

## 阶段时间

`executionTiming.schemaVersion = agenthub.execution_timing.v1`持久化启动、首段语义文本和Adapter终态。
Adapter启动与文本/终态跨度使用同一单调时钟；UTC时间用于对应持久化事件。

| 阶段字段 | 边界与口径 |
| --- | --- |
| `planningDispatchMs` | 生产消息路由调用开始至任务派发返回；包含Planner调用、规则与数据库操作，Planner自身duration另存 |
| `queueWaitMs` | SessionQueueEntry入队至领取；没有领取时间就为null |
| `preAdapterMs` | 领取至Adapter.createRun调用开始；包含权限、绑定和启动准备 |
| `adapterLaunchMs` | 调用Adapter.createRun至其返回 |
| `firstSemanticTextMs` | Adapter调用开始至应用收到第一段非空、脱敏的语义正文；只认明确的Claude文本与Codex agent_message，不把工具JSON或状态当正文 |
| `adapterWallMs` | Adapter调用开始至完整读取/等待进程结束后的唯一终态；成功失败使用同一边界 |
| `finalizationMs` | Adapter终态至TaskRun结束，包含实际Diff/范围/固定验证等收尾；不是纯测试时间 |
| `attemptEndToEndMs` | TaskRun创建至结束，包括排队、准备、执行及收尾 |
| `workflowExecutionMs` | 该需求阶段的工作循环，包含编码、QA、重试和进度采集；其内部跨度不能重复相加 |
| `independentAcceptanceMs` | 该需求阶段的独立固定业务检查；仅完成返回的检查计时，结果可以是失败 |
| `episodePipelineMs` / `episodeIncludingPreparationMs` | 单个评测episode不含/含隔离fixture准备的完整流程 |

首段正文是应用观察点，不是上游首Token；流中间快照、脱敏和调度均会影响它。
启动、首段文本和Adapter总跨度相互嵌套，不能当作独立阶段加总。
取消或异常中断的阶段为null，不进入已完成阶段的分位数；父级完整失败耗时仍保留。
旧记录、未开始、无正文或时钟顺序异常均保持未知，不制造0ms。
本轮Windows/Python3.12的单调时钟报告分辨率为15.625毫秒，见E盘`runtime-preflight.json`。
输出单位和小数位不代表亚毫秒准确度，不使用这些样本宣称微秒级性能。

## 汇总与评测

`summary.measurements.providerUsage.fields`对每项给出`known`、`unknown`、`knownSum`和`total`。
存在缺失时只有已知小计，完整总量为null；没有调用样本时总量也为null。
`callRecords`计量的是去重的Planner调用记录加TaskRun尝试，不是底层HTTP请求数量。
故障注入可能在启动CLI之前失败，该尝试仍留在分母且用量未知，不伪造一份零Token回执。
`summary.measurements.stageTimings`给出已观察/未知数及nearest-rank P50/P95/max，均只描述当前样本。
旧字段`medianElapsedSeconds`及`elapsed.medianSeconds`保持原先的`statistics.median`定义，偶数样本取中间两项均值；
新P50按nearest-rank选取样本，两者不可混用。TaskRun阶段混合编码与QA，规划和验收按需求阶段汇总；每列都有自己的样本量。
每类10次重复的P95常为该类最大值，不应称为稳定尾延迟；不同场景混合总P95不能代替同类分位数。

普通50次、探针、故意失败恢复及追加修复独立报告，保留所有失败。
正式50次是5类固定场景各重复10次，不是50种任意请求；任一运行时/操作器源码变化会使批次失效，
不能将修复版样本拼回旧版本。Token汇总涵盖规划、编码、QA、失败和重试，但不代表其他未观察到的后台服务调用。
本轮原始数据、源码快照和临时文件在`E:/Docker/AgentHub/usage-latency-20261020-01`；
结果以该目录最终报告为准；已完成批次的分母、失败和验证边界见
[中文同版验收](chinese-usage-latency-validation-20261020.md)，不把采集功能等同于任务全通过。
