import type { SessionTask } from "@/lib/api"
import { parseApiTimestamp } from "@/lib/date-format"
import { LocalTime, TimeZoneLabel } from "./local-time"
import { statusLabel } from "./task-card"

export type SessionVisualEvent = { id: string; sessionId: string; taskRunId: string; eventType: string; createdAt: string; state: string | null }

export function visualEvent(value: unknown, sessionId: string): SessionVisualEvent | null {
  if (!value || typeof value !== "object") return null
  const record = value as Record<string, unknown>
  if (!["id", "taskRunId", "eventType", "createdAt"].every((key) => typeof record[key] === "string" && (record[key] as string).length < 160)) return null
  const timestamp = record.createdAt as string
  const instant = parseApiTimestamp(timestamp)
  if (!record.id || !record.taskRunId || !record.eventType || !instant) return null
  if (!/^[\w.-]+$/.test(record.eventType as string)) return null
  const payload = record.payload && typeof record.payload === "object" ? record.payload as Record<string, unknown> : {}
  const state = typeof payload.state === "string" && ["created", "queued", "streaming", "waiting_approval", "applying_changes", "collecting_diff", "starting_preview", "completed", "failed", "interrupted", "cancelled"].includes(payload.state) ? payload.state : null
  return { id: record.id as string, sessionId, taskRunId: record.taskRunId as string, eventType: record.eventType as string, createdAt: timestamp, state }
}

const labels: Record<string, string> = { "session_queue.enqueued": "进入会话队列", "session_queue.ready": "队列任务就绪", "session_queue.running": "队列开始执行", "session_queue.advanced": "会话队列推进", "run.claimed": "执行器接管任务", "task.heartbeat": "执行心跳", "task.checkpoint.created": "保存执行前快照", queued: "任务进入队列", "task.state": "运行状态更新", "message.delta": "Agent 输出更新", "task.scope_validated": "作用域检查", "task.completion_validation": "文件输出验收", completed: "运行完成", error: "运行错误", "approval.requested": "请求审批", "approval.resolved": "审批已处理", "provider.health_checked": "执行器可用性检查" }

export function SessionEventTimeline({ events, tasks }: { events: SessionVisualEvent[]; tasks: SessionTask[] }) {
  const runs = new Map(tasks.flatMap((task) => task.taskRuns.map((run) => [run.id, task.title] as const)))
  return (
    <section
      aria-label="会话执行事件"
      className="mb-5 rounded-xl border border-[var(--border)] bg-white p-4"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-semibold">执行事件</h3>
        <TimeZoneLabel className="text-[10px] text-[var(--muted-foreground)]" />
        <span className="text-xs text-[var(--muted-foreground)]">
          {`最近 ${events.length} 条 / 最多 60 条`}
        </span>
      </div>
      {!events.length ? <p className="mt-3 text-xs leading-6 text-[var(--muted-foreground)]">尚未收到执行事件。任务启动后将在这里显示状态、审批和输出验收记录。</p> : (
        <ol className="mt-3 max-h-64 overflow-y-auto">
          {[...events].reverse().map((event) => {
            const eventTime = event.createdAt
            return (
              <li
                key={event.id}
                className="flex items-start gap-3 border-b border-[var(--border)] py-2.5 last:border-0"
              >
                <span className={`mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full ${event.eventType === "error" ? "bg-red-500" : "bg-[var(--primary)]"}`} />
                <div className="min-w-0 flex-1">
                  <p className="text-xs font-medium">
                    {labels[event.eventType] ?? "运行事件"}
                    {event.state ? ` · ${statusLabel(event.state)}` : ""}
                  </p>
                  <p className="mt-1 truncate text-[11px] text-[var(--muted-foreground)]">
                    {`${runs.get(event.taskRunId) ?? `运行 ${event.taskRunId.slice(0, 8)}`} · ${event.eventType}`}
                  </p>
                </div>
                <LocalTime
                  className="shrink-0 text-[10px] text-[var(--muted-foreground)]"
                  value={eventTime}
                />
              </li>
            )})}
        </ol>
      )}
    </section>
  )
}
