"use client"

import type { SessionExecutionLedger } from "@/lib/api"

type WorkspaceContextCardProps = {
  ledger: SessionExecutionLedger | null
}

export function MissionPanel({ ledger }: WorkspaceContextCardProps) {
  const latestEvidence = ledger?.latestDeploymentStatus
    ? `Mock deploy ${ledger.latestDeploymentStatus}`
    : ledger?.latestPreviewHealth
      ? `Preview ${ledger.latestPreviewHealth}`
      : ledger?.latestDiffArtifactId
        ? "Diff ready"
        : "等待证据"

  return (
    <section className="mx-auto w-full max-w-3xl rounded-lg border border-[var(--border)] bg-white px-4 py-3 shadow-sm">
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
                  className="rounded border border-[var(--border)] bg-[var(--surface-muted)] px-2 py-1 font-mono text-[11px] text-slate-700"
                  key={role}
                >
                  @{role}
                </span>
              ),
            )}
          </div>
        </div>
        <div className="grid min-w-[180px] gap-1 text-xs text-[var(--muted-foreground)]">
          <ContextRow label="Latest" value={latestEvidence} />
          <ContextRow
            label="Adapter"
            value={ledger?.lastSuccessfulAdapter ?? "未完成"}
          />
          <ContextRow
            label="Files"
            value={ledger?.latestChangedFiles.slice(0, 2).join(", ") || "无"}
          />
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
