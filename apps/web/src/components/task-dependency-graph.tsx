import { useId } from "react"
import type { AgentContact, SessionTask } from "@/lib/api"
import { dependencyLayout, latestTaskState, activeStates } from "./session-workbench-state"
import { statusLabel } from "./task-card"

export function TaskDependencyGraph({ tasks, agents = [] }: { tasks: SessionTask[]; agents?: AgentContact[] }) {
  const marker = `dependency-${useId().replaceAll(":", "")}`
  const graph = dependencyLayout(tasks)
  const byId = new Map(graph.nodes.map((node) => [node.task.id, node]))
  return (
    <div className="mt-4">
      <div
        className="overflow-x-auto rounded-xl border border-[var(--border)] bg-[var(--surface-muted)] p-2"
        tabIndex={0}
        aria-label="滚动查看任务依赖图"
      >
        <svg
          role="img"
          aria-label="任务依赖关系图"
          width={graph.width}
          height={graph.height}
          className="mx-auto block"
        >
          <title>任务依赖关系图</title>
          <desc>箭头表示任务先后依赖，不表示 Agent 已同时执行。节点状态来自最新运行记录。</desc>
          <defs>
            <marker
              id={marker}
              markerWidth="7"
              markerHeight="7"
              refX="6"
              refY="3.5"
              orient="auto"
            >
              <path
                d="M0,0 L7,3.5 L0,7"
                fill="#a6b0c0"
              />
            </marker>
          </defs>
          {graph.nodes.flatMap((node) => node.task.dependsOnTaskIds.map((id) => {
            const from = byId.get(id)
            if (!from) return null
            const start = from.x + 216, end = node.x, middle = (start + end) / 2
            return <path
              key={`${id}-${node.task.id}`}
              data-dependency={`${id}:${node.task.id}`}
              d={`M${start},${from.y + 40} C${middle},${from.y + 40} ${middle},${node.y + 40} ${end - 3},${node.y + 40}`}
              fill="none"
              stroke="#a6b0c0"
              strokeWidth="1.5"
              markerEnd={`url(#${marker})`}
            />
          }))}
          {graph.nodes.map(({ task, x, y }) => {
            const state = latestTaskState(task)
            const color = state === "completed" ? "var(--status-success)" : ["failed", "blocked", "interrupted"].includes(state) ? "var(--status-danger)" : activeStates.has(state) ? "var(--primary)" : "var(--text-muted)"
            return (
              <g
                key={task.id}
                transform={`translate(${x},${y})`}
              >
                <title>
                  {task.title}
                  {' '}
                  ·
                  {' '}
                  {statusLabel(state)}
                </title>
                <rect
                  width="216"
                  height="80"
                  rx="10"
                  fill="var(--surface)"
                  stroke="var(--border)"
                />
                <rect
                  width="3"
                  height="48"
                  x="0"
                  y="16"
                  rx="1.5"
                  fill={color}
                />
                <text
                  x="16"
                  y="25"
                  fontSize="11"
                  fill="var(--muted-foreground)"
                >
                  {(agents.find((agent) => agent.id === task.assignedAgentId) ?? agents.find((agent) => agent.role === task.assignedAgentRole))?.displayName.slice(0, 28) ?? task.assignedAgentRole ?? "unassigned"}
                </text>
                <text
                  x="16"
                  y="46"
                  fontSize="12"
                  fontWeight="600"
                  fill="var(--foreground)"
                >
                  {task.title.length > 18 ? `${task.title.slice(0, 18)}…` : task.title}
                </text>
                <circle
                  cx="19"
                  cy="64"
                  r="3"
                  fill={color}
                />
                <text
                  x="28"
                  y="68"
                  fontSize="10"
                  fill={color}
                >
                  {statusLabel(state)}
                </text>
              </g>
            )
          })}
        </svg>
      </div>
      {graph.cyclic || graph.missing ? <p className="mt-2 text-xs text-amber-700">{graph.cyclic ? "依赖记录包含环，无法确认完整执行顺序。" : "部分上游任务不在当前列表中，图中仅显示已加载的依赖。"}</p> : null}
    </div>
  )
}
