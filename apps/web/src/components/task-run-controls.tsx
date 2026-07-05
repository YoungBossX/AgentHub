"use client"

import {
  Check,
  CircleAlert,
  Play,
  RotateCcw,
  Shuffle,
  Square,
  X,
} from "lucide-react"

import { Button } from "./ui/button"
import type { TaskRun } from "../lib/api"

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

type RunControlsProps = {
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
}

export function RunControls({
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
}: RunControlsProps) {
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
          开始运行
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
            模拟 Codex 失败
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
          中断
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
          重试
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
            使用兜底重试
          </Button>
        ) : null}
      </div>
    )
  }

  if (latestRun.state === "completed") {
    if (!onStartPreview) {
      return null
    }
    return (
      <div className="mt-3">
        <Button
          className="h-8 px-3 text-xs"
          disabled={busy}
          onClick={onStartPreview}
          type="button"
          variant="secondary"
        >
          <Play aria-hidden="true" size={14} />
          启动预览
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
            需要审批
          </p>
          <p className="mt-1 text-sm font-medium text-amber-950">
            {request?.requestedAction ?? "查看请求动作"}
          </p>
        </div>
        <span className="rounded-sm border border-amber-300 bg-white px-2 py-0.5 text-xs text-amber-800">
          {request?.approvalType ?? "审批"}
        </span>
      </div>
      <p className="mt-2 text-sm leading-6 text-amber-950">
        {request?.reason ?? "这次运行正在等待用户确认，确认后才能继续。"}
      </p>
      {request?.command || request?.path ? (
        <dl className="mt-2 grid gap-1 text-xs text-amber-900">
          {request.command ? (
            <div className="grid gap-1">
              <dt className="font-semibold">命令</dt>
              <dd className="truncate font-mono">{request.command}</dd>
            </div>
          ) : null}
          {request.path ? (
            <div className="grid gap-1">
              <dt className="font-semibold">路径</dt>
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
          批准
        </Button>
        <Button
          className="h-8 px-3 text-xs"
          disabled={busy || !onDenyRun}
          onClick={onDenyRun}
          type="button"
          variant="secondary"
        >
          <X aria-hidden="true" size={14} />
          拒绝
        </Button>
      </div>
    </div>
  )
}
