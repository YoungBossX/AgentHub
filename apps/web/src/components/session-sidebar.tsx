"use client"

import Link from "next/link"
import { type ReactNode } from "react"
import {
  ChevronRight,
  GitBranch,
  MoreHorizontal,
  Plus,
  SlidersHorizontal,
  Users,
} from "lucide-react"

import type { AgentContact, Workspace, WorkspaceSession } from "@/lib/api"
import { formatCompactDateTime } from "@/lib/date-format"
import { cn } from "@/lib/utils"

type SessionSidebarProps = {
  agents: AgentContact[]
  isPending: boolean
  onCreateSession: () => void
  onSelectSession: (sessionId: string) => void
  selectedSessionId: string | null
  sessions: WorkspaceSession[]
  taskCount: number
  workspace: Workspace
}

export function SessionSidebar({
  agents,
  isPending,
  onCreateSession,
  onSelectSession,
  selectedSessionId,
  sessions,
  taskCount,
  workspace,
}: SessionSidebarProps) {
  return (
    <aside className="flex min-h-0 flex-col overflow-hidden border-b border-white/70 bg-[linear-gradient(180deg,#edf8f7_0%,#f7fafb_58%,#ffffff_100%)] lg:border-b-0 lg:border-r">
      <div className="shrink-0 p-5 pb-4">
        <div className="rounded-lg bg-transparent">
          <div className="flex items-start gap-3">
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-slate-950 text-white shadow-sm">
              <GitBranch aria-hidden="true" size={18} />
            </span>
            <div className="min-w-0">
              <p className="text-[11px] font-bold uppercase tracking-normal text-[var(--text-muted)]">
                工作区
              </p>
              <h2 className="mt-1 truncate text-base font-semibold text-slate-950">
                {workspace.name}
              </h2>
              <p className="mt-1 truncate font-mono text-xs text-[var(--muted-foreground)]">
                {workspace.rootPath}
              </p>
            </div>
          </div>
        </div>

        <section className="mt-6 grid gap-1.5">
          <p className="mb-1 px-1 text-[11px] font-bold uppercase tracking-normal text-[var(--text-muted)]">
            Main menu
          </p>
          <SidebarSettingsLink
            href="/settings/contacts"
            icon={<Users aria-hidden="true" size={17} />}
            label="联系人设置"
            meta={`${agents.length} 个`}
          />
          <SidebarSettingsLink
            href="/settings/runtime"
            icon={<SlidersHorizontal aria-hidden="true" size={17} />}
            label="运行设置"
            meta="工作区 / Agent"
          />
          <SidebarSettingsLink
            href="/settings/other"
            icon={<MoreHorizontal aria-hidden="true" size={17} />}
            label="其他设置"
            meta="预留"
          />
        </section>

        <button
          className="mt-4 flex min-h-11 w-full items-center gap-3 rounded-full bg-slate-950 px-4 text-left text-sm font-semibold text-white shadow-sm transition hover:bg-black disabled:opacity-60"
          disabled={isPending}
          onClick={onCreateSession}
          type="button"
        >
          <Plus aria-hidden="true" size={16} />
          <span className="min-w-0 flex-1 truncate">新建会话</span>
        </button>
      </div>

      <nav
        className="min-h-0 flex-1 overflow-x-hidden overflow-y-auto px-5 pb-5 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
        data-region="sidebar-scroll"
      >
        <div className="mb-3 px-1 text-[11px] font-bold uppercase tracking-normal text-[var(--text-muted)]">
          最近会话
        </div>
        <div className="grid min-w-0 gap-2 overflow-hidden">
          {sessions.map((session) => {
            const selected = session.id === selectedSessionId
            const smoke = session.title.toLowerCase().includes("smoke")
            return (
              <button
                className={cn(
                  "grid min-w-0 gap-1.5 overflow-hidden rounded-lg border-l-4 p-3 text-left transition",
                  selected
                    ? "border-l-slate-950 bg-white text-slate-950 shadow-sm"
                    : "border-l-transparent bg-transparent text-slate-700 hover:bg-white/75",
                  smoke && !selected && "opacity-55",
                )}
                key={session.id}
                onClick={() => onSelectSession(session.id)}
                type="button"
              >
                <span className="flex min-w-0 items-start justify-between gap-3">
                  <span className="min-w-0">
                    <span className="block truncate text-sm font-semibold">
                      {session.title}
                    </span>
                    <span className="mt-1 block truncate text-xs text-[var(--muted-foreground)]">
                      {formatSessionTime(session.lastMessageAt)}
                    </span>
                  </span>
                  {smoke && !selected ? null : <SessionStatusDot status={session.status} />}
                </span>
                {selected ? (
                  <span className="text-xs font-semibold text-slate-950">
                    聚焦 {taskCount} 个任务
                  </span>
                ) : null}
              </button>
            )
          })}

          {sessions.length === 0 ? (
            <div className="rounded-lg border border-dashed border-[var(--border)] bg-white/80 p-4 text-sm text-[var(--muted-foreground)]">
              暂无会话。
            </div>
          ) : null}
        </div>
      </nav>

      <div className="shrink-0 border-t border-white/70 p-5 text-xs text-[var(--muted-foreground)]">
        <div className="flex items-center justify-between">
          <span>本地 Demo</span>
          <span>单用户</span>
          <span>SSE</span>
        </div>
      </div>
    </aside>
  )
}

function SidebarSettingsLink({
  href,
  icon,
  label,
  meta,
}: {
  href: string
  icon: ReactNode
  label: string
  meta: string
}) {
  return (
    <Link
      className="flex min-h-11 items-center gap-3 rounded-lg px-3 text-left text-sm text-slate-700 transition hover:bg-white/70 hover:text-slate-950"
      href={href}
    >
      <span className="flex h-7 w-7 shrink-0 items-center justify-center text-slate-950">
        {icon}
      </span>
      <span className="min-w-0 flex-1">
        <span className="block truncate font-semibold">{label}</span>
        <span className="mt-0.5 block truncate text-xs text-[var(--muted-foreground)]">
          {meta}
        </span>
      </span>
      <ChevronRight
        aria-hidden="true"
        className="shrink-0 text-slate-400"
        size={15}
      />
    </Link>
  )
}

function formatSessionTime(value: string | null) {
  if (!value) {
    return "暂无消息"
  }

  return formatCompactDateTime(value)
}

function SessionStatusDot({ status }: { status: string }) {
  return (
    <span
      aria-label={status}
      className={cn(
        "mt-1 h-2.5 w-2.5 shrink-0 rounded-full",
        status === "active" ? "bg-blue-600" : "bg-slate-300",
      )}
    />
  )
}
