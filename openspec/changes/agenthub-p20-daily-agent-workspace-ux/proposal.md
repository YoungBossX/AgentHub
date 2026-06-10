## 为什么

AgentHub 现在可以通过真实编码智能体进行规划、路由、执行、验证、预览、本地部署以及记录证据，但主工作区仍感觉像一个内部演示控制台。需要 P20 阶段将现有平台核心转变为日常使用的智能体工作区，使用户无需了解后端实现细节即可管理会话、上下文、任务和证据。

## 变更内容

- 将主工作区升级为更清洁的日常聊天工作台：
  - 更清晰的会话列表，带有 search/filter 操作提示；
  - 明确的直接/群组对话模式指示器；
  - 针对活跃目标、内存快照、运行时配置和最新证据的紧凑状态摘要；
  - 减少主屏幕中仅用于演示的语言。
- 添加一流的消息操作和上下文管理：
  - 保留复制/引用功能；
  - 添加发送前可见的消息到上下文行为；
  - 在编辑器中显示选定的 artifact/message 上下文；
  - 保持普通聊天不创建编码任务。
- 改进聊天工作流中的任务计划审查：
  - 显示规划器理由、分配角色、目标、依赖项、计划文件和验收标准；
  - 在任务执行前公开只读的计划审查元数据；
  - 通过现有调度器和计划验证器保持任务执行。
- 提高代理工作台可见性：
  - 在上下文中显示活跃的 coding/review 代理和 provider/runtime 元数据；
  - 无需检查任务追踪即可显示兜底/重试/审批状态；
  - 保留现有代理 contacts/settings 页面。
- 改进制品和证据导航：
  - 使差异、审查、预览和部署制品更容易从对话和任务时间线中发现；
  - 保留内联预览和部署卡片；
  - 为后续制品 editing/version 历史准备 UI 边界，但不在 P20 中实现完整编辑器。
- 为日常工作区交互路径添加聚焦测试和冒烟覆盖。

## 能力

### 新能力

- `daily-agent-workspace`：定义会话的日常使用工作区用户体验、对话模式、消息上下文、任务计划审查、agent/evidence 状态以及制品导航。

### 修改后的能力

- `external-workspace`：运行时工作区设置应保持可从日常工作区访问，但详细的 target/provider 配置应位于主聊天页面之外。
- `planner-routing-hardening`：工作区 UI 应在用户可读的 task/mission 上下文中显示规划器结果和兜底证据，而不改变路由语义。

## 影响

- 影响 `apps/web/src/components/workspace-shell.tsx`、
  `apps/web/src/components/session-sidebar.tsx`、
  `apps/web/src/components/chat-thread.tsx`、
  `apps/web/src/components/message-composer.tsx`、
  `apps/web/src/components/mission-panel.tsx`、
  `apps/web/src/components/task-card*.tsx` 以及制品面板组件。
- 如果现有元数据对 UI 暴露不足，可能需要在 `apps/api/app/schemas.py`、
  `apps/api/app/mission_trace.py` 或账本响应中添加小的响应字段补充。
- 新增前端组件测试，并在响应元数据变更处添加针对性 API 测试。
- 更新 `docs/change-log.md` 和 `docs/project-state.md`。
- 不包含任意自定义代理、生产部署、新编码适配器、多用户协作、提供商市场或完整制品编辑功能。
