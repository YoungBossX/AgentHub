import type { SessionTask } from "@/lib/api"

type TaskCardListProps = {
  tasks: SessionTask[]
}

export function TaskCardList({ tasks }: TaskCardListProps) {
  if (tasks.length === 0) {
    return null
  }

  return (
    <div className="grid gap-2">
      {tasks.map((task, index) => (
        <article
          className="rounded-md border border-[var(--border)] bg-white p-3"
          key={task.id}
        >
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-xs font-medium uppercase tracking-normal text-[var(--muted-foreground)]">
                Step {index + 1} · {task.assignedAgentRole ?? "unassigned"}
              </p>
              <h3 className="mt-1 text-sm font-semibold">{task.title}</h3>
            </div>
            <span className="rounded-sm border border-[var(--border)] px-2 py-0.5 text-xs text-[var(--muted-foreground)]">
              {task.status}
            </span>
          </div>
          {task.dependsOnTaskIds.length > 0 ? (
            <p className="mt-2 truncate text-xs text-[var(--muted-foreground)]">
              Depends on {task.dependsOnTaskIds.join(", ")}
            </p>
          ) : null}
        </article>
      ))}
    </div>
  )
}
