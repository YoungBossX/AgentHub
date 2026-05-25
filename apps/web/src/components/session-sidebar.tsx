"use client"

import { GitBranch, Plus } from "lucide-react"

import { AgentContactList } from "@/components/agent-contact-list"
import { Button } from "@/components/ui/button"
import type { AgentContact, Workspace, WorkspaceSession } from "@/lib/api"
import { formatCompactDateTime } from "@/lib/date-format"
import { cn } from "@/lib/utils"

type SessionSidebarProps = {
  agents: AgentContact[]
  isPending: boolean
  mode: "direct" | "group"
  onCreateSession: () => void
  onModeChange: (mode: "direct" | "group") => void
  onSelectAgent: (agentId: string) => void
  onSelectSession: (sessionId: string) => void
  selectedAgentId: string | null
  selectedSessionId: string | null
  sessions: WorkspaceSession[]
  taskCount: number
  workspace: Workspace
}

export function SessionSidebar({
  agents,
  isPending,
  mode,
  onCreateSession,
  onModeChange,
  onSelectAgent,
  onSelectSession,
  selectedAgentId,
  selectedSessionId,
  sessions,
  taskCount,
  workspace,
}: SessionSidebarProps) {
  return (
    <aside className="flex min-h-0 flex-col overflow-hidden border-b border-[var(--border)] bg-[#FBF9FF] lg:border-b-0 lg:border-r">
      <div className="shrink-0 p-4">
        <div className="rounded-lg bg-transparent p-2">
          <div className="flex items-start gap-3">
            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-[var(--primary-soft)] text-[var(--primary)]">
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

          <div className="mt-4 grid grid-cols-2 gap-2 text-xs">
            <WorkspaceMeta label="会话" value={String(sessions.length)} />
            <WorkspaceMeta label="当前任务" value={String(taskCount)} />
          </div>
        </div>

        <Button
          className="mt-4 w-full"
          disabled={isPending}
          onClick={onCreateSession}
          type="button"
        >
          <Plus aria-hidden="true" size={16} />
          新建会话
        </Button>

        <AgentContactList
          agents={agents}
          mode={mode}
          onModeChange={onModeChange}
          onSelectAgent={onSelectAgent}
          selectedAgentId={selectedAgentId}
        />
      </div>

      <nav
        className="min-h-0 flex-1 overflow-y-auto px-3 pb-4"
        data-region="sidebar-scroll"
      >
        <div className="mb-2 px-1 text-[11px] font-bold uppercase tracking-normal text-[var(--text-muted)]">
          最近会话
        </div>
        <div className="grid gap-1.5">
          {sessions.map((session) => {
            const selected = session.id === selectedSessionId
            const smoke = session.title.toLowerCase().includes("smoke")
            return (
              <button
                className={cn(
                  "grid gap-1.5 rounded-lg border-r-4 p-2.5 text-left transition",
                  selected
                    ? "border-r-[var(--primary)] bg-[var(--primary-soft)]/80 text-slate-950 shadow-sm"
                    : "border-r-transparent bg-transparent text-slate-700 hover:bg-white/80",
                  smoke && !selected && "opacity-55",
                )}
                key={session.id}
                onClick={() => onSelectSession(session.id)}
                type="button"
              >
                <span className="flex items-start justify-between gap-3">
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
                  <span className="text-xs font-semibold text-[var(--primary)]">
                    聚焦 {taskCount} 个任务
                  </span>
                ) : null}
              </button>
            )
          })}

          {sessions.length === 0 ? (
            <div className="rounded-md border border-dashed border-[var(--border)] bg-white p-4 text-sm text-[var(--muted-foreground)]">
              暂无会话。
            </div>
          ) : null}
        </div>
      </nav>

      <div className="shrink-0 border-t border-[var(--border)] p-4 text-xs text-[var(--muted-foreground)]">
        <div className="flex items-center justify-between">
          <span>文档</span>
          <span>API</span>
          <span>支持</span>
        </div>
      </div>
    </aside>
  )
}

function formatSessionTime(value: string | null) {
  if (!value) {
    return "暂无消息"
  }

  return formatCompactDateTime(value)
}

function WorkspaceMeta({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded bg-[var(--surface-muted)] p-2">
      <p className="text-[11px] text-[var(--text-muted)]">{label}</p>
      <p className="mt-1 font-semibold text-slate-950">{value}</p>
    </div>
  )
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
