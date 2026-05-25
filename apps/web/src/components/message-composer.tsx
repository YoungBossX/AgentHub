"use client"

import { type FormEvent } from "react"
import { MessageSquare, Send } from "lucide-react"

import { Button } from "@/components/ui/button"
import type { ArtifactPanelItem } from "@/components/preview-card"

type MessageComposerProps = {
  contextArtifact: ArtifactPanelItem | null
  draft: string
  isPending: boolean
  onClearContext: () => void
  onDraftChange: (value: string) => void
  onSubmit: (event: FormEvent<HTMLFormElement>) => void
}

export function MessageComposer({
  contextArtifact,
  draft,
  isPending,
  onClearContext,
  onDraftChange,
  onSubmit,
}: MessageComposerProps) {
  return (
    <div className="mx-auto grid w-full max-w-3xl shrink-0 gap-2">
      {contextArtifact ? (
        <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-[var(--border)] bg-white px-3 py-2 text-xs shadow-sm">
          <div className="min-w-0">
            <span className="font-semibold text-[var(--primary)]">
              Follow-up context
            </span>
            <span className="ml-2 text-[var(--muted-foreground)]">
              {artifactContextLabel(contextArtifact)} · run{" "}
              {contextArtifact.taskRunId.slice(0, 8)}
            </span>
          </div>
          <button
            className="rounded-full bg-slate-100 px-2.5 py-1 font-semibold text-slate-600 transition hover:bg-slate-200"
            onClick={onClearContext}
            type="button"
          >
            Clear context
          </button>
        </div>
      ) : null}
      <form
        className="flex gap-2 rounded-xl border border-[var(--border)] bg-white p-2 shadow-sm"
        data-region="composer"
        onSubmit={onSubmit}
      >
        <div className="flex min-w-0 flex-1 items-center gap-2 rounded-lg bg-[var(--surface-muted)] px-3">
          <MessageSquare
            aria-hidden="true"
            className="shrink-0 text-[var(--muted-foreground)]"
            size={16}
          />
          <input
            className="min-w-0 flex-1 bg-transparent py-3 text-sm outline-none"
            onChange={(event) => onDraftChange(event.target.value)}
            placeholder="@orchestrator 为演示应用构建登录页"
            type="text"
            value={draft}
          />
        </div>
        <Button disabled={isPending || draft.trim().length === 0} type="submit">
          <Send aria-hidden="true" size={16} />
          发送
        </Button>
      </form>
    </div>
  )
}

function artifactContextLabel(item: ArtifactPanelItem) {
  const labels: Record<ArtifactPanelItem["kind"], string> = {
    deployment: "Mock Deploy artifact",
    diff: "Diff artifact",
    preview: "Preview artifact",
    review: "Review artifact",
  }
  return labels[item.kind]
}
