"use client"

import { type ReactNode } from "react"
import { Bot, Copy, Quote } from "lucide-react"

import type { ChatMessage, WorkspaceSession } from "@/lib/api"
import { cn } from "@/lib/utils"

type ChatThreadProps = {
  messages: ChatMessage[]
  onQuoteMessage?: (message: ChatMessage) => void
  selectedSession: WorkspaceSession | null
  taskCount: number
  taskListSlot?: ReactNode
}

export function ChatThread({
  messages,
  onQuoteMessage,
  selectedSession,
  taskCount,
  taskListSlot,
}: ChatThreadProps) {
  return (
    <section
      className="min-h-0 flex-1 overflow-y-auto pr-1"
      data-region="center-scroll"
    >
      <div className="mx-auto grid max-w-4xl gap-4">
        {selectedSession && messages.length === 0 ? (
          <div className="rounded-lg border border-[var(--border)] bg-white p-5 shadow-sm">
            <div className="flex items-start gap-3">
              <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-[var(--primary)] text-white">
                <Bot aria-hidden="true" size={16} />
              </span>
              <div>
                <p className="text-sm font-semibold text-slate-950">
                  @orchestrator
                </p>
                <p className="mt-1 text-sm leading-6 text-[var(--text-secondary)]">
                  当前会话拥有独立 worktree。发送需求后，Orchestrator
                  会生成执行计划与任务时间线。
                </p>
              </div>
            </div>
          </div>
        ) : null}

        {messages.map((message) => (
          <MessageBubble
            message={message}
            key={message.id}
            onQuoteMessage={onQuoteMessage}
          />
        ))}

        {taskCount > 0 ? <OrchestratorPlanCard taskCount={taskCount} /> : null}

        {taskListSlot}
      </div>
    </section>
  )
}

function MessageBubble({
  message,
  onQuoteMessage,
}: {
  message: ChatMessage
  onQuoteMessage?: (message: ChatMessage) => void
}) {
  const isUser = message.senderType === "user"
  function copyMessage() {
    void navigator.clipboard?.writeText(message.contentMd)
  }

  return (
    <article className={cn("flex gap-3", isUser ? "justify-end" : "justify-start")}>
      {!isUser ? (
        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-[var(--primary-soft)] text-[var(--primary)]">
          <Bot aria-hidden="true" size={16} />
        </span>
      ) : null}
      <div
        className={cn(
          "max-w-[82%] rounded-lg px-4 py-3 text-sm leading-6 shadow-sm",
          isUser
            ? "bg-[var(--primary)] text-white"
            : "border border-[var(--border)] bg-white text-slate-800",
        )}
      >
        <p
          className={cn(
            "mb-1 text-[11px] font-bold uppercase tracking-normal",
            isUser ? "text-indigo-100" : "text-[var(--text-muted)]",
          )}
        >
          {senderLabel(message.senderType)}
        </p>
        <p className="whitespace-pre-wrap">{message.contentMd}</p>
        <div className={cn("mt-2 flex gap-1", isUser ? "justify-end" : "justify-start")}>
          <button
            aria-label="Copy message"
            className={cn(
              "inline-flex h-7 w-7 items-center justify-center rounded-md transition",
              isUser
                ? "bg-white/15 text-white hover:bg-white/25"
                : "bg-slate-100 text-slate-600 hover:bg-slate-200",
            )}
            onClick={copyMessage}
            type="button"
          >
            <Copy aria-hidden="true" size={13} />
          </button>
          <button
            aria-label="Quote as context"
            className={cn(
              "inline-flex h-7 w-7 items-center justify-center rounded-md transition",
              isUser
                ? "bg-white/15 text-white hover:bg-white/25"
                : "bg-slate-100 text-slate-600 hover:bg-slate-200",
            )}
            onClick={() => onQuoteMessage?.(message)}
            type="button"
          >
            <Quote aria-hidden="true" size={13} />
          </button>
        </div>
      </div>
    </article>
  )
}

function OrchestratorPlanCard({ taskCount }: { taskCount: number }) {
  return (
    <section className="rounded-lg border border-[var(--border)] bg-white p-4 shadow-sm">
      <div className="flex items-start gap-3">
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-slate-950 text-white">
          <Bot aria-hidden="true" size={17} />
        </span>
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <p className="font-mono text-sm font-semibold text-[var(--primary-strong)]">
              @orchestrator
            </p>
            <span className="rounded-full bg-emerald-50 px-2.5 py-1 text-[11px] font-bold uppercase tracking-normal text-emerald-700">
              规划完成
            </span>
          </div>
          <p className="mt-2 text-sm leading-6 text-slate-800">
            已生成包含 {taskCount} 个任务的指挥中心执行计划。你可以在下方时间线中启动运行、恢复失败、查看 Diff 证据、启动预览并创建模拟部署卡片。
          </p>
        </div>
      </div>
    </section>
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
