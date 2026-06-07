"use client"

import { type FormEvent } from "react"
import { FileText, MessageSquare, Send, X } from "lucide-react"

import { Button } from "@/components/ui/button"
import type { ArtifactPanelItem } from "@/components/preview-card"
import type { ChatMessage } from "@/lib/api"

type MessageComposerProps = {
  contextArtifact: ArtifactPanelItem | null
  contextMessage: ChatMessage | null
  draft: string
  isPending: boolean
  onClearContext: () => void
  onDraftChange: (value: string) => void
  onSubmit: (event: FormEvent<HTMLFormElement>) => void
}

export function MessageComposer({
  contextArtifact,
  contextMessage,
  draft,
  isPending,
  onClearContext,
  onDraftChange,
  onSubmit,
}: MessageComposerProps) {
  const hasContext = Boolean(contextArtifact || contextMessage)

  return (
    <div className="mx-auto grid w-full max-w-4xl shrink-0 gap-2">
      {hasContext ? (
        <div className="grid gap-2 rounded-lg border border-[var(--border)] bg-white px-3 py-2 text-xs shadow-sm">
          <div className="flex items-center justify-between gap-2">
            <span className="font-semibold text-[var(--primary)]">待发送上下文</span>
            <button
              aria-label="清除上下文"
              className="inline-flex h-7 items-center gap-1 rounded-full bg-slate-100 px-2.5 font-semibold text-slate-600 transition hover:bg-slate-200"
              onClick={onClearContext}
              type="button"
            >
              <X aria-hidden="true" size={13} />
              清除
            </button>
          </div>
          {contextMessage ? (
            <div className="flex min-w-0 items-start gap-2 rounded-md bg-[var(--surface-muted)] px-2.5 py-2">
              <MessageSquare
                aria-hidden="true"
                className="mt-0.5 shrink-0 text-[var(--primary)]"
                size={14}
              />
              <div className="min-w-0">
                <p className="font-semibold text-slate-700">
                  引用消息 · {senderLabel(contextMessage.senderType)}
                </p>
                <p className="mt-1 line-clamp-2 text-[var(--muted-foreground)]">
                  {contextMessage.contentMd}
                </p>
              </div>
            </div>
          ) : null}
          {contextArtifact ? (
            <div className="flex min-w-0 items-center gap-2 rounded-md bg-[var(--surface-muted)] px-2.5 py-2">
              <FileText
                aria-hidden="true"
                className="shrink-0 text-[var(--primary)]"
                size={14}
              />
              <span className="min-w-0 truncate text-[var(--muted-foreground)]">
                {artifactContextLabel(contextArtifact)} · {contextArtifact.taskTitle} · run{" "}
                {contextArtifact.taskRunId.slice(0, 8)}
              </span>
            </div>
          ) : null}
        </div>
      ) : null}
      <form
        className="flex gap-2 rounded-lg border border-[var(--border)] bg-white p-2 shadow-sm"
        data-region="composer"
        onSubmit={onSubmit}
      >
        <div className="flex min-w-0 flex-1 items-center gap-2 rounded-md bg-[var(--surface-muted)] px-3">
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
    deployment: "部署产物",
    diff: "Diff 产物",
    preview: "预览产物",
    review: "评审产物",
  }
  return labels[item.kind]
}

function senderLabel(senderType: string) {
  if (senderType === "user") {
    return "用户"
  }
  if (senderType === "orchestrator") {
    return "orchestrator"
  }
  if (senderType === "agent") {
    return "Agent"
  }
  return senderType
}
