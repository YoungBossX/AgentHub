import { Server } from "lucide-react"

import type { BackendHealth } from "@/lib/api"

type HealthCardProps = {
  backendUrl: string
  health: BackendHealth
}

export function HealthCard({ backendUrl, health }: HealthCardProps) {
  const isReady = health.status === "ok" && health.database === "ready"

  return (
    <aside className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-5">
      <div className="flex items-center gap-3">
        <span className="flex h-10 w-10 items-center justify-center rounded-md bg-blue-600 text-white">
          <Server aria-hidden="true" size={20} />
        </span>
        <div>
          <h2 className="text-lg font-semibold">Backend health</h2>
          <p className="text-sm text-[var(--muted-foreground)]">{backendUrl}</p>
        </div>
      </div>

      <dl className="mt-5 grid gap-3 text-sm">
        <div className="flex items-center justify-between border-t border-[var(--border)] pt-3">
          <dt className="text-[var(--muted-foreground)]">Service</dt>
          <dd className="font-medium">{health.service}</dd>
        </div>
        <div className="flex items-center justify-between border-t border-[var(--border)] pt-3">
          <dt className="text-[var(--muted-foreground)]">API</dt>
          <dd className="font-medium">{health.status}</dd>
        </div>
        <div className="flex items-center justify-between border-t border-[var(--border)] pt-3">
          <dt className="text-[var(--muted-foreground)]">SQLite</dt>
          <dd className="font-medium">{health.database}</dd>
        </div>
      </dl>

      <p className="mt-5 rounded-md border border-[var(--border)] bg-slate-50 p-3 text-sm text-[var(--muted-foreground)]">
        {isReady
          ? "FastAPI and SQLModel are reachable from the Next.js app."
          : "Start the API on port 8000, then refresh this page."}
      </p>
    </aside>
  )
}
