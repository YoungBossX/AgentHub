"use client"

import { ExternalLink, Monitor, RefreshCw, Rocket, Square, X } from "lucide-react"

import { Button } from "@/components/ui/button"
import type { PreviewArtifact } from "@/lib/api"
import { formatCompactDateTime } from "@/lib/date-format"

type PreviewCardProps = {
  busy?: boolean
  onCreateDeploy?: (previewId: string) => void
  onOpen?: (preview: PreviewArtifact) => void
  onRefresh?: (taskRunId: string) => void
  onStop?: (previewId: string) => void
  preview: PreviewArtifact
}

type PreviewPanelProps = {
  frameKey: number
  onClose?: () => void
  onRefresh?: (taskRunId: string) => void
  preview: PreviewArtifact | null
}

function formatPreviewTime(value: string | null) {
  if (!value) {
    return "Last checked: pending"
  }

  return `Last checked: ${formatCompactDateTime(value)}`
}

function previewHost(url: string) {
  try {
    return new URL(url).host
  } catch {
    return url
  }
}

export function PreviewCard({
  busy = false,
  onCreateDeploy,
  onOpen,
  onRefresh,
  onStop,
  preview,
}: PreviewCardProps) {
  return (
    <article className="rounded-md border border-[var(--border)] bg-white p-3">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="flex items-center gap-2 text-xs font-medium uppercase tracking-normal text-[var(--muted-foreground)]">
            <Monitor aria-hidden="true" size={14} />
            Preview
          </p>
          <h3 className="mt-1 truncate text-sm font-semibold">{preview.title}</h3>
          <p className="mt-1 truncate text-xs text-[var(--muted-foreground)]">
            {preview.url}
          </p>
        </div>
        <span className="rounded-sm border border-[var(--border)] px-2 py-0.5 text-xs text-[var(--muted-foreground)]">
          {preview.healthStatus}
        </span>
      </div>

      <dl className="mt-3 grid gap-2 text-xs sm:grid-cols-3">
        <div>
          <dt className="text-[var(--muted-foreground)]">Status</dt>
          <dd className="mt-1 font-medium">{preview.status}</dd>
        </div>
        <div>
          <dt className="text-[var(--muted-foreground)]">Port</dt>
          <dd className="mt-1 font-medium">{preview.port}</dd>
        </div>
        <div className="min-w-0">
          <dt className="text-[var(--muted-foreground)]">Checked</dt>
          <dd className="mt-1 truncate font-medium">
            {formatPreviewTime(preview.lastCheckedAt)}
          </dd>
        </div>
      </dl>

      {preview.statusReason ? (
        <p className="mt-3 rounded-md bg-amber-50 p-2 text-xs text-amber-900">
          {preview.statusReason}
        </p>
      ) : null}

      <div className="mt-3 flex flex-wrap gap-2">
        <Button
          className="h-8 px-3 text-xs"
          disabled={busy || !onOpen}
          onClick={() => onOpen?.(preview)}
          type="button"
        >
          <ExternalLink aria-hidden="true" size={14} />
          Open preview
        </Button>
        <Button
          className="h-8 px-3 text-xs"
          disabled={busy || !onRefresh}
          onClick={() => onRefresh?.(preview.taskRunId)}
          type="button"
          variant="secondary"
        >
          <RefreshCw aria-hidden="true" size={14} />
          Refresh preview
        </Button>
        <Button
          className="h-8 px-3 text-xs"
          disabled={busy || !onCreateDeploy || preview.healthStatus !== "healthy"}
          onClick={() => onCreateDeploy?.(preview.id)}
          type="button"
          variant="secondary"
        >
          <Rocket aria-hidden="true" size={14} />
          Create deploy card
        </Button>
        <Button
          className="h-8 px-3 text-xs"
          disabled={busy || !onStop}
          onClick={() => onStop?.(preview.id)}
          type="button"
          variant="secondary"
        >
          <Square aria-hidden="true" size={14} />
          Stop preview
        </Button>
      </div>
    </article>
  )
}

export function PreviewPanel({
  frameKey,
  onClose,
  onRefresh,
  preview,
}: PreviewPanelProps) {
  return (
    <aside className="flex min-h-[560px] flex-col border-t border-[var(--border)] bg-slate-50 xl:border-l xl:border-t-0">
      <header className="flex items-start justify-between gap-3 border-b border-[var(--border)] bg-white p-4">
        <div className="min-w-0">
          <p className="text-xs font-medium uppercase tracking-normal text-[var(--muted-foreground)]">
            Preview panel
          </p>
          <h2 className="mt-1 truncate text-base font-semibold">
            {preview ? previewHost(preview.url) : "No preview selected"}
          </h2>
          {preview ? (
            <p className="mt-1 text-xs text-[var(--muted-foreground)]">
              {preview.healthStatus} · port {preview.port}
            </p>
          ) : null}
        </div>
        <div className="flex gap-2">
          <Button
            aria-label="Refresh panel"
            className="h-8 w-8 p-0"
            disabled={!preview || !onRefresh}
            onClick={() => preview && onRefresh?.(preview.taskRunId)}
            type="button"
            variant="secondary"
          >
            <RefreshCw aria-hidden="true" size={14} />
          </Button>
          <Button
            aria-label="Close preview"
            className="h-8 w-8 p-0"
            disabled={!preview || !onClose}
            onClick={onClose}
            type="button"
            variant="secondary"
          >
            <X aria-hidden="true" size={14} />
          </Button>
        </div>
      </header>

      <div className="flex flex-1 min-h-0 p-3">
        {preview ? (
          <iframe
            className="min-h-[480px] w-full rounded-md border border-[var(--border)] bg-white"
            key={`${preview.id}-${frameKey}`}
            src={preview.url}
            title="Vite React preview"
          />
        ) : (
          <div className="flex min-h-[480px] w-full items-center justify-center rounded-md border border-dashed border-[var(--border)] bg-white p-5 text-center text-sm text-[var(--muted-foreground)]">
            Start or open a task run preview to inspect the Vite React demo.
          </div>
        )}
      </div>
    </aside>
  )
}
