"use client"

import { Rocket } from "lucide-react"

import type { DeploymentArtifact } from "@/lib/api"

type DeployCardProps = {
  deployment: DeploymentArtifact
}

export function DeployCard({ deployment }: DeployCardProps) {
  return (
    <article className="rounded-md border border-[var(--border)] bg-white p-3">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="flex items-center gap-2 text-xs font-medium uppercase tracking-normal text-[var(--muted-foreground)]">
            <Rocket aria-hidden="true" size={14} />
            Deploy artifact
          </p>
          <h3 className="mt-1 truncate text-sm font-semibold">{deployment.title}</h3>
        </div>
        <span className="rounded-sm border border-[var(--border)] px-2 py-0.5 text-xs text-[var(--muted-foreground)]">
          {deployment.status}
        </span>
      </div>

      <dl className="mt-3 grid gap-2 text-xs sm:grid-cols-3">
        <div>
          <dt className="text-[var(--muted-foreground)]">Provider</dt>
          <dd className="mt-1 font-medium">{deployment.provider}</dd>
        </div>
        <div>
          <dt className="text-[var(--muted-foreground)]">Environment</dt>
          <dd className="mt-1 font-medium">{deployment.environment}</dd>
        </div>
        <div className="min-w-0">
          <dt className="text-[var(--muted-foreground)]">Commit or ref</dt>
          <dd className="mt-1 truncate font-medium">
            {deployment.commitSha ?? "worktree"}
          </dd>
        </div>
      </dl>

      <dl className="mt-3 grid gap-2 text-xs">
        <div className="min-w-0">
          <dt className="text-[var(--muted-foreground)]">URL</dt>
          <dd className="mt-1 truncate font-medium">{deployment.url ?? "mock://pending"}</dd>
        </div>
        <div className="min-w-0">
          <dt className="text-[var(--muted-foreground)]">Deploy log</dt>
          <dd className="mt-1 truncate font-medium">
            {deployment.deployLogUri ?? "mock://logs/pending"}
          </dd>
        </div>
      </dl>
    </article>
  )
}
