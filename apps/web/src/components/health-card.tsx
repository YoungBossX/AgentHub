import { Server } from "lucide-react"

import type { BackendHealth } from "@/lib/api"

type HealthCardProps = {
  backendUrl: string
  health: BackendHealth
}

export function HealthCard({ backendUrl, health }: HealthCardProps) {
  const isReady = health.status === "ok" && health.database === "ready"
  const serviceStatus = health.status === "ok" ? "正常" : health.status
  const databaseStatus = health.database === "ready" ? "就绪" : health.database

  return (
    <aside
      className="inline-flex items-center gap-2 rounded-full border border-[var(--border)] bg-white px-3 py-2 shadow-sm"
      title={`${backendUrl} · API ${health.status} · SQLite ${health.database}`}
    >
      <span
        className={
          isReady
            ? "h-2.5 w-2.5 rounded-full bg-emerald-500"
            : "h-2.5 w-2.5 rounded-full bg-amber-500"
        }
      />
      <Server aria-hidden="true" className="text-slate-500" size={14} />
      <span className="text-xs font-semibold text-slate-950">后端</span>
      <span className="hidden text-xs text-[var(--muted-foreground)] xl:inline">
        {serviceStatus} / {databaseStatus}
      </span>
    </aside>
  )
}
