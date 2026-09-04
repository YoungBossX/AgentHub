## ADDED Requirements

### Requirement: 兼容串行与显式并行 DAG

系统 SHALL 同时支持保留既有串行默认行为和显式声明的 fork/join 任务图。

#### Scenario: 缺省依赖保持串行

- **WHEN** Planner 创建多个有序任务且后续任务没有声明 `dependsOn`
- **THEN** 除首任务外的每个任务 MUST 继续依赖前一任务
- **并且** 现有线性 Planner 的执行顺序 MUST 保持不变

#### Scenario: 显式 root 可以并行就绪

- **WHEN** 两个任务均显式声明空 `dependsOn`
- **并且** 其他依赖、审批、queue、lock 和 conflict 条件允许
- **THEN** 两个任务 MUST 都能被评估为依赖就绪
- **并且** 调度器 MUST NOT 因数组位置为后一个任务添加隐式依赖

#### Scenario: Join 等待所有上游

- **WHEN** 一个任务显式依赖两个或更多上游任务
- **THEN** 任一上游未完成时该任务 MUST 保持等待依赖
- **并且** 仅在全部上游完成且其他门禁允许时才可运行

#### Scenario: 非法依赖被拒绝

- **WHEN** Planner 声明未知、自引用或指向拓扑顺序中后续节点的依赖
- **THEN** PlanValidator MUST 拒绝该任务图
- **并且** 系统 MUST NOT 静默删除该依赖后启动任务

### Requirement: 并行提示不绕过安全门禁

系统 SHALL 将 `parallelGroup` 仅作为展示和诊断提示，执行授权仍由依赖、queue、lock、
审批和 conflict gates 决定。

#### Scenario: 并行组中的共享 Session 写任务

- **WHEN** 两个写任务属于同一 `parallelGroup`
- **并且** 它们仍共享当前 Session 的可变 worktree
- **THEN** Session Queue MUST 继续应用当前写入串行规则
- **并且** 系统 MUST NOT 仅根据 `parallelGroup` 同时启动两个 adapter

#### Scenario: 串行场景未声明并行组

- **WHEN** Planner 创建普通线性任务且未声明 `parallelGroup`
- **THEN** 任务 MUST 按声明或兼容默认依赖串行推进
- **并且** UI 或诊断 MUST NOT 将该任务链显示为并行执行

### Requirement: Contract-first Fork Join 图

系统 SHALL 为受支持的 Contract-first 全栈计划表达 Backend 与 Frontend fork 以及 Review/QA join。

#### Scenario: Contract-first 计划创建

- **WHEN** Orchestrator 创建受支持的 Contract-first 全栈计划
- **THEN** Backend 和 Frontend MUST 都依赖已完成的 Planning 节点
- **并且** Backend 和 Frontend SHOULD 共享一个非授权性的并行组标识
- **并且** Review/QA MUST 同时依赖 Backend 和 Frontend
- **并且** 现有 target、文件、审批、queue 和 lock 边界 MUST 保持有效

### Requirement: 安全就绪 TaskRun 有界并发执行

系统 SHALL 通过本地有界 dispatcher 并发执行已经通过现有安全门禁的 TaskRun，并保证
一个 TaskRun 同一时刻只有一个持久化 claim 获胜。

#### Scenario: 两个安全只读 TaskRun 同时执行

- **WHEN** 两个 queued TaskRun 均已依赖就绪
- **并且** Session Queue 将两者判定为可并发的只读运行
- **THEN** dispatcher MUST 在默认并发上限内 claim 两者
- **并且** 两个 adapter 执行区间 MUST 能真实重叠
- **并且** 每个执行 MUST 使用独立数据库 Session

#### Scenario: 并发 claim 竞争

- **WHEN** 两个 worker 同时尝试 claim 同一 queued TaskRun
- **THEN** 持久化条件更新 MUST 只允许一个 worker 获胜
- **并且** 系统 MUST 只记录一个获胜的 `run.claimed` 事件

#### Scenario: 串行写队列保持有效

- **WHEN** 两个写 TaskRun 位于同一 Session Queue
- **并且** 当前仍共享 Session worktree
- **THEN** dispatcher MUST 只启动队首写 TaskRun
- **并且** 后一个写 TaskRun 的 adapter 执行区间 MUST NOT 与前一个重叠

#### Scenario: 既有安全门禁保持有效

- **WHEN** TaskRun 正在等待依赖、审批、Session Queue、Target Lock、conflict gate 或
  provider capacity
- **THEN** dispatcher MUST NOT 绕过对应门禁启动 adapter
- **并且** 执行边界 MUST 再次验证 scheduler、queue 和 lock 状态

### Requirement: 同 Session 显式隔离写执行

系统 SHALL 为显式开启隔离的内置 demo 写 TaskRun 创建独立、可验证归属的 execution
worktree/branch，同时保留 canonical Session worktree 和默认串行路径。

#### Scenario: 不同 target 的独立写分支

- **WHEN** 两个依赖就绪的内置 demo 写任务显式请求隔离且共享干净 Session Git 基线
- **THEN** 每个 TaskRun MUST 获得独立工作树和分支，canonical Session 路径 MUST 保持不变
- **并且** 仅在真实 Git 归属、基线、不同 target 和其他既有门禁均通过时允许执行重叠
- **并且** 分支 MUST 各自产出带 owner 与基线的 Diff patch，不能混入 sibling 修改

#### Scenario: 未知隔离能力保守串行

- **WHEN** 未显式启用隔离、源工作树不干净或隔离预检不能证明归属
- **THEN** 系统 MUST 保留串行路径且不得仅依赖并行组放行
- **并且** 显式请求隔离但回退时 MUST 记录原因，其他冲突门禁仍可阻止运行
- **并且** 已分配分支的路径、branch 或基线被改变时 MUST 拒绝执行和 Diff 采集

#### Scenario: 分支重试保留证据

- **WHEN** 失败或中断的隔离 TaskRun 被重试且原归属和基线仍有效
- **THEN** 新 TaskRun MUST 在同一基线创建新工作树和分支并记录前次运行关联
- **并且** 旧目录、patch 和终态 MUST 保留，不覆盖成功 sibling 的结果
- **并且** 基线或归属无效时 MUST 拒绝重试，不静默转到共享工作树

#### Scenario: 未集成分支不冒充完整交付

- **WHEN** 第三阶段隔离写分支完成但尚无经验证的集成结果
- **THEN** 下游 join MUST 等待集成，preview/deployment MUST 被阻止
- **并且** 一个分支结束触发的调度刷新 MUST NOT 将运行中的 sibling queue entry 回退为 ready

### Requirement: 可审计且可恢复的 Join 集成

系统 SHALL 仅在所有必需依赖完成后集成最新隔离分支，并保留串行路径和既有安全门禁。

#### Scenario: 所有上游完成后确定性集成

- **WHEN** 同 Session join 的全部声明依赖完成，最新隔离 TaskRun 均有通过 scope 的 Diff
- **THEN** coordinator MUST 按固定任务顺序在独立候选工作树应用经 target 校验的 patch
- **并且** MUST 记录分支 Run、Diff、patch hash、基线和集成 commit
- **并且** 仅在 canonical 干净且没有其他非终态运行或 Session 写锁时才可快进推广
- **并且** 新 TaskRun 创建基线与推广 MUST 通过同一 SQLite 写边界串行化

#### Scenario: 冲突不会污染主工作树

- **WHEN** patch 存在合并冲突、越界修改或证据不可验证
- **THEN** 系统 MUST 生成带来源、原因和可用冲突路径的 Conflict Artifact
- **并且** canonical 内容与 HEAD MUST NOT 因失败的候选应用而改变
- **并且** 成功分支和失败候选证据 MUST 保留，同输入同 HEAD MUST NOT 忙重试

#### Scenario: 单分支失败后的恢复

- **WHEN** 一个分支成功而另一个失败，并且失败分支后来成功重试
- **THEN** join MUST 仅采用失败任务的新成功 Run 和原成功 sibling Run
- **并且** MUST NOT 重跑成功 sibling 或覆盖旧尝试的 Diff 和终态
- **并且** 集成冲突 MUST 可通过 join integration retry 操作重新评估

#### Scenario: Git 推广后进程中断

- **WHEN** canonical 已快进但数据库尚未确认 integration ready 时进程退出
- **THEN** 恢复 MUST 从事先持久化的 prepared artifact 核对 candidate、HEAD、parent 和 inputs
- **并且** 验证后 MUST 只确认原集成结果，不重复合并
- **并且** 并发 coordinator MUST NOT 创建两个获胜的推广结果

#### Scenario: 集成交付来源可验证

- **WHEN** 隔离分支触发 preview 或 deployment
- **THEN** 系统 MUST 验证当前 clean canonical 对应的 ready integration artifact
- **并且** MUST 使用集成目录与 commit，而不是单分支目录
- **并且** MUST 拒绝仅凭 merged 标志放行或将旧 Preview 冒充当前集成结果

### Requirement: 可核实的 DAG 执行展示与预演

系统 SHALL 区分声明依赖、实际运行证据和集成结果，保留串行及安全门禁诊断。

#### Scenario: DAG 与执行证据分离

- **WHEN** UI 展示线性、fork/join 或带 parallelGroup 的任务
- **THEN** MUST 按实际依赖显示串行、分叉、汇合及并行组提示
- **并且** MUST 显示 scheduler/queue 阻塞和隔离回退原因，不能仅凭并行组宣称执行重叠
- **并且** 生命周期重叠 MUST 依赖完整有效时间区间，不冒充 provider 性能证明

#### Scenario: 集成历史不得冒充当前证据

- **WHEN** join 包含 ready、prepared 或 conflict 制品
- **THEN** MUST 区分已验证集成、历史或未验证集成、待恢复准备记录和冲突
- **并且** ready 标记 MUST 经服务端复验，不能信任 plan 或 run 中的 merged 自报

#### Scenario: 有界回归证据

- **WHEN** 完成并行 DAG 冻结预演
- **THEN** MUST 记录实际适配器区间重叠、分支 Diff、join commit 和失败恢复
- **并且** MUST 包含串行不重叠对照，并明确测试替身与真实 provider 的边界
