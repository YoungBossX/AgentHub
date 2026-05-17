"use client"

import { Check, CircleAlert, Play, RotateCcw, Shuffle, Square, X } from "lucide-react"
import { Fragment, useEffect, useMemo, useState } from "react"

import { DeployCard } from "./deploy-card"
import { DiffCard } from "./diff-card"
import { PreviewCard } from "./preview-card"
import { Button } from "./ui/button"
import {
  listTaskRunDeployments,
  listTaskRunDiffs,
  listTaskRunPreviews,
  type DeploymentArtifact,
  type DiffArtifact,
  type PreviewArtifact,
  type SessionTask,
  type TaskRun,
} from "../lib/api"

type TaskCardListProps = {
  tasks: SessionTask[]
  artifactRefreshKey?: number
  backendUrl?: string
  busy?: boolean
  fetcher?: typeof fetch
  onApproveRun?: (taskRunId: string) => void
  onCreateDeploy?: (previewId: string) => void
  onCreateRun?: (taskId: string) => void
  onDenyRun?: (taskRunId: string) => void
  onForceCodexFailure?: (taskId: string) => void
  onInterruptRun?: (taskRunId: string) => void
  onOpenPreview?: (preview: PreviewArtifact) => void
  onRefreshPreviews?: (taskRunId: string) => void
  onRetryRun?: (taskRunId: string) => void
  onRetryWithFallback?: (taskRunId: string) => void
  onStartPreview?: (taskRunId: string) => void
  onStopPreview?: (previewId: string) => void
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
  onApproveRun,
  onCreateDeploy,
  onCreateRun,
  onDenyRun,
  onForceCodexFailure,
  onInterruptRun,
  onOpenPreview,
  onRefreshPreviews,
  onRetryRun,
  onRetryWithFallback,
  onStartPreview,
  onStopPreview,
}: TaskCardListProps) {
  const [deploymentsByRunId, setDeploymentsByRunId] = useState<
    Record<string, DeploymentArtifact[]>
  >({})
  const [diffsByRunId, setDiffsByRunId] = useState<Record<string, DiffArtifact[]>>({})
  const [previewsByRunId, setPreviewsByRunId] = useState<Record<string, PreviewArtifact[]>>({})
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

  useEffect(() => {
    if (!backendUrl || taskRunIds.length === 0) {
      return
    }

    let cancelled = false
    Promise.all(
      taskRunIds.map(async (taskRunId) => {
        const deployments = await listTaskRunDeployments(backendUrl, taskRunId, fetcher)
        return [taskRunId, deployments] as const
      }),
    ).then((entries) => {
      if (!cancelled) {
        setDeploymentsByRunId(Object.fromEntries(entries))
      }
    })

    return () => {
      cancelled = true
    }
  }, [artifactRefreshKey, backendUrl, fetcher, taskRunIds])

  useEffect(() => {
    if (!backendUrl || taskRunIds.length === 0) {
      return
    }

    let cancelled = false
    Promise.all(
      taskRunIds.map(async (taskRunId) => {
        const previews = await listTaskRunPreviews(backendUrl, taskRunId, fetcher)
        return [taskRunId, previews] as const
      }),
    ).then((entries) => {
      if (!cancelled) {
        setPreviewsByRunId(Object.fromEntries(entries))
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
        const taskDeployments = task.taskRuns.flatMap(
          (taskRun) => deploymentsByRunId[taskRun.id] ?? [],
        )
        const taskPreviews = task.taskRuns.flatMap(
          (taskRun) => previewsByRunId[taskRun.id] ?? [],
        )
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
                onApproveRun={
                  latestRun && onApproveRun ? () => onApproveRun(latestRun.id) : undefined
                }
                onCreateRun={onCreateRun ? () => onCreateRun(task.id) : undefined}
                onDenyRun={
                  latestRun && onDenyRun ? () => onDenyRun(latestRun.id) : undefined
                }
                onForceCodexFailure={
                  !latestRun && onForceCodexFailure
                    ? () => onForceCodexFailure(task.id)
                    : undefined
                }
                onInterruptRun={
                  latestRun && onInterruptRun ? () => onInterruptRun(latestRun.id) : undefined
                }
                onRetryRun={latestRun && onRetryRun ? () => onRetryRun(latestRun.id) : undefined}
                onRetryWithFallback={
                  latestRun && onRetryWithFallback
                    ? () => onRetryWithFallback(latestRun.id)
                    : undefined
                }
                onStartPreview={
                  latestRun && onStartPreview ? () => onStartPreview(latestRun.id) : undefined
                }
              />
            </article>
            {taskDiffs.map((diff) => (
              <DiffCard diff={diff} key={diff.id} />
            ))}
            {taskPreviews.map((preview) => (
              <PreviewCard
                busy={busy}
                key={preview.id}
                onCreateDeploy={onCreateDeploy}
                onOpen={onOpenPreview}
                onRefresh={onRefreshPreviews}
                onStop={onStopPreview}
                preview={preview}
              />
            ))}
            {taskDeployments.map((deployment) => (
              <DeployCard deployment={deployment} key={deployment.id} />
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
  onApproveRun,
  onCreateRun,
  onDenyRun,
  onForceCodexFailure,
  onInterruptRun,
  onRetryRun,
  onRetryWithFallback,
  onStartPreview,
}: {
  busy: boolean
  latestRun: TaskRun | null
  onApproveRun?: () => void
  onCreateRun?: () => void
  onDenyRun?: () => void
  onForceCodexFailure?: () => void
  onInterruptRun?: () => void
  onRetryRun?: () => void
  onRetryWithFallback?: () => void
  onStartPreview?: () => void
}) {
  if (!latestRun) {
    return (
      <div className="mt-3 flex flex-wrap gap-2">
        <Button
          className="h-8 px-3 text-xs"
          disabled={busy || !onCreateRun}
          onClick={onCreateRun}
          type="button"
        >
          <Play aria-hidden="true" size={14} />
          Start run
        </Button>
        {onForceCodexFailure ? (
          <Button
            className="h-8 px-3 text-xs"
            disabled={busy}
            onClick={onForceCodexFailure}
            type="button"
            variant="secondary"
          >
            <CircleAlert aria-hidden="true" size={14} />
            Force Codex failure
          </Button>
        ) : null}
      </div>
    )
  }

  if (latestRun.state === "waiting_approval") {
    return (
      <ApprovalRequestCard
        busy={busy}
        onApproveRun={onApproveRun}
        onDenyRun={onDenyRun}
        run={latestRun}
      />
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
            Retry with ScriptedMockAdapter
          </Button>
        ) : null}
      </div>
    )
  }

  if (latestRun.state === "completed") {
    return (
      <div className="mt-3">
        <Button
          className="h-8 px-3 text-xs"
          disabled={busy || !onStartPreview}
          onClick={onStartPreview}
          type="button"
          variant="secondary"
        >
          <Play aria-hidden="true" size={14} />
          Start preview
        </Button>
      </div>
    )
  }

  return null
}

function ApprovalRequestCard({
  busy,
  onApproveRun,
  onDenyRun,
  run,
}: {
  busy: boolean
  onApproveRun?: () => void
  onDenyRun?: () => void
  run: TaskRun
}) {
  const request = run.approvalRequest
  return (
    <div className="mt-3 rounded-md border border-amber-300 bg-amber-50 p-3">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-normal text-amber-800">
            Approval required
          </p>
          <p className="mt-1 text-sm font-medium text-amber-950">
            {request?.requestedAction ?? "Review requested action"}
          </p>
        </div>
        <span className="rounded-sm border border-amber-300 bg-white px-2 py-0.5 text-xs text-amber-800">
          {request?.approvalType ?? "approval"}
        </span>
      </div>
      <p className="mt-2 text-sm leading-6 text-amber-950">
        {request?.reason ?? "This run is waiting for a user decision before it can continue."}
      </p>
      {request?.command || request?.path ? (
        <dl className="mt-2 grid gap-1 text-xs text-amber-900">
          {request.command ? (
            <div className="grid gap-1">
              <dt className="font-semibold">Command</dt>
              <dd className="truncate font-mono">{request.command}</dd>
            </div>
          ) : null}
          {request.path ? (
            <div className="grid gap-1">
              <dt className="font-semibold">Path</dt>
              <dd className="truncate font-mono">{request.path}</dd>
            </div>
          ) : null}
        </dl>
      ) : null}
      <div className="mt-3 flex flex-wrap gap-2">
        <Button
          className="h-8 px-3 text-xs"
          disabled={busy || !onApproveRun}
          onClick={onApproveRun}
          type="button"
        >
          <Check aria-hidden="true" size={14} />
          Approve
        </Button>
        <Button
          className="h-8 px-3 text-xs"
          disabled={busy || !onDenyRun}
          onClick={onDenyRun}
          type="button"
          variant="secondary"
        >
          <X aria-hidden="true" size={14} />
          Deny
        </Button>
      </div>
    </div>
  )
}
