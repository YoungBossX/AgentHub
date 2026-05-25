"use client"

import { Rocket } from "lucide-react"

import type { DeploymentArtifact } from "@/lib/api"

type DeployCardProps = {
  deployment: DeploymentArtifact
}

function statusLabel(status: string) {
  const labels: Record<string, string> = {
    pending: "等待中",
    ready: "就绪",
    failed: "失败",
  }
  return labels[status] ?? status
}

function deploymentTitle(title: string) {
  return title === "Mock deploy" ? "模拟部署" : title
}

export function DeployCard({ deployment }: DeployCardProps) {
  return (
    <article className="rounded-md border border-[var(--border)] bg-white p-3">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="flex items-center gap-2 text-xs font-medium uppercase tracking-normal text-[var(--muted-foreground)]">
            <Rocket aria-hidden="true" size={14} />
            部署产物
          </p>
          <h3 className="mt-1 truncate text-sm font-semibold">
            {deploymentTitle(deployment.title)}
          </h3>
        </div>
        <span className="rounded-sm border border-[var(--border)] px-2 py-0.5 text-xs text-[var(--muted-foreground)]">
          {statusLabel(deployment.status)}
        </span>
      </div>

      <dl className="mt-3 grid gap-2 text-xs sm:grid-cols-3">
        <div>
          <dt className="text-[var(--muted-foreground)]">提供方</dt>
          <dd className="mt-1 font-medium">
            {deployment.providerType ?? deployment.provider}
          </dd>
        </div>
        <div>
          <dt className="text-[var(--muted-foreground)]">环境</dt>
          <dd className="mt-1 font-medium">{deployment.environment}</dd>
        </div>
        <div className="min-w-0">
          <dt className="text-[var(--muted-foreground)]">提交或引用</dt>
          <dd className="mt-1 truncate font-medium">
            {deployment.commitSha ?? "worktree"}
          </dd>
        </div>
        {deployment.targetId ? (
          <div className="min-w-0">
            <dt className="text-[var(--muted-foreground)]">目标</dt>
            <dd className="mt-1 truncate font-medium">{deployment.targetId}</dd>
          </div>
        ) : null}
      </dl>

      <dl className="mt-3 grid gap-2 text-xs">
        <div className="min-w-0">
          <dt className="text-[var(--muted-foreground)]">URL</dt>
          <dd className="mt-1 truncate font-medium">{deployment.url ?? "mock://pending"}</dd>
        </div>
        <div className="min-w-0">
          <dt className="text-[var(--muted-foreground)]">部署日志</dt>
          <dd className="mt-1 truncate font-medium">
            {deployment.deployLogUri ?? "mock://logs/pending"}
          </dd>
        </div>
        {deployment.sourceDiffArtifactId ? (
          <div className="min-w-0">
            <dt className="text-[var(--muted-foreground)]">Diff</dt>
            <dd className="mt-1 truncate font-medium">{deployment.sourceDiffArtifactId}</dd>
          </div>
        ) : null}
        {deployment.sourceReviewArtifactId ? (
          <div className="min-w-0">
            <dt className="text-[var(--muted-foreground)]">Review</dt>
            <dd className="mt-1 truncate font-medium">
              {deployment.sourceReviewArtifactId}
            </dd>
          </div>
        ) : null}
      </dl>

      {deployment.statusHistory.length > 0 ? (
        <ol className="mt-3 grid gap-1 text-xs text-[var(--muted-foreground)]">
          {deployment.statusHistory.map((item, index) => (
            <li key={`${item.status}-${index}`} className="flex gap-2">
              <span className="font-medium text-[var(--foreground)]">{item.status}</span>
              <span className="truncate">{item.message ?? item.status}</span>
            </li>
          ))}
        </ol>
      ) : null}

      {deployment.logs.length > 0 ? (
        <pre className="mt-3 max-h-28 overflow-auto rounded-sm bg-[var(--muted)] p-2 text-xs leading-relaxed text-[var(--foreground)]">
          {deployment.logs.join("\n")}
        </pre>
      ) : null}
    </article>
  )
}
