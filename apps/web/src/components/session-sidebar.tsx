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
  X,
  Pin,
  PinOff,
  Archive,
  ArchiveRestore,
} from "lucide-react"

import type { AgentContact, Workspace, WorkspaceSession } from "@/lib/api"
import { compareApiTimestamps, formatCompactDateTime } from "@/lib/date-format"
import { LocalTime, TimeZoneLabel, useLocalTimeZone } from "./local-time"
import { cn } from "@/lib/utils"

type SessionSidebarProps = {
  onClose?: () => void
  agents: AgentContact[]
  isPending: boolean
  onCreateSession: () => void
  onMentionAgent?: (role: string) => void
  onSelectSession: (sessionId: string) => void
  onOrganizeSession?: (sessionId: string, changes: { pinned?: boolean; archived?: boolean }) => void
  selectedSessionId: string | null
  sessions: WorkspaceSession[]
  taskCount: number
  workspace: Workspace
}

export function SessionSidebar({
  onClose,
  agents,
  isPending,
  onCreateSession,
  onSelectSession,
  onMentionAgent,
  onOrganizeSession,
  selectedSessionId,
  sessions,
  taskCount,
  workspace,
}: SessionSidebarProps) {
  const [sessionSearch, setSessionSearch] = useState("")
  const timeZone = useLocalTimeZone() ?? "UTC"
  const [sessionView, setSessionView] = useState<"active" | "archived">(() => sessions.some((session) => session.id === selectedSessionId && session.archivedAt) ? "archived" : "active")
  const viewSessions = sessions.filter((session) => sessionView === "archived" ? !!session.archivedAt : !session.archivedAt)
  const visibleSessions = useMemo(() => {
    const query = sessionSearch.trim().toLowerCase()
    return sessions.filter((session) => (sessionView === "archived" ? !!session.archivedAt : !session.archivedAt) && (!query ||
      [
        session.title,
        session.status,
        formatSessionTime(session.lastMessageAt, timeZone),
      ].some((value) => value.toLowerCase().includes(query))))
      .sort((a, b) => Number(!!b.pinnedAt) - Number(!!a.pinnedAt) || compareApiTimestamps(b.pinnedAt, a.pinnedAt) || compareApiTimestamps(b.lastMessageAt, a.lastMessageAt) || compareApiTimestamps(b.createdAt, a.createdAt) || a.id.localeCompare(b.id))
  }, [sessionSearch, sessions, sessionView, timeZone])

  return (
    <aside className="flex min-h-0 flex-col overflow-hidden border-b border-[var(--border)] bg-[var(--sidebar)] lg:border-b-0 lg:border-r">
      <div className="shrink-0 p-4 pb-4">
        {onClose ? <button aria-label="关闭会话列表" className="mb-2 ml-auto flex rounded-lg p-1.5 lg:hidden" onClick={onClose}><X size={16} /></button> : null}
        <div className="rounded-lg bg-transparent">
          <div className="flex items-start gap-3">
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-[var(--primary)] text-[var(--primary-foreground)]">
              <GitBranch aria-hidden="true" size={18} />
            </span>
            <div className="min-w-0">
              <h2 className="truncate text-base font-semibold text-slate-950">
                {workspace.name}
              </h2>
            </div>
          </div>
        </div>



        <button
          className="mt-5 flex min-h-9 w-full items-center gap-3 rounded-lg bg-[var(--primary)] px-4 text-left text-sm font-semibold text-[var(--primary-foreground)] shadow-sm transition hover:bg-[var(--primary-strong)] disabled:opacity-60"
          disabled={isPending}
          onClick={onCreateSession}
          type="button"
        >
          <Plus aria-hidden="true" size={16} />
          <span className="min-w-0 flex-1 truncate">新建会话</span>
        </button>
      </div>

      <nav
        className="min-h-0 flex-1 overflow-x-hidden overflow-y-auto px-3 pb-3 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
        data-region="sidebar-scroll"
      >
        <div className="mb-3 flex items-center justify-between gap-3 px-1">
          <span className="text-[11px] font-bold uppercase tracking-normal text-[var(--text-muted)]">
            {sessionView === "active" ? "最近会话" : "已归档会话"}
          </span>
          <span className="shrink-0 text-[11px] font-semibold text-[var(--muted-foreground)]">
            {visibleSessions.length}/{viewSessions.length}
          </span>
        </div>
        <div className="mb-3 grid grid-cols-2 gap-1 rounded-lg bg-[var(--surface-muted)] p-1" aria-label="会话列表视图">
          {(["active", "archived"] as const).map((view) => <button key={view} type="button" aria-pressed={sessionView === view} onClick={() => setSessionView(view)} className={cn("rounded-md px-2 py-1.5 text-xs", sessionView === view ? "bg-[var(--surface)] text-[var(--foreground)] shadow-sm" : "text-[var(--muted-foreground)]")}>{view === "active" ? "最近" : "已归档"}</button>)}
        </div>
        <label className="mb-3 flex min-h-9 items-center gap-2 rounded-lg border border-[var(--border)] bg-white px-3 text-sm text-slate-700 shadow-sm">
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
            {sessionSearch.trim() ? "没有匹配的会话。" : sessionView === "archived" ? "暂无已归档会话。" : "暂无最近会话。"}
          </div>
        ) : null}
        <div className="grid min-w-0 gap-1 overflow-hidden">
          {visibleSessions.map((session) => {
            const selected = session.id === selectedSessionId
            const smoke = session.title.toLowerCase().includes("smoke")
            return (
              <div key={session.id} data-session-id={session.id} className={cn("flex min-w-0 items-center rounded-lg border-l-2", selected ? "border-l-[var(--primary)] bg-[var(--primary-soft)]" : "border-l-transparent hover:bg-[var(--surface)]", smoke && !selected && "opacity-55")}>
              <button
                className={cn(
                  "grid min-w-0 flex-1 gap-1.5 overflow-hidden px-2 py-2.5 text-left transition",
                  selected
                    ? "text-[var(--primary)]"
                    : "text-[var(--foreground)]",
                )}
                onClick={() => onSelectSession(session.id)}
                type="button"
              >
                <span className="flex min-w-0 items-start justify-between gap-3">
                  <span className="min-w-0">
                    <span className="block truncate text-sm font-semibold">
                      {session.pinnedAt ? <Pin aria-label="已置顶" size={11} className="mr-1 inline" /> : null}
                      {session.title}
                    </span>
                    <span className="mt-1 block truncate text-xs text-[var(--muted-foreground)]">
                      <LocalTime value={session.lastMessageAt} emptyLabel="暂无消息" />
                    </span>
                  </span>
                  {smoke && !selected ? null : <SessionStatusDot status={session.archivedAt ? "archived" : session.status} />}
                </span>
                {selected ? (
                  <span className="text-xs font-semibold text-[var(--foreground)]">
                    聚焦 {taskCount} 个任务
                  </span>
                ) : null}
              </button>
              {onOrganizeSession ? <div className="flex shrink-0 flex-col gap-1 pr-1">
                <button type="button" disabled={isPending} aria-label={`${session.pinnedAt ? "取消置顶会话" : "置顶会话"}：${session.title}`} title={session.pinnedAt ? "取消置顶" : "置顶会话"} onClick={() => onOrganizeSession(session.id, { pinned: !session.pinnedAt })} className="rounded p-1.5 text-[var(--muted-foreground)] hover:bg-[var(--surface-muted)] disabled:opacity-40">{session.pinnedAt ? <PinOff size={13} /> : <Pin size={13} />}</button>
                <button type="button" disabled={isPending} aria-label={`${session.archivedAt ? "恢复会话" : "归档会话"}：${session.title}`} title={session.archivedAt ? "恢复到最近会话" : "归档会话（保留记录与运行）"} onClick={() => onOrganizeSession(session.id, { archived: !session.archivedAt })} className="rounded p-1.5 text-[var(--muted-foreground)] hover:bg-[var(--surface-muted)] disabled:opacity-40">{session.archivedAt ? <ArchiveRestore size={13} /> : <Archive size={13} />}</button>
              </div> : null}
              </div>
            )
          })}

          {sessions.length === 0 ? (
            <div className="rounded-lg border border-dashed border-[var(--border)] bg-white/80 p-4 text-sm text-[var(--muted-foreground)]">
              暂无会话。
            </div>
          ) : null}
        </div>
        <section className="mt-7 border-t border-[var(--border)] pt-4" aria-label="Agent 联系人">
          <div className="mb-2 flex items-center justify-between gap-2 px-2"><p className="text-[11px] font-semibold text-slate-400">Agent 联系人</p><Link href="/settings/agents#create-agent" className="text-[10px] font-medium text-[var(--primary)] hover:underline">对话创建</Link></div>
          {agents.map((agent, index) => <button key={agent.id} disabled={agent.status !== "available" || (!agent.mentionAlias && !["orchestrator", "frontend", "backend", "qa"].includes(agent.role))} onClick={() => onMentionAgent?.(agent.mentionAlias ?? agent.role)} className="flex w-full items-center gap-2.5 rounded-lg px-2 py-2 text-left hover:bg-white disabled:cursor-default disabled:opacity-50" title={`@${agent.mentionAlias ?? agent.role} · ${agent.description}`}>
            <span className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-[11px] font-bold ${index % 3 === 0 ? "bg-indigo-100 text-indigo-600" : index % 3 === 1 ? "bg-emerald-100 text-emerald-700" : "bg-amber-100 text-amber-700"}`}>{agent.avatarInitials}</span>
            <span className="min-w-0"><span className="block truncate text-xs font-medium text-slate-700">{agent.displayName}</span><span className="block truncate text-[10px] text-slate-400">{agent.capabilityTags.slice(0, 2).join(" · ") || agent.role}</span></span>
          </button>)}
        </section>
      </nav>

      <div className="shrink-0 border-t border-[var(--border)] p-3 text-xs text-slate-500">
        <details><summary className="cursor-pointer rounded-lg px-2 py-2 font-medium">工作区设置</summary>        <section className="grid gap-1">
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
            href={selectedSessionId ? `/settings/memory?session=${encodeURIComponent(selectedSessionId)}` : "/settings/memory"}
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
        </section></details>
        <p className="mt-2 px-2 text-[10px] text-slate-400">本地工作区 · {workspace.name}</p>
        <TimeZoneLabel className="mt-1 block truncate px-2 text-[10px] text-[var(--muted-foreground)]" />
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
      className="flex min-h-8 items-center gap-3 rounded-lg px-3 text-left text-sm text-slate-700 transition hover:bg-white/70 hover:text-slate-950"
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

function formatSessionTime(value: string | null, timeZone: string) {
  if (!value) {
    return "暂无消息"
  }

  return formatCompactDateTime(value, timeZone)
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
