"use client"

import { Play, RotateCcw, Shuffle, Square } from "lucide-react"
import { Fragment, useEffect, useMemo, useState } from "react"

import { DiffCard } from "./diff-card"
import { Button } from "./ui/button"
import { listTaskRunDiffs, type DiffArtifact, type SessionTask, type TaskRun } from "../lib/api"

type TaskCardListProps = {
  tasks: SessionTask[]
  artifactRefreshKey?: number
  backendUrl?: string
  busy?: boolean
  fetcher?: typeof fetch
  onCreateRun?: (taskId: string) => void
  onInterruptRun?: (taskRunId: string) => void
  onRetryRun?: (taskRunId: string) => void
  onRetryWithFallback?: (taskRunId: string) => void
}

const activeRunStates = new Set([
  "created",
  "queued",
  "streaming",
  "waiting_approval",
  "applying_changes",
  "collecting_diff",
  "starting_preview",
])
const retryableRunStates = new Set(["failed", "interrupted"])

export function TaskCardList({
  tasks,
  artifactRefreshKey = 0,
  backendUrl,
  busy = false,
  fetcher = fetch,
  onCreateRun,
  onInterruptRun,
  onRetryRun,
  onRetryWithFallback,
}: TaskCardListProps) {
  const [diffsByRunId, setDiffsByRunId] = useState<Record<string, DiffArtifact[]>>({})
  const taskRunIds = useMemo(
    () => tasks.flatMap((task) => task.taskRuns.map((taskRun) => taskRun.id)),
    [tasks],
  )

  useEffect(() => {
    if (!backendUrl || taskRunIds.length === 0) {
      return
    }

    let cancelled = false
    Promise.all(
      taskRunIds.map(async (taskRunId) => {
        const diffs = await listTaskRunDiffs(backendUrl, taskRunId, fetcher)
        return [taskRunId, diffs] as const
      }),
    ).then((entries) => {
      if (!cancelled) {
        setDiffsByRunId(Object.fromEntries(entries))
      }
    })

    return () => {
      cancelled = true
    }
  }, [artifactRefreshKey, backendUrl, fetcher, taskRunIds])

  if (tasks.length === 0) {
    return null
  }

  return (
    <div className="grid gap-2">
      {tasks.map((task, index) => {
        const latestRun = task.taskRuns[task.taskRuns.length - 1] ?? null
        const taskDiffs = task.taskRuns.flatMap((taskRun) => diffsByRunId[taskRun.id] ?? [])
        return (
          <Fragment key={task.id}>
            <article className="rounded-md border border-[var(--border)] bg-white p-3">
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
              {task.taskRuns.length > 0 ? (
                <div className="mt-3 grid gap-1 rounded-md bg-slate-50 p-2">
                  {task.taskRuns.map((taskRun, runIndex) => (
                    <RunSummary key={taskRun.id} run={taskRun} runIndex={runIndex} />
                  ))}
                </div>
              ) : null}
              <RunControls
                busy={busy}
                latestRun={latestRun}
                onCreateRun={onCreateRun ? () => onCreateRun(task.id) : undefined}
                onInterruptRun={
                  latestRun && onInterruptRun ? () => onInterruptRun(latestRun.id) : undefined
                }
                onRetryRun={latestRun && onRetryRun ? () => onRetryRun(latestRun.id) : undefined}
                onRetryWithFallback={
                  latestRun && onRetryWithFallback
                    ? () => onRetryWithFallback(latestRun.id)
                    : undefined
                }
              />
            </article>
            {taskDiffs.map((diff) => (
              <DiffCard diff={diff} key={diff.id} />
            ))}
          </Fragment>
        )
      })}
    </div>
  )
}

function RunSummary({ run, runIndex }: { run: TaskRun; runIndex: number }) {
  return (
    <div className="flex items-center justify-between gap-2 text-xs text-[var(--muted-foreground)]">
      <span>
        Run {runIndex + 1} · {run.adapterType} · {run.state}
      </span>
      {run.errorCode ? <span className="truncate">{run.errorCode}</span> : null}
    </div>
  )
}

function RunControls({
  busy,
  latestRun,
  onCreateRun,
  onInterruptRun,
  onRetryRun,
  onRetryWithFallback,
}: {
  busy: boolean
  latestRun: TaskRun | null
  onCreateRun?: () => void
  onInterruptRun?: () => void
  onRetryRun?: () => void
  onRetryWithFallback?: () => void
}) {
  if (!latestRun) {
    return (
      <div className="mt-3">
        <Button
          className="h-8 px-3 text-xs"
          disabled={busy || !onCreateRun}
          onClick={onCreateRun}
          type="button"
        >
          <Play aria-hidden="true" size={14} />
          Start run
        </Button>
      </div>
    )
  }

  if (activeRunStates.has(latestRun.state)) {
    return (
      <div className="mt-3">
        <Button
          disabled={busy || !onInterruptRun}
          className="h-8 px-3 text-xs"
          onClick={onInterruptRun}
          type="button"
          variant="secondary"
        >
          <Square aria-hidden="true" size={14} />
          Interrupt
        </Button>
      </div>
    )
  }

  if (retryableRunStates.has(latestRun.state)) {
    return (
      <div className="mt-3 flex flex-wrap gap-2">
        <Button
          className="h-8 px-3 text-xs"
          disabled={busy || !onRetryRun}
          onClick={onRetryRun}
          type="button"
        >
          <RotateCcw aria-hidden="true" size={14} />
          Retry
        </Button>
        {latestRun.adapterType === "codex" ? (
          <Button
            disabled={busy || !onRetryWithFallback}
            className="h-8 px-3 text-xs"
            onClick={onRetryWithFallback}
            type="button"
            variant="secondary"
          >
            <Shuffle aria-hidden="true" size={14} />
            Retry with fallback
          </Button>
        ) : null}
      </div>
    )
  }

  return null
}
