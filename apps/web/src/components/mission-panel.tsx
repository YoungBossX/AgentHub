"use client"

import type { SessionExecutionLedger, SessionTask, WorkspaceSession } from "@/lib/api"

type WorkspaceContextCardProps = {
  ledger: SessionExecutionLedger | null
  selectedSession: WorkspaceSession | null
  tasks?: SessionTask[]
}

export function MissionPanel({ ledger, selectedSession, tasks = [] }: WorkspaceContextCardProps) {
  const latestEvidence = ledger?.latestDeploymentStatus
    ? `Deploy ${ledger.latestDeploymentStatus}`
    : ledger?.latestPreviewHealth
      ? `Preview ${ledger.latestPreviewHealth}`
      : ledger?.latestDiffArtifactId
        ? "Diff ready"
        : "等待证据"
  const frontendTarget = selectedSession?.activeFrontendTargetId ?? "未选择"
  const backendTarget = selectedSession?.activeBackendTargetId ?? "未选择"
  const memorySnapshot = selectedSession?.memorySnapshotId
    ? selectedSession.memorySnapshotId.slice(0, 8)
    : "未固定"
  const adapter = ledger?.lastSuccessfulAdapter ?? "未完成"
  const latestFiles = ledger?.latestChangedFiles.slice(0, 2).join(", ") || "无"
  const pmoSummary = summarizePmo(tasks)

  return (
    <section className="mx-auto w-full max-w-4xl rounded-lg border border-[var(--border)] bg-white px-4 py-3 shadow-sm">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <p className="text-[11px] font-bold uppercase tracking-normal text-[var(--text-muted)]">
            Workspace Context
          </p>
          <p className="mt-1 truncate text-sm font-semibold text-slate-950">
            {ledger?.currentGoal ?? "等待用户需求"}
          </p>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {(ledger?.activeAgents.length ? ledger.activeAgents : ["orchestrator"]).map(
              (role) => (
                <span
                  className="rounded-full border border-[var(--border)] bg-[var(--surface-muted)] px-2.5 py-1 font-mono text-[11px] text-slate-700"
                  key={role}
                >
                  @{role}
                </span>
              ),
            )}
          </div>
          <div className="mt-2 flex flex-wrap gap-1.5">
            <ContextPill label="前端" value={frontendTarget} />
            <ContextPill label="后端" value={backendTarget} />
            <ContextPill label="记忆" value={memorySnapshot} />
          </div>
        </div>
        <div className="grid min-w-[180px] gap-1 text-xs text-[var(--muted-foreground)]">
          <ContextRow label="最新证据" value={latestEvidence} />
          <ContextRow label="Adapter" value={adapter} />
          <ContextRow label="文件" value={latestFiles} />
          <ContextRow
            label="部署"
            value={ledger?.latestDeploymentProvider ?? ledger?.latestDeploymentStatus ?? "无"}
          />
          {tasks.length > 0 ? (
            <div className="mt-2 rounded-lg border border-[var(--border)] bg-[var(--surface-muted)] px-3 py-2">
              <p className="font-bold text-slate-700">PMO 状态</p>
              <div className="mt-1 flex flex-wrap gap-1.5">
                <ContextMetric label="ready" value={pmoSummary.ready} />
                <ContextMetric label="waiting" value={pmoSummary.waiting} />
                <ContextMetric label="blocked" value={pmoSummary.blocked} />
              </div>
              <p className="mt-2 font-semibold text-slate-700">建议</p>
              <div className="mt-1 flex flex-wrap gap-1.5">
                {pmoSummary.actions.map((action) => (
                  <span
                    className="rounded bg-white px-2 py-0.5 text-[11px] font-medium text-slate-700"
                    key={action}
                  >
                    {action}
                  </span>
                ))}
              </div>
            </div>
          ) : null}
        </div>
      </div>
    </section>
  )
}

function ContextRow({ label, value }: { label: string; value: string }) {
  return (
    <p className="flex items-center justify-between gap-3">
      <span>{label}</span>
      <span className="truncate font-medium text-slate-800">{value}</span>
    </p>
  )
}

function ContextPill({ label, value }: { label: string; value: string }) {
  return (
    <span className="inline-flex max-w-full items-center gap-1.5 rounded-full border border-[var(--border)] bg-white px-2.5 py-1 text-[11px] text-slate-600">
      <span className="shrink-0 font-semibold text-[var(--text-muted)]">{label}</span>
      <span className="truncate font-mono">{value}</span>
    </span>
  )
}

function ContextMetric({ label, value }: { label: string; value: number }) {
  return (
    <span className="rounded bg-white px-2 py-0.5 font-mono text-[11px] text-slate-700">
      {label} {value}
    </span>
  )
}

function summarizePmo(tasks: SessionTask[]) {
  let ready = 0
  let waiting = 0
  let blocked = 0
  const actions = new Set<string>()
  for (const task of tasks) {
    const scheduler = objectValue(task.planJson.scheduler)
    const schedulerState = stringValue(scheduler.state)
    const pmoDecision = objectValue(task.planJson.pmoDecision)
    if (pmoDecision.state === "pending_review") {
      actions.add("审阅计划")
    }
    if (task.status === "pending" && schedulerState !== "waiting_dependency") {
      ready += 1
      actions.add("启动可运行任务")
    } else if (
      task.status === "waiting_dependency" ||
      task.status === "waiting_target_lock" ||
      schedulerState === "waiting_dependency" ||
      schedulerState === "waiting_target_lock"
    ) {
      waiting += 1
      actions.add("检查阻塞任务")
    } else if (
      task.status === "blocked" ||
      task.status === "failed" ||
      schedulerState === "blocked" ||
      schedulerState === "retryable" ||
      schedulerState === "fallback_available"
    ) {
      blocked += 1
      actions.add("检查阻塞任务")
    }
  }
  if (actions.size === 0) {
    actions.add("等待下一步")
  }
  return { actions: Array.from(actions).slice(0, 3), blocked, ready, waiting }
}

function objectValue(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {}
}

function stringValue(value: unknown): string | undefined {
  return typeof value === "string" && value.trim() ? value.trim() : undefined
}
