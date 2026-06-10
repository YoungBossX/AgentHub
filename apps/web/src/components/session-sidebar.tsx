"use client"

import Link from "next/link"
import { type ReactNode, useMemo, useState } from "react"
import {
  Bot,
  ChevronRight,
  GitBranch,
  Brain,
  MoreHorizontal,
  Plus,
  Search,
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
  const [sessionSearch, setSessionSearch] = useState("")
  const visibleSessions = useMemo(() => {
    const query = sessionSearch.trim().toLowerCase()
    if (!query) {
      return sessions
    }

    return sessions.filter((session) =>
      [
        session.title,
        session.status,
        formatSessionTime(session.lastMessageAt),
      ].some((value) => value.toLowerCase().includes(query)),
    )
  }, [sessionSearch, sessions])

  return (
    <aside className="flex min-h-0 flex-col overflow-hidden border-b border-white/70 bg-[linear-gradient(150deg,#eef7f6_0%,#f6fbfa_46%,#ffffff_100%)] lg:border-b-0 lg:border-r">
      <div className="shrink-0 p-5 pb-4">
        <div className="rounded-lg bg-transparent">
          <div className="flex items-start gap-3">
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-slate-950 text-white shadow-sm">
              <GitBranch aria-hidden="true" size={18} />
            </span>
            <div className="min-w-0">
              <h2 className="truncate text-base font-semibold text-slate-950">
                {workspace.name}
              </h2>
            </div>
          </div>
        </div>

        <section className="mt-6 grid gap-1.5">
          <SidebarSettingsLink
            href="/settings/contacts"
            icon={<Users aria-hidden="true" size={17} />}
            label="联系人设置"
            meta={`${agents.length} 个`}
          />
          <SidebarSettingsLink
            href="/settings/agents"
            icon={<Bot aria-hidden="true" size={17} />}
            label="Agent 目录"
            meta="能力 / 状态"
          />
          <SidebarSettingsLink
            href="/settings/runtime"
            icon={<SlidersHorizontal aria-hidden="true" size={17} />}
            label="运行设置"
            meta="工作区 / Agent"
          />
          <SidebarSettingsLink
            href="/settings/memory"
            icon={<Brain aria-hidden="true" size={17} />}
            label="记忆设置"
            meta="规则 / 偏好"
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
        <div className="mb-3 flex items-center justify-between gap-3 px-1">
          <span className="text-[11px] font-bold uppercase tracking-normal text-[var(--text-muted)]">
            最近会话
          </span>
          <span className="shrink-0 text-[11px] font-semibold text-[var(--muted-foreground)]">
            {visibleSessions.length}/{sessions.length}
          </span>
        </div>
        <label className="mb-3 flex min-h-10 items-center gap-2 rounded-lg border border-white/70 bg-white/80 px-3 text-sm text-slate-700 shadow-sm">
          <Search aria-hidden="true" className="shrink-0 text-slate-400" size={15} />
          <span className="sr-only">搜索会话</span>
          <input
            aria-label="搜索会话"
            className="min-w-0 flex-1 bg-transparent text-sm outline-none placeholder:text-slate-400"
            onChange={(event) => setSessionSearch(event.target.value)}
            placeholder="搜索会话"
            type="search"
            value={sessionSearch}
          />
        </label>
        {sessionSearch.trim() ? (
          <div className="mb-2 px-1 text-xs text-[var(--muted-foreground)]">
            正在筛选：{sessionSearch.trim()}
          </div>
        ) : null}
        {selectedSessionId ? (
          <div className="mb-3 rounded-lg border border-white/80 bg-white/70 px-3 py-2 text-xs text-slate-700">
            当前聚焦 {taskCount} 个任务
          </div>
        ) : null}
        {visibleSessions.length === 0 && sessions.length > 0 ? (
          <div className="rounded-lg border border-dashed border-[var(--border)] bg-white/80 p-4 text-sm text-[var(--muted-foreground)]">
            没有匹配的会话。
          </div>
        ) : null}
        <div className="grid min-w-0 gap-2 overflow-hidden">
          {visibleSessions.map((session) => {
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
