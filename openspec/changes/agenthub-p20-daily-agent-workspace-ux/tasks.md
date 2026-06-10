## 1. 会话导航打磨

- [x] 1.1 在侧边栏中添加会话 search/filter UI，同时保留 create/select 行为。
- [x] 1.2 为空白搜索、活动状态、任务数量和最新消息时间添加所选会话的摘要状态。
- [x] 1.3 添加或更新工作区 shell/sidebar 测试，涵盖会话搜索、空白搜索和会话创建。
- [x] 1.4 验证目标 Web 测试、`pnpm check`、`git diff --check` 以及严格的 OpenSpec 验证。

## 2. 对话模式与上下文展示

- [x] 2.1 在主工作区添加直接/分组模式控件或指示器，不改变后端路由语义。
- [x] 2.2 改进消息操作，使引用的消息和选中的制品在发送前以可见方式暂存为上下文。
- [x] 2.3 确保模式切换和上下文暂存本身不会创建任务或 TaskRun。
- [x] 2.4 为 Direct/Group 显示、引用上下文、制品上下文和清除上下文添加或更新测试。
- [x] 2.5 验证目标 Web 测试、`pnpm check`、`git diff --check` 和严格的 OpenSpec 验证。

## 3. 只读计划审查界面

- [x] 3.1 从现有任务元数据中渲染计划依据、分配角色、目标、依赖项、计划文件、验收标准和验证预期。
- [x] 3.2 当存在时，以用户可读的任务上下文形式渲染编排器兜底或验证证据。
- [x] 3.3 在 P20 阶段保持计划审查为只读状态，不提供计划变更控制。
- [x] 3.4 为计划审查元数据和兜底证据添加或更新任务 card/list 测试。
- [x] 3.5 验证目标 Web 测试、`pnpm check`、`git diff --check` 以及严格的 OpenSpec 验证。

## 4. Agent、Target、Memory 与 Evidence 总结

- [x] 4.1 改进 mission/context 面板，汇总活跃代理、选定目标、内存快照状态、最新 diff/review/preview/deploy 证据以及可用的运行时 adapter/provider 元数据。
- [x] 4.2 仅在现有响应未提供所需摘要数据时，添加最小化的 API/schema 暴露。
- [x] 4.3 为 mission/context 摘要渲染及任何 API 响应变更添加测试。
- [x] 4.4 验证定向测试、`pnpm check`、`git diff --check` 以及严格的 OpenSpec 验证。

## 5. 制品导航工作台

- [x] 5.1 使 Diff、Review、Preview 和 Deployment 制品的任务时间线发现更清晰。
- [x] 5.2 改进制品面板导航标签和空状态，同时保留预览、部署、审查和差异行为。
- [x] 5.3 确保导航变更后，制品上下文仍可传递给编辑器。
- [x] 5.4 添加或更新 artifact/task 时间线测试，用于选择制品以及将制品用作上下文。
- [x] 5.5 验证目标 Web 测试、`pnpm check`、`git diff --check` 以及严格的 OpenSpec 验证。

## 6. P20 排练与冻结评审

- [x] 6.1 运行一次本地 UI 冒烟测试或组件级演练，覆盖会话搜索、Direct/Group 显示、上下文暂存、计划审查、任务总结和制品导航。
- [x] 6.2 验证 P6-P19 基线路径在使用 `pnpm check`、`pnpm test`、`pnpm demo:api:test`、`git diff --check` 和 `openspec validate agenthub-p20-daily-agent-workspace-ux --strict` 时保持完整。
- [x] 6.3 使用 P20 状态、验证结果和剩余限制更新 `docs/change-log.md` 和 `docs/project-state.md`。
- [x] 6.4 仅在收集到验证证据后，才将 P20 任务标记为完成。
