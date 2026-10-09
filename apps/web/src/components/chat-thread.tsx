"use client"

import { type ReactNode } from "react"
import { Bot, Quote, Pin, PinOff } from "lucide-react"

import type { AgentContact, ChatMessage, WorkspaceSession } from "@/lib/api"
import { cn } from "@/lib/utils"
import { GroupSummaryCard } from "./group-summary-card"
import { ChatMarkdown } from "./chat-markdown"
import { CopyTextButton } from "./copy-text-button"
import { MessageAttachments } from "./message-attachments"
import { MessageRegeneration, RegenerationLineage } from "./message-regeneration"

type ChatThreadProps = {
  onRegenerateMessage?: (message: ChatMessage) => Promise<void>
  backendUrl?: string
  agents?: AgentContact[]
  messages: ChatMessage[]
  onQuoteMessage?: (message: ChatMessage) => void
  onRetryGroupSummary?: (groupId: string) => void
  onPinMessage?: (message: ChatMessage, pinned: boolean) => void
  actionsPending?: boolean
  selectedSession: WorkspaceSession | null
  taskCount: number
  taskListSlot?: ReactNode
}

export function ChatThread({
  onRegenerateMessage,
  backendUrl = "",
  agents = [],
  messages,
  onQuoteMessage,
  onRetryGroupSummary,
  onPinMessage,
  actionsPending = false,
  selectedSession,
  taskCount,
  taskListSlot,
}: ChatThreadProps) {
  return (
    <section
      className="min-h-0 flex-1 overflow-y-auto pr-1"
      data-region="center-scroll"
    >
      <div className="mx-auto grid w-full min-w-0 max-w-3xl grid-cols-1 gap-4">
        {messages.some((message) => message.pinnedAt) ? <details className="sticky top-0 z-10 rounded-lg border border-[var(--border)] bg-[var(--surface)] p-3 shadow-sm" aria-label="关键消息">
          <summary className="cursor-pointer text-sm font-medium"><Pin size={14} className="mr-2 inline" />置顶消息 · {messages.filter((message) => message.pinnedAt).length}</summary>
          <div className="mt-2 grid max-h-48 gap-1 overflow-y-auto">{messages.filter((message) => message.pinnedAt).map((message) => <button key={message.id} type="button" onClick={() => document.getElementById(`message-${message.id}`)?.scrollIntoView({ behavior: "smooth", block: "center" })} className="rounded p-2 text-left text-xs text-[var(--muted-foreground)] hover:bg-[var(--surface-muted)]">{message.contentMd.slice(0, 140)}</button>)}</div>
        </details> : null}
        {selectedSession && messages.length === 0 ? (
          <div className="rounded-lg border border-[var(--border)] bg-white p-5 shadow-sm">
            <div className="flex items-start gap-3">
              <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-[var(--primary)] text-[var(--primary-foreground)]">
                <Bot aria-hidden="true" size={16} />
              </span>
              <div>
                <p className="text-sm font-semibold text-slate-950">
                  {agents.find((agent) => agent.role === "orchestrator")?.displayName ?? "@orchestrator"}
                </p>
                <p className="mt-1 text-sm leading-6 text-[var(--text-secondary)]">
                  {taskCount > 0 ? "本会话已有执行记录。查看协作计划与成果，或发送消息继续修改。" : "描述你想构建的应用，或 @ 一位 Agent 开始协作。你可以随时查看执行过程，检查成果，再继续修改。"}
                </p>
              </div>
            </div>
          </div>
        ) : null}

        {messages.map((message) => (
          <MessageBubble
            onRegenerateMessage={onRegenerateMessage}
            backendUrl={backendUrl}
            message={message}
            agent={agents.find((agent) => agent.id === message.senderId || (message.senderType === "orchestrator" && agent.role === "orchestrator"))}
            key={message.id}
            onQuoteMessage={onQuoteMessage}
            onRetryGroupSummary={onRetryGroupSummary}
            onPinMessage={onPinMessage}
            actionsPending={actionsPending}
          />
        ))}


        {taskListSlot}
      </div>
    </section>
  )
}

function MessageBubble({
  onRegenerateMessage,
  backendUrl,
  message,
  agent,
  onQuoteMessage,
  onRetryGroupSummary,
  onPinMessage,
  actionsPending,
}: {
  onRegenerateMessage?: (message: ChatMessage) => Promise<void>
  backendUrl: string
  message: ChatMessage
  agent?: AgentContact
  onQuoteMessage?: (message: ChatMessage) => void
  onRetryGroupSummary?: (groupId: string) => void
  onPinMessage?: (message: ChatMessage, pinned: boolean) => void
  actionsPending?: boolean
}) {
  const isUser = message.senderType === "user"

  return (
    <article id={`message-${message.id}`} className={cn("flex min-w-0 scroll-mt-28 gap-3", isUser ? "justify-end" : "justify-start")}>
      {!isUser ? (
        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-[var(--primary-soft)] text-[var(--primary)]">
          <Bot aria-hidden="true" size={16} />
        </span>
      ) : null}
      <div
        className={cn(
          "min-w-0 max-w-[92%] rounded-lg px-4 py-3 text-sm leading-6 sm:max-w-[88%]",
          isUser
            ? "bg-[var(--user-bubble)] text-slate-800"
            : "border border-[var(--border)] bg-white text-slate-800",
        )}
      >
        <p
          className={cn(
            "mb-1 text-[11px] font-bold uppercase tracking-normal",
            isUser ? "text-slate-400" : "text-[var(--text-muted)]",
          )}
        >
          {message.groupSummary?.coordinatorName ?? agent?.displayName ?? senderLabel(message.senderType)}
          {message.pinnedAt ? <Pin aria-label="消息已置顶" size={12} className="ml-2 inline text-[var(--primary)]" /> : null}
        </p>
        {message.messageKind === "group_summary" && message.groupSummary?.evidence ? <GroupSummaryCard summary={message.groupSummary} onRetry={onRetryGroupSummary} /> : <ChatMarkdown content={message.contentMd} messageId={message.id} />}
        {message.attachments?.length ? <MessageAttachments items={message.attachments} backendUrl={backendUrl} /> : null}
        <RegenerationLineage message={message} />
        <div className={cn("mt-2 flex gap-1", isUser ? "justify-end" : "justify-start")}>
          {onPinMessage ? <button type="button" disabled={actionsPending} aria-label={message.pinnedAt ? "取消置顶消息" : "置顶消息"} title={message.pinnedAt ? "取消置顶消息" : "置顶关键消息"} onClick={() => onPinMessage(message, !message.pinnedAt)} className="inline-flex h-7 w-7 items-center justify-center rounded-md text-[var(--muted-foreground)] hover:bg-[var(--surface-muted)] disabled:opacity-40">{message.pinnedAt ? <PinOff size={13} /> : <Pin size={13} />}</button> : null}
          <CopyTextButton text={message.contentMd} label="复制消息" ariaLabel="Copy message" compact />
          <button
            aria-label="Quote as context"
            className={cn(
              "inline-flex h-7 w-7 items-center justify-center rounded-md transition",
              isUser
                ? "text-slate-400 hover:bg-slate-200"
                : "bg-slate-100 text-slate-600 hover:bg-slate-200",
            )}
            onClick={() => onQuoteMessage?.(message)}
            type="button"
          >
            <Quote aria-hidden="true" size={13} />
          </button>
        </div>
        {onRegenerateMessage ? <MessageRegeneration message={message} onRun={onRegenerateMessage} disabled={actionsPending} /> : null}
      </div>
    </article>
  )
}

function senderLabel(senderType: string) {
  if (senderType === "user") {
    return "用户"
  }
  if (senderType === "agent") {
    return "Agent"
  }
  return senderType
}
