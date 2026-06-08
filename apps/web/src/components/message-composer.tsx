"use client"

import { type FormEvent } from "react"
import { ArrowDown, ArrowUp, FileText, MessageSquare, Send, X } from "lucide-react"

import { Button } from "@/components/ui/button"
import type { ArtifactPanelItem } from "@/components/preview-card"
import type { ChatMessage } from "@/lib/api"

export type ComposerContextItem = {
  artifact?: ArtifactPanelItem
  id: string
  kind: "artifact" | "deployment" | "message" | "note" | "selected_text"
  message?: ChatMessage
  summary?: string
  title: string
}

type MessageComposerProps = {
  contextItems: ComposerContextItem[]
  draft: string
  isPending: boolean
  onClearContext: () => void
  onDraftChange: (value: string) => void
  onMoveContextItem: (id: string, direction: "up" | "down") => void
  onRemoveContextItem: (id: string) => void
  onSubmit: (event: FormEvent<HTMLFormElement>) => void
}

export function MessageComposer({
  contextItems,
  draft,
  isPending,
  onClearContext,
  onDraftChange,
  onMoveContextItem,
  onRemoveContextItem,
  onSubmit,
}: MessageComposerProps) {
  const hasContext = contextItems.length > 0

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
          <ol className="grid gap-2">
            {contextItems.map((item, index) => (
              <li
                className="flex min-w-0 items-start gap-2 rounded-md bg-[var(--surface-muted)] px-2.5 py-2"
                key={item.id}
              >
                {item.kind === "message" ? (
                  <MessageSquare
                    aria-hidden="true"
                    className="mt-0.5 shrink-0 text-[var(--primary)]"
                    size={14}
                  />
                ) : (
                  <FileText
                    aria-hidden="true"
                    className="mt-0.5 shrink-0 text-[var(--primary)]"
                    size={14}
                  />
                )}
                <div className="min-w-0 flex-1">
                  <p className="truncate font-semibold text-slate-700">
                    {contextItemLabel(item)}
                  </p>
                  {item.summary ? (
                    <p className="mt-1 line-clamp-2 text-[var(--muted-foreground)]">
                      {item.summary}
                    </p>
                  ) : null}
                </div>
                <div className="flex shrink-0 items-center gap-1">
                  <button
                    aria-label={`上移上下文 ${item.title}`}
                    className="inline-flex h-7 w-7 items-center justify-center rounded-full bg-white text-slate-600 ring-1 ring-slate-200 transition hover:bg-slate-50 disabled:opacity-40"
                    disabled={index === 0}
                    onClick={() => onMoveContextItem(item.id, "up")}
                    type="button"
                  >
                    <ArrowUp aria-hidden="true" size={13} />
                  </button>
                  <button
                    aria-label={`下移上下文 ${item.title}`}
                    className="inline-flex h-7 w-7 items-center justify-center rounded-full bg-white text-slate-600 ring-1 ring-slate-200 transition hover:bg-slate-50 disabled:opacity-40"
                    disabled={index === contextItems.length - 1}
                    onClick={() => onMoveContextItem(item.id, "down")}
                    type="button"
                  >
                    <ArrowDown aria-hidden="true" size={13} />
                  </button>
                  <button
                    aria-label={`移除上下文 ${item.title}`}
                    className="inline-flex h-7 w-7 items-center justify-center rounded-full bg-white text-slate-600 ring-1 ring-slate-200 transition hover:bg-slate-50"
                    onClick={() => onRemoveContextItem(item.id)}
                    type="button"
                  >
                    <X aria-hidden="true" size={13} />
                  </button>
                </div>
              </li>
            ))}
          </ol>
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

export function contextItemFromArtifact(artifact: ArtifactPanelItem): ComposerContextItem {
  const latestVersion =
    artifact.kind === "workbench"
      ? (
          artifact.artifact.versions.find(
            (version) => version.version === artifact.artifact.version,
          ) ?? artifact.artifact.versions[artifact.artifact.versions.length - 1]
        )
      : null
  return {
    artifact,
    id: artifact.id,
    kind: artifact.kind === "deployment" ? "deployment" : "artifact",
    summary:
      latestVersion?.summary ||
      artifact.taskTitle ||
      artifact.artifact.title ||
      artifactContextLabel(artifact),
    title: artifact.artifact.title,
  }
}

export function contextItemFromMessage(message: ChatMessage): ComposerContextItem {
  return {
    id: `message:${message.id}`,
    kind: "message",
    message,
    summary: message.contentMd,
    title: senderLabel(message.senderType),
  }
}

export function buildComposerMessageContext(
  contextItems: ComposerContextItem[],
): Record<string, unknown> {
  const context: Record<string, unknown> = {}
  if (contextItems.length > 0) {
    context.contextItems = contextItems.map((item) => contextPayloadItem(item))
  }
  const firstArtifact = contextItems.find((item) => item.artifact)?.artifact ?? null
  if (firstArtifact) {
    const latestVersion = latestArtifactVersion(firstArtifact)
    context.selectedArtifactId = firstArtifact.artifact.artifactId
    context.selectedArtifactVersionId = latestVersion?.id ?? null
    context.selectedArtifact = {
      artifactId: firstArtifact.artifact.artifactId,
      kind: firstArtifact.kind,
      safeSummary:
        latestVersion?.summary || firstArtifact.taskTitle || firstArtifact.artifact.title,
      title: firstArtifact.artifact.title,
      type: firstArtifact.artifact.artifactType,
      versionId: latestVersion?.id ?? null,
    }
  }
  const firstMessage = contextItems.find((item) => item.message)?.message ?? null
  if (firstMessage) {
    context.quotedMessage = {
      contentMd: firstMessage.contentMd,
      messageId: firstMessage.id,
      senderType: firstMessage.senderType,
    }
  }
  return context
}

function contextPayloadItem(item: ComposerContextItem) {
  if (item.artifact) {
    const latestVersion = latestArtifactVersion(item.artifact)
    return {
      artifactId: item.artifact.artifact.artifactId,
      artifactVersionId: latestVersion?.id ?? null,
      id: item.id,
      kind: item.kind,
      selectedText: null,
      summary: item.summary,
      title: item.title,
      type: item.artifact.artifact.artifactType,
    }
  }
  if (item.message) {
    return {
      id: item.id,
      kind: "message",
      messageId: item.message.id,
      summary: item.message.contentMd,
      title: senderLabel(item.message.senderType),
    }
  }
  return {
    id: item.id,
    kind: item.kind,
    summary: item.summary,
    title: item.title,
  }
}

function latestArtifactVersion(item: ArtifactPanelItem) {
  if (item.kind !== "workbench") {
    return null
  }
  return (
    item.artifact.versions.find((version) => version.version === item.artifact.version) ??
    item.artifact.versions[item.artifact.versions.length - 1] ??
    null
  )
}

function contextItemLabel(item: ComposerContextItem) {
  if (item.kind === "message" && item.message) {
    return `引用消息 · ${senderLabel(item.message.senderType)}`
  }
  if (item.artifact) {
    return `${artifactContextLabel(item.artifact)} · ${item.artifact.taskTitle} · run ${item.artifact.taskRunId.slice(0, 8)}`
  }
  return item.title
}

function artifactContextLabel(item: ArtifactPanelItem) {
  const labels: Record<ArtifactPanelItem["kind"], string> = {
    deployment: "部署产物",
    diff: "Diff 产物",
    preview: "预览产物",
    review: "评审产物",
    workbench: "工作台产物",
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
